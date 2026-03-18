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
    CompositeVideoClip, TextClip, afx
)

logger = logging.getLogger(__name__)

class VideoEditor:
    def __init__(self):
        logger.info("Inicializando VideoEditor...")

    def create_video(self, audio_path, media_list, script_data, format_type, output_path, music_dir="assets/music"):
        # 1. Cargar Audio Principal (TTS) para determinar duración
        tts_audio = AudioFileClip(audio_path)
        duration = tts_audio.duration

        # Determinar si es Short basado en duración (máximo 60s para YouTube Shorts)
        # El usuario pidió 60-70s pero YouTube corta a los 60s para Shorts.
        is_short = duration <= 60.0
        
        # Forzar resolución 9:16 para Shorts (1080x1920) y 16:9 para largos (1920x1080)
        target_h = 1920 if is_short else 1080
        target_w = 1080 if is_short else 1920
        
        logger.info(f"Formato detectado: {'Short (9:16)' if is_short else 'Largo (16:9)'} - Duración: {duration:.2f}s")
        
        # 2. Preparar Clips Visuales
        clips = []
        current_time = 0
        for item in media_list:
            if not Path(item.get("path")).exists(): continue
            
            item_type = item.get("type")
            item_path = item.get("path")
            
            try:
                if item_type == "video":
                    clip = VideoFileClip(item_path, audio=False)
                else:
                    clip = ImageClip(item_path)
                
                # Ajustar duración y tamaño
                # Usar la duración estimada del segmento para el clip visual
                clip_duration = item.get("segment_duration", 5)
                # Redimensionar y centrar/recortar en un solo paso para eficiencia
                clip = clip.resize(height=target_h)
                if clip.w > target_w:
                    x_center = clip.w / 2
                    clip = clip.crop(x1=x_center - target_w / 2, y1=0, x2=x_center + target_w / 2, y2=target_h)
                elif clip.w < target_w:
                    # Si es más estrecho, lo centramos con márgenes negros
                    diff = target_w - clip.w
                    left = diff // 2
                    right = diff - left 
                    clip = clip.margin(left=left, right=right, color=(0,0,0))
                
                clip = clip.set_duration(clip_duration).set_start(current_time)
                clips.append(clip)
                current_time += clip_duration
                if current_time >= duration: break
            except Exception as e:
                logger.warning(f"Error procesando clip {item_path}: {e}")
                continue
            
        # Concatenar y ajustar a la duración del audio
        # method="chain" es más eficiente en memoria que "compose" para concatenaciones simples
        visual_base = concatenate_videoclips(clips, method="chain").set_duration(duration)
        
        # 3. Añadir Música de Fondo Aleatoria
        final_audio = tts_audio
        try:
            music_files = list(Path(music_dir).glob("*.mp3"))
            if music_files:
                bg_music_path = random.choice(music_files)
                logger.info(f"Añadiendo música de fondo: {bg_music_path.name}")
                bg_music = AudioFileClip(str(bg_music_path))
                
                # Ajustar volumen (ligeramente aumentado para que se escuche mejor sin opacar la voz)
                bg_music = bg_music.volumex(0.15)
                if bg_music.duration < duration:
                    bg_music = afx.audio_loop(bg_music, duration=duration)
                else:
                    bg_music = bg_music.set_duration(duration)
                
                # Mezclar audios
                from moviepy.audio.AudioClip import CompositeAudioClip
                final_audio = CompositeAudioClip([tts_audio, bg_music])
        except Exception as e:
            logger.error(f"Error al añadir música de fondo: {e}")

        # 4. Añadir Subtítulos Automáticos (MEJORA)
        # Dividimos el guion en frases cortas para los subtítulos
        full_script = script_data.get('full_script', '')
        subtitles = []
        
        # Lógica de sincronización: dividir el texto en fragmentos manejables
        import re
        # Dividir por puntos, comas o saltos de línea
        raw_sentences = re.split(r'[.,!?\n]', full_script)
        sentences = []
        for s in raw_sentences:
            s = s.strip()
            if not s: continue
            # Si la frase es muy larga (más de 60 caracteres), la dividimos para no saturar ImageMagick
            while len(s) > 60:
                split_idx = s[:60].rfind(' ')
                if split_idx == -1: split_idx = 60
                sentences.append(s[:split_idx].strip())
                s = s[split_idx:].strip()
            if s: sentences.append(s)

        if sentences:
            time_per_sentence = duration / len(sentences)
            for i, sentence in enumerate(sentences):
                try:
                    # Ajustamos el tamaño de fuente para asegurar legibilidad sin exceder límites
                    # MEJORA: Tamaño de subtítulos aumentado al doble (120 para Shorts, 80 para largos)
                    fs = 120 if is_short else 80
                    txt_clip = TextClip(
                        sentence, 
                        fontsize=fs, 
                        color='yellow', # Cambiado a amarillo para mayor contraste
                        font='Liberation-Sans-Bold',
                        stroke_color='black',
                        stroke_width=4, # Aumentado el borde para mayor legibilidad
                        method='caption',
                        size=(target_w * 0.9, None), # Aumentado el ancho del área de texto
                        align='center'
                    ).set_start(i * time_per_sentence).set_duration(time_per_sentence).set_position(('center', target_h * 0.75)) # Subido un poco para que no tape el borde inferior
                    subtitles.append(txt_clip)
                except Exception as e:
                    logger.warning(f"No se pudo crear subtítulo para '{sentence[:20]}...': {e}")

        # 5. Componer Video Final con Subtítulos
        final_video = CompositeVideoClip([visual_base] + subtitles).set_audio(final_audio)
        
        logger.info(f"Renderizando video final en {output_path}...")
        # threads=1 para procesamiento secuencial
        # bitrate="2000k" para limitar el flujo de datos y RAM
        # write_videofile puede consumir mucha RAM, por lo que cerramos clips después
        final_video.write_videofile(
            output_path, 
            fps=24, 
            codec="libx264", 
            audio_codec="aac", 
            logger=None, 
            preset="ultrafast", 
            threads=1,
            ffmpeg_params=["-crf", "28", "-tune", "stillimage"]
        )
        
        # Limpieza exhaustiva para liberar RAM
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
