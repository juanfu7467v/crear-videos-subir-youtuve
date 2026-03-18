import logging
import os
import random
from pathlib import Path
from PIL import Image
import numpy as np

# PARCHE: Esto obliga a que MoviePy encuentre la propiedad que busca
Image.ANTIALIAS = Image.Resampling.LANCZOS 

from moviepy.editor import (
    VideoFileClip, ImageClip, AudioFileClip, concatenate_videoclips, 
    CompositeVideoClip, TextClip, afx, vfx
)

logger = logging.getLogger(__name__)

class VideoEditor:
    def __init__(self):
        logger.info("Inicializando VideoEditor...")

    def create_video(self, audio_path, media_list, script_data, format_type, output_path, music_dir="assets/music"):
        # 1. Cargar Audio Principal (TTS) para determinar duración
        tts_audio = AudioFileClip(audio_path)
        duration = float(tts_audio.duration)

        is_short = "short" in str(format_type).lower() if format_type else (duration <= 60.0)
        
        target_h = 1920 if is_short else 1080
        target_w = 1080 if is_short else 1920
        
        logger.info(f"Formato detectado: {'Short (9:16)' if is_short else 'Largo (16:9)'} - Duración: {duration:.2f}s")
        
        # 2. Preparar Clips Visuales
        clips = []
        current_time = 0.0
        for i, item in enumerate(media_list):
            path_str = str(item.get("path", ""))
            if not path_str or not Path(path_str).exists():
                logger.warning(f"Clip {i} no encontrado o ruta vacía: {path_str}")
                continue
            
            # Validación de tamaño de archivo (evitar 0 bytes)
            if os.path.getsize(path_str) == 0:
                logger.warning(f"Clip {i} tiene 0 bytes, saltando: {path_str}")
                continue
            
            item_type = str(item.get("type", "video"))
            source = str(item.get("source", ""))
            
            try:
                # Asegurar que la duración sea float
                try:
                    clip_duration = float(item.get("segment_duration", 5.0))
                except (TypeError, ValueError):
                    clip_duration = 5.0

                if item_type == "video":
                    # Cargar video con manejo de errores para archivos corruptos
                    try:
                        raw_clip = VideoFileClip(path_str, audio=False)
                    except Exception as ve:
                        logger.warning(f"Video corrupto detectado ({path_str}): {ve}")
                        continue
                    
                    raw_duration = float(raw_clip.duration)
                    
                    if raw_duration < clip_duration:
                        clip = raw_clip.loop(duration=clip_duration)
                    else:
                        # Evitar el último frame problemático
                        safe_end = min(raw_duration - 0.1, clip_duration)
                        clip = raw_clip.subclip(0, safe_end).set_duration(clip_duration)
                    
                    # MEJORA COPYRIGHT: Aplicar cambios sutiles a clips reales
                    if "youtube" in source or "kinocheck" in source:
                        if random.random() > 0.5:
                            clip = clip.fx(vfx.mirror_x)
                        clip = clip.fx(vfx.resize, 1.1)
                else:
                    clip = ImageClip(path_str).set_duration(float(clip_duration))
                    # Zoom dinámico para imágenes
                    clip = clip.fx(vfx.resize, lambda t: 1 + 0.02*t)
                
                # Redimensionar y centrar/recortar
                clip = clip.resize(height=target_h)
                
                # Forzar valores float para evitar errores de tipo en comparaciones posteriores
                clip_w = float(clip.w)
                clip_h = float(clip.h)
                target_w_f = float(target_w)
                target_h_f = float(target_h)

                if clip_w > target_w_f:
                    x_center = clip_w / 2.0
                    clip = clip.crop(x1=float(x_center - target_w_f / 2.0), y1=0.0, x2=float(x_center + target_w_f / 2.0), y2=target_h_f)
                elif clip_w < target_w_f:
                    diff = target_w_f - clip_w
                    left = int(diff // 2)
                    right = int(diff - left)
                    clip = clip.margin(left=left, right=right, color=(0,0,0))
                
                clip = clip.set_start(current_time)
                clips.append(clip)
                current_time += clip_duration
                if current_time >= duration: break
            except Exception as e:
                logger.warning(f"Error procesando clip {path_str}: {e}")
                continue
            
        if not clips:
            logger.error("No se pudieron cargar clips visuales válidos.")
            raise Exception("No visual clips available")

        visual_base = concatenate_videoclips(clips, method="chain")
        visual_base = visual_base.set_duration(duration)
        
        # 3. Añadir Música de Fondo
        final_audio = tts_audio
        try:
            music_files = list(Path(music_dir).glob("*.mp3"))
            if music_files:
                bg_music_path = random.choice(music_files)
                logger.info(f"Añadiendo música de fondo: {bg_music_path.name}")
                bg_music = AudioFileClip(str(bg_music_path))
                
                bg_music = bg_music.volumex(0.15)
                if float(bg_music.duration) < duration:
                    bg_music = afx.audio_loop(bg_music, duration=duration)
                else:
                    bg_music = bg_music.set_duration(duration)
                
                from moviepy.audio.AudioClip import CompositeAudioClip
                final_audio = CompositeAudioClip([tts_audio, bg_music])
        except Exception as e:
            logger.error(f"Error al añadir música de fondo: {e}")

        # 4. Añadir Subtítulos
        full_script = str(script_data.get('full_script', ''))
        subtitles = []
        
        import re
        raw_sentences = re.split(r'[.,!?\n]', full_script)
        sentences = []
        for s in raw_sentences:
            s = s.strip()
            if not s: continue
            while len(s) > 60:
                split_idx = s[:60].rfind(' ')
                if split_idx == -1: split_idx = 60
                sentences.append(s[:split_idx].strip())
                s = s[split_idx:].strip()
            if s: sentences.append(s)

        if sentences:
            time_per_sentence = float(duration) / len(sentences)
            for i, sentence in enumerate(sentences):
                try:
                    fs = 120 if is_short else 80
                    txt_clip = TextClip(
                        sentence, 
                        fontsize=fs, 
                        color='yellow',
                        font='Liberation-Sans-Bold',
                        stroke_color='black',
                        stroke_width=4,
                        method='caption',
                        size=(target_w * 0.9, None),
                        align='center'
                    ).set_start(float(i * time_per_sentence)).set_duration(float(time_per_sentence)).set_position(('center', target_h * 0.75))
                    subtitles.append(txt_clip)
                except Exception as e:
                    logger.warning(f"No se pudo crear subtítulo para '{sentence[:20]}...': {e}")

        # 5. Componer Video Final
        final_video = CompositeVideoClip([visual_base] + subtitles, size=(target_w, target_h)).set_audio(final_audio)
        final_video = final_video.set_duration(duration)
        
        logger.info(f"Renderizando video final en {output_path}...")
        final_video.write_videofile(
            str(output_path), 
            fps=24, 
            codec="libx264", 
            audio_codec="aac", 
            logger=None, 
            preset="ultrafast", 
            threads=1,
            ffmpeg_params=["-crf", "28", "-tune", "stillimage"]
        )
        
        final_video.close()
        visual_base.close()
        for c in clips:
            try:
                c.close()
            except:
                pass
        
        tts_audio.close()
        if 'bg_music' in locals(): 
            try:
                bg_music.close()
            except:
                pass
        
        return output_path
