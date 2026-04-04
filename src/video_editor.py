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
            
            if os.path.getsize(path_str) == 0:
                logger.warning(f"Clip {i} tiene 0 bytes, saltando: {path_str}")
                continue
            
            item_type = str(item.get("type", "video"))
            source = str(item.get("source", ""))
            
            try:
                try:
                    clip_duration = float(item.get("segment_duration", 5.0))
                except (TypeError, ValueError):
                    clip_duration = 5.0

                if item_type == "video":
                    try:
                        raw_clip = VideoFileClip(path_str, audio=False)
                    except Exception as ve:
                        logger.warning(f"Video corrupto detectado ({path_str}): {ve}")
                        continue
                    
                    raw_duration = float(raw_clip.duration)
                    if raw_duration < clip_duration:
                        clip = raw_clip.loop(duration=clip_duration)
                    else:
                        safe_end = min(raw_duration - 0.1, clip_duration)
                        clip = raw_clip.subclip(0, safe_end).set_duration(clip_duration)
                    
                    if "youtube" in source or "kinocheck" in source:
                        if random.random() > 0.5:
                            clip = clip.fx(vfx.mirror_x)
                        clip = clip.fx(vfx.resize, 1.1)
                else:
                    clip = ImageClip(path_str).set_duration(float(clip_duration))
                    clip = clip.fx(vfx.resize, lambda t: 1 + 0.02*t)
                
                # MEJORAS VISUALES: Nitidez, Brillo y Contraste
                # eq=contrast=1.1:brightness=0.05
                # unsharp=5:5:1.0:5:5:0.0
                # MoviePy no tiene unsharp nativo fácil, usamos colorx y lum_contrast
                clip = clip.fx(vfx.lum_contrast, lum=12, contrast=0.1) # Simula brillo 0.05 y contraste 1.1
                
                # Redimensionar según formato
                if is_short:
                    # TÉCNICA: Fondo desenfocado para Shorts
                    # 1. Crear el fondo (el mismo clip, redimensionado para cubrir 9:16 y desenfocado)
                    bg = clip.resize(height=target_h)
                    # Si el ancho sigue siendo menor que el target, ajustar por ancho
                    if bg.w < target_w:
                        bg = bg.resize(width=target_w)
                    
                    # Recortar fondo para que sea exactamente 1080x1920
                    bg = bg.crop(x_center=bg.w/2, y_center=bg.h/2, width=target_w, height=target_h)
                    
                    # MEJORA: Desenfoque manual con PIL (evita errores de MoviePy)
                    from PIL import ImageFilter as pil_filters
                    def apply_blur(image):
                        # Convertir frame de numpy a PIL
                        pil_img = Image.fromarray(image.astype('uint8'))
                        # Aplicar desenfoque
                        pil_img = pil_img.filter(pil_filters.GaussianBlur(radius=15))
                        # Convertir de vuelta a numpy
                        return np.array(pil_img)
                    
                    bg = bg.fl_image(apply_blur)
                    bg = bg.fx(vfx.colorx, 0.7) # Oscurecer un poco el fondo
                    
                    # 2. Crear el frente (el clip original manteniendo su relación de aspecto)
                    # Redimensionar para que quepa en el ancho
                    fg = clip.resize(width=target_w)
                    # Si al redimensionar por ancho, la altura supera el target, redimensionar por altura
                    if fg.h > target_h:
                        fg = fg.resize(height=target_h)
                    
                    # 3. Componer el clip individual (fondo + frente centrado)
                    clip = CompositeVideoClip([bg, fg.set_position("center")], size=(target_w, target_h))
                else:
                    # Para videos largos, mantenemos el resize/crop estándar pero con las mejoras visuales ya aplicadas
                    clip = clip.resize(height=target_h)
                    if clip.w > target_w:
                        clip = clip.crop(x_center=clip.w/2, y_center=clip.h/2, width=target_w, height=target_h)
                    elif clip.w < target_w:
                        diff = target_w - clip.w
                        clip = clip.margin(left=int(diff//2), right=int(diff-diff//2), color=(0,0,0))
                
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

        total_clips_duration = sum(c.duration for c in clips)
        if total_clips_duration < duration:
            logger.info(f"Clips insuficientes ({total_clips_duration:.2f}s < {duration:.2f}s). Repitiendo clips...")
            original_clips = clips.copy()
            while total_clips_duration < duration:
                shuffled_clips = original_clips.copy()
                random.shuffle(shuffled_clips)
                for c in shuffled_clips:
                    new_c = c.copy().set_start(total_clips_duration)
                    if random.random() > 0.5:
                        new_c = new_c.fx(vfx.mirror_x)
                    clips.append(new_c)
                    total_clips_duration += c.duration
                    if total_clips_duration >= duration:
                        break

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
        sentences = [s.strip() for s in raw_sentences if s.strip()]
        
        final_sentences = []
        for s in sentences:
            while len(s) > 60:
                split_idx = s[:60].rfind(' ')
                if split_idx == -1: split_idx = 60
                final_sentences.append(s[:split_idx].strip())
                s = s[split_idx:].strip()
            if s: final_sentences.append(s)

        if final_sentences:
            time_per_sentence = float(duration) / len(final_sentences)
            for i, sentence in enumerate(final_sentences):
                try:
                    fs = 150 if is_short else 100
                    txt_clip = TextClip(
                        sentence, 
                        fontsize=fs, 
                        color='white',
                        font='Liberation-Sans-Bold',
                        stroke_color='black',
                        stroke_width=5,
                        method='caption',
                        size=(target_w * 0.9, None),
                        align='center',
                        bg_color='black'
                    ).set_start(float(i * time_per_sentence)).set_duration(float(time_per_sentence)).set_position(('center', target_h * 0.75))
                    subtitles.append(txt_clip)
                except Exception as e:
                    logger.warning(f"No se pudo crear subtítulo: {e}")

        # 5. Componer Video Final
        final_video = CompositeVideoClip([visual_base] + subtitles, size=(target_w, target_h)).set_audio(final_audio)
        final_video = final_video.set_duration(duration)
        
        logger.info(f"Renderizando video final en {output_path}...")
        
        # MEJORA: Mayor bitrate para evitar pérdida de calidad
        # -b:v 5M solicitado
        ffmpeg_params = [
            "-crf", "18", # Menor CRF = mayor calidad (rango 18-28, 18 es visualmente sin pérdida)
            "-tune", "film",
            "-b:v", "5M", # Bitrate de video 5Mbps
            "-maxrate", "8M",
            "-bufsize", "10M"
        ]
        
        final_video.write_videofile(
            str(output_path), 
            fps=24, 
            codec="libx264", 
            audio_codec="aac", 
            logger=None, 
            preset="medium", # Cambio de ultrafast a medium para mejor compresión/calidad
            threads=4,
            ffmpeg_params=ffmpeg_params
        )
        
        final_video.close()
        visual_base.close()
        for c in clips:
            try: c.close()
            except: pass
        tts_audio.close()
        if 'bg_music' in locals(): 
            try: bg_music.close()
            except: pass
        
        return output_path
