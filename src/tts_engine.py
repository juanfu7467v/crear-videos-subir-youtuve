import asyncio
import logging
import os
import subprocess
from pathlib import Path
import edge_tts
import re

logger = logging.getLogger(__name__)

AVAILABLE_VOICES = {
    "mx_female": "es-MX-DaliaNeural",
    "mx_male":   "es-MX-JorgeNeural",
    "es_female": "es-ES-ElviraNeural",
    "es_male":   "es-ES-AlvaroNeural",
}

class TTSEngine:
    def __init__(self):
        self.default_voice = os.getenv("DEFAULT_VOICE", "es-MX-JorgeNeural")
        self.default_rate  = os.getenv("DEFAULT_SPEECH_RATE", "+10%")
        self.default_pitch = os.getenv("DEFAULT_PITCH", "+0Hz")

    def _get_valid_voice(self, voice_input: str) -> str:
        if voice_input in AVAILABLE_VOICES.values(): return voice_input
        return AVAILABLE_VOICES.get(voice_input, self.default_voice)

    def generate_audio(self, text: str, output_path: str, voice: str = None, rate: str = None, pitch: str = None) -> str:
        voice = self._get_valid_voice(voice or self.default_voice)
        rate  = rate  or self.default_rate
        pitch = pitch or self.default_pitch

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        text = self._clean_text(text)
        
        logger.info(f"Generando TTS con voz: {voice}")
        
        try:
            communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
            asyncio.run(communicate.save(output_path))
        except Exception as e:
            logger.error(f"Error en Edge-TTS: {e}")
            raise e
        return output_path

    def get_audio_duration(self, audio_path: str) -> float:
        """Recuperada para que el pipeline no falle."""
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", audio_path],
                capture_output=True, text=True
            )
            return float(result.stdout.strip())
        except:
            return 5.0 # Duración por defecto si falla ffprobe

    def _clean_text(self, text: str) -> str:
        text = re.sub(r'[^\w\s\.,!?¿¡\-:;áéíóúüñÁÉÍÓÚÜÑ\(\)\"\']+', ' ', text)
        return text.strip()[:8000]
