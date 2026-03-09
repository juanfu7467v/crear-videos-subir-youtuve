"""
tts_engine.py
──────────────
Motor de Text-to-Speech usando Edge-TTS (voces de Microsoft).
Completamente GRATUITO, sin límites de uso.
"""

import asyncio
import logging
import os
import subprocess
from pathlib import Path
import edge_tts

logger = logging.getLogger(__name__)


# Voces disponibles en español
AVAILABLE_VOICES = {
    "mx_female": "es-MX-DaliaNeural",
    "mx_male":   "es-MX-JorgeNeural",
    "es_female": "es-ES-ElviraNeural",
    "es_male":   "es-ES-AlvaroNeural",
    "ar_female": "es-AR-ElenaNeural",
    "ar_male":   "es-AR-TomasNeural",
    "co_female": "es-CO-SalomeNeural",
    "co_male":   "es-CO-GonzaloNeural",
    "cl_female": "es-CL-CatalinaNeural",
    "cl_male":   "es-CL-LorenzoNeural",
    "pe_female": "es-PE-CamilaNeural",
    "pe_male":   "es-PE-AlexNeural",
    "ve_female": "es-VE-PaolaNeural",
    "ve_male":   "es-VE-SebastianNeural",
}


class TTSEngine:
    """
    Motor TTS basado en Edge-TTS de Microsoft.
    Soporta múltiples voces en español, control de velocidad y tono.
    """

    def __init__(self):
        self.default_voice = os.getenv("DEFAULT_VOICE", "es-MX-DaliaNeural")
        self.default_rate  = os.getenv("DEFAULT_SPEECH_RATE", "+10%")
        self.default_pitch = os.getenv("DEFAULT_PITCH", "+0Hz")

    def generate_audio(
        self,
        text: str,
        output_path: str,
        voice: str = None,
        rate: str = None,
        pitch: str = None,
    ) -> str:
        """
        Genera audio MP3 a partir de texto.

        Args:
            text: Texto a convertir en voz
            output_path: Ruta donde guardar el MP3
            voice: Voz de Edge-TTS (ej: "es-MX-DaliaNeural")
            rate: Velocidad (ej: "+10%", "-5%", "+0%")
            pitch: Tono (ej: "+5Hz", "-5Hz")

        Returns:
            Path al archivo de audio generado
        """
        voice = voice or self.default_voice
        rate  = rate  or self.default_rate
        pitch = pitch or self.default_pitch

        # Asegurar que el directorio existe
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # Limpiar texto para TTS
        text = self._clean_text(text)
        if not text:
            raise ValueError("El texto está vacío después de la limpieza")

        logger.info(f"Generando TTS con voz: {voice}")
        logger.info(f"Velocidad: {rate} | Tono: {pitch}")
        logger.info(f"Texto ({len(text)} chars): {text[:100]}...")

        # Ejecutar en loop asyncio
        try:
            asyncio.run(self._async_generate(text, output_path, voice, rate, pitch))
        except RuntimeError:
            # En caso de que ya haya un loop corriendo
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                self._async_generate(text, output_path, voice, rate, pitch)
            )
            loop.close()

        # Verificar que se generó el archivo
        if not Path(output_path).exists():
            raise FileNotFoundError(f"No se generó el audio en: {output_path}")

        size_kb = Path(output_path).stat().st_size / 1024
        logger.info(f"Audio generado: {output_path} ({size_kb:.1f} KB)")
        return output_path

    async def _async_generate(
        self, text: str, output_path: str, voice: str, rate: str, pitch: str
    ):
        """Generación asíncrona de Edge-TTS."""
        communicate = edge_tts.Communicate(
            text=text,
            voice=voice,
            rate=rate,
            pitch=pitch,
        )
        await communicate.save(output_path)

    def generate_with_subtitles(
        self,
        text: str,
        audio_path: str,
        subtitle_path: str,
        voice: str = None,
        rate: str = None,
    ) -> tuple:
        """
        Genera audio Y archivo de subtítulos VTT/SRT.
        Útil para añadir subtítulos automáticos al video.

        Returns:
            (audio_path, subtitle_path)
        """
        voice = voice or self.default_voice
        rate  = rate  or self.default_rate

        text = self._clean_text(text)
        Path(audio_path).parent.mkdir(parents=True, exist_ok=True)
        Path(subtitle_path).parent.mkdir(parents=True, exist_ok=True)

        try:
            asyncio.run(
                self._async_generate_with_subs(text, audio_path, subtitle_path, voice, rate)
            )
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                self._async_generate_with_subs(text, audio_path, subtitle_path, voice, rate)
            )
            loop.close()

        return audio_path, subtitle_path

    async def _async_generate_with_subs(
        self, text: str, audio_path: str, subtitle_path: str, voice: str, rate: str
    ):
        """Genera audio y subtítulos asíncronamente."""
        communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate)

        subs = edge_tts.SubMaker()
        audio_chunks = []

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                subs.create_sub(
                    (chunk["offset"], chunk["duration"]),
                    chunk["text"]
                )

        # Guardar audio
        with open(audio_path, "wb") as f:
            for chunk in audio_chunks:
                f.write(chunk)

        # Guardar subtítulos VTT
        with open(subtitle_path, "w", encoding="utf-8") as f:
            f.write(subs.generate_subs(words_in_cue=6))

        logger.info(f"Audio: {audio_path} | Subs: {subtitle_path}")

    def convert_to_wav(self, mp3_path: str, wav_path: str) -> str:
        """Convierte MP3 a WAV usando ffmpeg (necesario para MoviePy a veces)."""
        try:
            cmd = [
                "ffmpeg", "-y", "-i", mp3_path,
                "-ar", "44100", "-ac", "2", wav_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.warning(f"ffmpeg warning: {result.stderr[:200]}")
            return wav_path
        except FileNotFoundError:
            logger.error("ffmpeg no encontrado. Instalar con: apt-get install ffmpeg")
            return mp3_path

    def get_audio_duration(self, audio_path: str) -> float:
        """Retorna la duración en segundos del archivo de audio."""
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "csv=p=0", audio_path],
                capture_output=True, text=True
            )
            return float(result.stdout.strip())
        except Exception as e:
            logger.error(f"Error obteniendo duración de audio: {e}")
            return 0.0

    def list_voices(self) -> dict:
        """Retorna el diccionario de voces disponibles."""
        return AVAILABLE_VOICES

    def _clean_text(self, text: str) -> str:
        """Limpia el texto para mejor pronunciación en TTS."""
        import re
        # Eliminar emojis
        text = re.sub(r'[^\w\s\.,!?¿¡\-:;áéíóúüñÁÉÍÓÚÜÑ\(\)\"\']+', ' ', text)
        # Normalizar espacios
        text = re.sub(r'\s+', ' ', text)
        # Cortar si es muy largo (Edge-TTS tiene límite)
        max_chars = 8000
        if len(text) > max_chars:
            logger.warning(f"Texto truncado de {len(text)} a {max_chars} chars")
            text = text[:max_chars].rsplit('.', 1)[0] + '.'
        return text.strip()


# ─── Test rápido ──────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    tts = TTSEngine()

    test_text = (
        "¿Sabías que el 90% de las personas no conoce este dato increíble? "
        "Hoy en El Tío Jota te contamos todo. "
        "Quédate hasta el final porque lo mejor está por venir."
    )

    tts.generate_audio(
        text=test_text,
        output_path="/tmp/test_tts.mp3",
        voice="es-MX-DaliaNeural",
        rate="+10%",
    )
    print("✅ TTS generado en /tmp/test_tts.mp3")
