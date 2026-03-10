import logging
import os
import random
import numpy as np
from pathlib import Path
from moviepy.editor import (
    VideoFileClip, ImageClip, AudioFileClip, CompositeAudioClip,
    concatenate_videoclips, CompositeVideoClip, ColorClip
)

logger = logging.getLogger(__name__)

class VideoEditor:
    def __init__(self):
        self.default_resolution = (1080, 1920)
        self.long_resolution = (1920, 1080)
        self.fps = 30
        self.bg_music_volume = float(os.getenv("BG_MUSIC_VOLUME", "0.08"))

    def create_video(self, audio_path, media_list, script_data, format_type, output_path, music_dir="assets/music"):
        is_short = "short" in format_type.lower()
        target_w, target_h = self.default_resolution if is_short else self.long_resolution
        
        tts_audio = AudioFileClip(audio_path)
        total_duration = tts_audio.duration

        video_clips = self._prepare_video_clips(media_list, total_duration, target_h)
        
        if not video_clips:
            video_clips = [ColorClip(size=(target_w, target_h), color=(10, 10, 30), duration=total_duration)]

        # Composición principal
        main_video = concatenate_videoclips(video_clips, method="compose").set_duration(total_duration)
        
        # Audio con música de fondo
        bg_music = self._get_background_music(music_dir, total_duration)
        if bg_music:
            final_audio = CompositeAudioClip([tts_audio, bg_music.volumex(self.bg_music_volume)])
        else:
            final_audio = tts_audio

        final_video = main_video.set_audio(final_audio)
        
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        final_video.write_videofile(output_path, fps=self.fps, codec="libx264", audio_codec="aac", logger=None)
        
        final_video.close()
        tts_audio.close()
        return output_path

    def _prepare_video_clips(self, media_list, total_duration, target_h):
        clips = []
        clip_duration = max(3, total_duration / max(len(media_list), 1))
        for item in media_list:
            path = item.get("path")
            if not Path(path).exists(): continue
            
            # Ajuste de tamaño usando la versión estable de Pillow
            if item.get("type") == "video":
                clip = VideoFileClip(path, audio=False).resize(height=target_h)
            else:
                clip = ImageClip(path).set_duration(clip_duration).resize(height=target_h)
            
            clips.append(clip.set_duration(clip_duration))
        return clips

    def _get_background_music(self, music_dir, duration):
        music_path = Path(music_dir)
        if not music_path.exists(): return None
        files = list(music_path.glob("*.mp3"))
        if not files: return None
        music = AudioFileClip(str(random.choice(files)))
        return music.subclip(0, min(duration, music.duration))
