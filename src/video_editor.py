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
    CompositeVideoClip, afx
)

logger = logging.getLogger(__name__)

class VideoEditor:
    def __init__(self):
        logger.info("Inicializando VideoEditor...")

    def create_video(self, audio_path, media_list, script_data, format_type, output_path, music_dir="assets/music"):
        is_short = "short" in format_type.lower()
        target_h = 1920 if is_short else 1080
        target_w = 1080 if is_short else 1920
        
        # 1. Cargar Audio Principal (TTS)
        tts_audio = AudioFileClip(audio_path)
        duration = tts_audio.duration
        
        # 2. Preparar Clips Visuales
        clips = []
        current_time = 0
        for item in media_list:
            if not Path(item.get("path")).exists(): continue
            
            item_type = item.get("type")
            item_path = item.get("path")
            
            if item_type == "video":
                clip = VideoFileClip(item_path, audio=False)
            else:
                clip = ImageClip(item_path)
            
            # Ajustar duración y tamaño
            clip_duration = 5 if item_type == "image" else clip.duration
            clip = clip.resize(height=target_h)
            
            # Centrar si es más ancho que el objetivo
            if clip.w > target_w:
                clip = clip.margin(left=-(clip.w - target_w)//2, right=-(clip.w - target_w)//2)
            
            clip = clip.set_duration(clip_duration).set_start(current_time)
            clips.append(clip)
            current_time += clip_duration
            if current_time >= duration: break
            
        # Concatenar y ajustar a la duración del audio
        visual_base = concatenate_videoclips(clips, method="compose").set_duration(duration)
        
        # 3. Añadir Música de Fondo Aleatoria
        final_audio = tts_audio
        try:
            music_files = list(Path(music_dir).glob("*.mp3"))
            if music_files:
                bg_music_path = random.choice(music_files)
                logger.info(f"Añadiendo música de fondo: {bg_music_path.name}")
                bg_music = AudioFileClip(str(bg_music_path))
                
                # Ajustar volumen (bajo para no interferir) y loopear si es necesario
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

        # 4. Componer Video Final (Sin subtítulos)
        final_video = CompositeVideoClip([visual_base]).set_audio(final_audio)
        
        logger.info(f"Renderizando video final en {output_path}...")
        final_video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac", logger=None)
        
        # Limpieza
        final_video.close()
        tts_audio.close()
        if 'bg_music' in locals(): bg_music.close()
        
        return output_path
