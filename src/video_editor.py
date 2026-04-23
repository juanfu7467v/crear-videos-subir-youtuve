import logging
import os
import random
import json
from pathlib import Path
from PIL import Image, ImageFilter as pil_filters
import numpy as np
from src.utils import validate_video, cleanup_ffmpeg

if not hasattr(Image, 'ANTIALIAS'):
    try:
        from PIL import Image
        Image.ANTIALIAS = Image.Resampling.LANCZOS
    except Exception:
        pass

import subprocess
from src.ass_generator import ASSGenerator
from moviepy.editor import (
    VideoFileClip, ImageClip, AudioFileClip, concatenate_videoclips, 
    CompositeVideoClip, afx, vfx
)
from moviepy.audio.AudioClip import AudioArrayClip, concatenate_audioclips, CompositeAudioClip

logger = logging.getLogger(__name__)

def apply_blur(image):
    pil_img = Image.fromarray(image.astype('uint8'))
    pil_img = pil_img.filter(pil_filters.GaussianBlur(radius=15))
    return np.array(pil_img)

class VideoEditor:
    def __init__(self):
        logger.info("Inicializando VideoEditor con Sincronización Palabra por Palabra...")

    def create_video(self, audio_path, media_list, script_data, format_type, output_path, music_dir="assets/music", thumbnail_path=None):
        # 1. Cargar Audio Principal
        if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
            raise Exception(f"Archivo de audio no encontrado o vacío: {audio_path}")
            
        tts_audio = AudioFileClip(audio_path)
        duration = float(tts_audio.duration)
        is_short = "short" in str(format_type).lower()

        target_h = 1920 if is_short else 1080
        target_w = 1080 if is_short else 1920
        
        # 2. Preparar Clips Visuales
        clips = []
        current_time = 0.0
        for i, item in enumerate(media_list):
            path_str = str(item.get("path", ""))
            if not path_str or not Path(path_str).exists() or os.path.getsize(path_str) == 0: 
                continue
            
            try:
                clip_duration = float(item.get("segment_duration", 5.0))
                if item.get("type") == "video":
                    raw_clip = VideoFileClip(path_str, audio=False).resize(height=target_h)
                    if raw_clip.duration < clip_duration:
                        clip = raw_clip.loop(duration=clip_duration)
                    else:
                        clip = raw_clip.subclip(0, clip_duration)
                else:
                    clip = ImageClip(path_str).set_duration(clip_duration)
                    clip = clip.fx(vfx.resize, lambda t: 1 + 0.02*t)

                # Ajustar al formato
                if is_short:
                    bg = clip.resize(height=target_h)
                    if bg.w < target_w: bg = bg.resize(width=target_w)
                    bg = bg.crop(x_center=bg.w/2, y_center=bg.h/2, width=target_w, height=target_h)
                    bg = bg.fl_image(apply_blur).fx(vfx.colorx, 0.6)
                    
                    fg = clip.resize(width=target_w) if clip.w/clip.h > target_w/target_h else clip.resize(height=target_h)
                    clip = CompositeVideoClip([bg, fg.set_position("center")], size=(target_w, target_h))
                else:
                    clip = clip.resize(height=target_h)
                    if clip.w > target_w: clip = clip.crop(x_center=clip.w/2, width=target_w)
                    elif clip.w < target_w: clip = clip.resize(width=target_w)

                clip = clip.set_start(current_time).set_duration(clip_duration)
                clips.append(clip)
                current_time += clip_duration
                if current_time >= duration: break
            except Exception as e:
                logger.warning(f"Error procesando clip {path_str}: {e}")
                continue

        visual_base = CompositeVideoClip(clips, size=(target_w, target_h)) if clips else None
        if not visual_base: raise Exception("No se pudieron cargar clips visuales")

        # Miniatura para Shorts
        start_offset = 0.0
        if is_short and thumbnail_path and os.path.exists(thumbnail_path) and os.path.getsize(thumbnail_path) > 0:
            thumb_clip = ImageClip(thumbnail_path).set_duration(1.0).set_start(0).resize(height=target_h)
            if thumb_clip.w < target_w: thumb_clip = thumb_clip.resize(width=target_w)
            thumb_clip = thumb_clip.crop(x_center=thumb_clip.w/2, y_center=thumb_clip.h/2, width=target_w, height=target_h)
            visual_base = visual_base.set_start(1.0)
            visual_base = CompositeVideoClip([thumb_clip, visual_base], size=(target_w, target_h))
            duration += 1.0
            start_offset = 1.0

        # 3. Música de Fondo con Bucle (Audio Loop)
        final_audio = tts_audio.set_start(start_offset)
        try:
            music_files = list(Path(music_dir).glob("*.mp3"))
            if music_files:
                music_path = str(random.choice(music_files))
                bg_music = AudioFileClip(music_path).volumex(0.15)
                
                # Aplicar bucle si la música es más corta que el video
                if bg_music.duration < duration:
                    bg_music = bg_music.fx(afx.audio_loop, duration=duration)
                else:
                    bg_music = bg_music.set_duration(duration)
                
                final_audio = CompositeAudioClip([final_audio, bg_music])
        except Exception as e:
            logger.warning(f"Error al añadir música de fondo: {e}")

        # 4. Composición Base (Sin subtítulos de MoviePy)
        final_video = visual_base.set_audio(final_audio).set_duration(duration)
        
        # Guardar video temporal sin subtítulos
        temp_no_subs = output_path.replace(".mp4", "_no_subs.mp4")
        final_video.write_videofile(temp_no_subs, fps=24, codec="libx264", audio_codec="aac", threads=4, preset="ultrafast", logger=None)
        
        # 5. SUBTÍTULOS AVANZADOS CON FFmpeg (Estilo ASS/Karaoke)
        ts_path = audio_path.replace(".mp3", ".json")
        ass_path = output_path.replace(".mp4", ".ass")
        
        if os.path.exists(ts_path) and os.path.getsize(ts_path) > 0:
            try:
                with open(ts_path, "r", encoding="utf-8") as f:
                    word_timestamps = json.load(f)
                
                # Generar archivo ASS
                ass_gen = ASSGenerator()
                ass_gen.generate_ass(word_timestamps, ass_path, start_offset=start_offset)
                
                # "Quemar" subtítulos usando FFmpeg directamente
                logger.info("Quemando subtítulos ASS con FFmpeg...")
                # Escapar la ruta para el filtro ass de ffmpeg
                # En FFmpeg, los dos puntos en la ruta del archivo deben escaparse
                escaped_ass_path = ass_path.replace(":", "\\:")
                
                cmd = [
                    "ffmpeg", "-y", "-i", temp_no_subs,
                    "-vf", f"ass={escaped_ass_path}",
                    "-c:a", "copy", "-preset", "ultrafast", output_path
                ]
                # Usamos shell=True si hay problemas con argumentos complejos, 
                # pero con lista de argumentos suele ser más seguro.
                subprocess.run(cmd, check=True, capture_output=True)
                logger.info(f"✅ Video final con subtítulos generado: {output_path}")
                
                # Limpiar archivo temporal
                if os.path.exists(temp_no_subs): os.remove(temp_no_subs)
            except Exception as e:
                logger.error(f"Error quemando subtítulos ASS: {e}")
                # Si falla FFmpeg, usamos el video sin subtítulos como final
                if os.path.exists(temp_no_subs): os.rename(temp_no_subs, output_path)
        else:
            logger.warning("No se encontraron timestamps, generando video sin subtítulos.")
            if os.path.exists(temp_no_subs): os.rename(temp_no_subs, output_path)

        # Limpieza final de clips
        tts_audio.close()
        final_video.close()
        cleanup_ffmpeg()
        
        return output_path
