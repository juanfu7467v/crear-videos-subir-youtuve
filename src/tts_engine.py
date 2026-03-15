import asyncio
import logging
import os
import subprocess
import random
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
        # Si se solicita 'random', elegir una al azar
        if voice_input == "random":
            selected = random.choice(self.voices_list)
            logger.info(f"Voz aleatoria seleccionada: {selected}")
            return selected
            
        if voice_input in self.voices_list: return voice_input
        if voice_input in AVAILABLE_VOICES.values(): return voice_input
        
        mapped = AVAILABLE_VOICES.get(voice_input)
        if mapped: return mapped
        
        return self.default_voice

    def generate_audio(self, text: str, output_path: str, voice: str = None, rate: str = None, pitch: str = None) -> str:
        # Si no viene voz, o viene algo no reconocido, podemos forzar aleatoriedad si así se desea
        # Pero para mantener compatibilidad, si viene None usamos el default o random si así se configura
        voice = self._get_valid_voice(voice or "random")
        rate  = rate  or self.default_rate
        pitch = pitch or self.default_pitch

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        text = self._clean_text(text)
        # Limitar la longitud del texto para evitar errores de Edge-TTS con textos muy largos
        text = text[:8000]
        
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
        # Eliminar estructuras JSON si se colaron (ej: {"full_script": "..."})
        if text.startswith('{') and '}' in text:
            try:
                import json
                data = json.loads(text)
                if isinstance(data, dict):
                    text = data.get('full_script', text)
            except:
                pass
                
        # Eliminar etiquetas de formato markdown como **texto** o __texto__
        text = re.sub(r'\*\*|__', '', text)
        
        # Eliminar comillas dobles y simples que suelen venir del JSON
        text = text.replace('"', '').replace("'", "")
        
        # Eliminar guiones que se usan para listas pero se leen como "guion"
        # Solo si están al inicio de una línea o seguidos de espacio
        text = re.sub(r'(^|\s)-\s+', r'\1 ', text)
        
        # Eliminar otros símbolos problemáticos que no sean puntuación básica
        text = re.sub(r'[{|\\\\\[\]<>]', ' ', text)
        
        # Eliminar números si no están asociados a texto (ej: "cero trece" vs "13")
        # Esto es más complejo y podría requerir un enfoque más inteligente.
        # Por ahora, nos enfocamos en los símbolos y comillas.
        
        # Normalizar espacios
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
