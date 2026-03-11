import asyncio
import logging
import os
import subprocess
from pathlib import Path
import edge_tts

logger = logging.getLogger(__name__)

# Diccionario de voces válidas
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
        """Valida que la voz exista, si no, devuelve la por defecto."""
        # Si es una descripción (ej: 'Narrador masculino...'), devolver por defecto
        if voice_input not in AVAILABLE_VOICES.values() and voice_input not in AVAILABLE_VOICES.keys():
            logger.warning(f"Voz inválida recibida: '{voice_input}'. Usando por defecto: {self.default_voice}")
            return self.default_voice
        
        # Si es un alias (ej: 'mx_male'), devolver ID técnico
        return AVAILABLE_VOICES.get(voice_input, voice_input)

    def generate_audio(self, text: str, output_path: str, voice: str = None, rate: str = None, pitch: str = None) -> str:
        voice = self._get_valid_voice(voice or self.default_voice)
        rate  = rate  or self.default_rate
        pitch = pitch or self.default_pitch

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        text = self._clean_text(text)
        
        logger.info(f"Generando TTS con voz técnica: {voice}")
        
        try:
            # Corregido: usamos la librería edge_tts correctamente
            communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
            asyncio.run(communicate.save(output_path))
        except Exception as e:
            logger.error(f"Error en Edge-TTS: {e}")
            raise e

        if not Path(output_path).exists():
            raise FileNotFoundError(f"No se generó el audio.")
        return output_path

    def _clean_text(self, text: str) -> str:
        import re
        text = re.sub(r'[^\w\s\.,!?¿¡\-:;áéíóúüñÁÉÍÓÚÜÑ\(\)\"\']+', ' ', text)
        return text.strip()[:8000]
