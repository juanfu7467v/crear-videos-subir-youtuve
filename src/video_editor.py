import logging
import os
from pathlib import Path
from PIL import Image
# PARCHE: Esto obliga a que MoviePy encuentre la propiedad que busca
Image.ANTIALIAS = Image.Resampling.LANCZOS 

from moviepy.editor import VideoFileClip, ImageClip, AudioFileClip, concatenate_videoclips, ColorClip

logger = logging.getLogger(__name__)

class VideoEditor:
    def create_video(self, audio_path, media_list, script_data, format_type, output_path, music_dir="assets/music"):
        is_short = "short" in format_type.lower()
        target_h = 1920 if is_short else 1080
        
        tts_audio = AudioFileClip(audio_path)
        clips = []
        
        for item in media_list:
            if not Path(item.get("path")).exists(): continue
            clip = (VideoFileClip(item.get("path"), audio=False) if item.get("type") == "video" 
                    else ImageClip(item.get("path"))).resize(height=target_h).set_duration(3)
            clips.append(clip)
            
        final = concatenate_videoclips(clips).set_audio(tts_audio)
        final.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac", logger=None)
        final.close()
        tts_audio.close()
        return output_path
