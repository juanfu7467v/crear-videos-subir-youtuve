import os
import random
import requests
from moviepy.editor import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, ColorClip
from edge_tts import Communicate
import asyncio

def generate_video(data):
    title = data.get('title', 'Sin título')
    topic = data.get('topic', 'General')
    
    # 1. Generate script (Mockup)
    script = f"Este es un video sobre {topic}. {title} es un tema fascinante."
    
    # 2. Generate audio with Edge-TTS
    audio_path = "temp_audio.mp3"
    communicate = Communicate(script, "es-ES-AlvaroNeural")
    asyncio.run(communicate.save(audio_path))
    
    # 3. Assemble video (Mockup simple)
    audio = AudioFileClip(audio_path)
    clip = ColorClip(size=(1080, 1920), color=(0,0,0), duration=audio.duration)
    clip = clip.set_audio(audio)
    output_path = "output_video.mp4"
    clip.write_videofile(output_path, fps=24)
    return output_path
