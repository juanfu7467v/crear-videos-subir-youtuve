import asyncio
import logging
import os
import subprocess
import random
import json
from pathlib import Path
import edge_tts
import re

logger = logging.getLogger(__name__)

AVAILABLE_VOICES = {
    "mx_female": "es-MX-DaliaNeural",
    "mx_male":   "es-MX-JorgeNeural",
    "mx_male_2": "es-MX-EmilioNeural",
}

class TTSEngine:
    def __init__(self):
        self.default_voice = os.getenv("DEFAULT_VOICE", "es-MX-JorgeNeural")
        self.default_rate  = os.getenv("DEFAULT_SPEECH_RATE", "+10%")
        self.default_pitch = os.getenv("DEFAULT_PITCH", "+0Hz")
        self.voices_list = ["es-MX-DaliaNeural", "es-MX-EmilioNeural", "es-MX-JorgeNeural"]

    def _get_valid_voice(self, voice_input: str) -> str:
        if voice_input == "random":
            return random.choice(self.voices_list)
        if voice_input in self.voices_list: return voice_input
        if voice_input in AVAILABLE_VOICES.values(): return voice_input
        mapped = AVAILABLE_VOICES.get(voice_input)
        if mapped: return mapped
        return self.default_voice

    async def _generate_with_timestamps(self, text: str, voice: str, output_path: str, rate: str, pitch: str):
        communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
        submaker = edge_tts.SubMaker()
        
        # Guardar audio
        await communicate.save(output_path)
        
        # Generar timestamps
        with open(output_path.replace(".mp3", ".json"), "w", encoding="utf-8") as f:
            word_timestamps = []
            async for chunk in communicate.stream():
                if chunk["type"] == "WordBoundary":
                    word_timestamps.append({
                        "word": chunk["text"],
                        "start": chunk["offset"] / 10**7, # Convertir a segundos
                        "duration": chunk["duration"] / 10**7
                    })
            json.dump(word_timestamps, f, ensure_ascii=False, indent=2)

    def generate_audio(self, text: str, output_path: str, voice: str = None, rate: str = None, pitch: str = None) -> str:
        voice = self._get_valid_voice(voice or "random")
        rate  = rate  or self.default_rate
        pitch = pitch or self.default_pitch

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        text = self._clean_text(text)
        text = text[:8000]
        
        logger.info(f"Generando TTS con timestamps para voz: {voice}")
        
        try:
            asyncio.run(self._generate_with_timestamps(text, voice, output_path, rate, pitch))
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                return output_path
        except Exception as e:
            logger.error(f"Error en Edge-TTS con timestamps: {e}")
            # Fallback simple si falla el sistema de timestamps
            communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
            asyncio.run(communicate.save(output_path))
            
        return output_path

    def get_audio_duration(self, audio_path: str) -> float:
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", audio_path],
                capture_output=True, text=True
            )
            return float(result.stdout.strip())
        except:
            return 5.0

    def _clean_text(self, text: str) -> str:
        if text.startswith('{') and '}' in text:
            try:
                data = json.loads(text)
                if isinstance(data, dict):
                    text = data.get('full_script', text)
            except: pass
        text = re.sub(r'\*\*|__', '', text)
        text = re.sub(r'#+\s+', '', text)
        text = text.replace('"', '').replace("'", "").replace('\\n', ' ').replace('\\', '')
        text = text.replace('_', ' ')
        text = re.sub(r'[-—–]', ' ', text)
        text = re.sub(r'[{|\[\]<>/@#$%^&*+=~]', ' ', text)
        text = text.replace('...', '.')
        text = re.sub(r'\s+([,.?!])', r'\1', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
