"""
script_generator.py
────────────────────
Genera guiones completos usando la NUEVA librería google-genai.
"""

import json
import logging
import os
import re
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

SHORT_SCRIPT_PROMPT = """
Eres un guionista experto en YouTube Shorts virales en español.
Tema del video: {topic}
Idea: {idea}
Hook sugerido: {hook_idea}
Canal: {channel}
Audiencia: {audience}

Responde ÚNICAMENTE con JSON válido:
{{
  "title": "título",
  "hook": "texto hook",
  "full_script": "guion completo",
  "segments": [],
  "keywords": ["p1", "p2"],
  "visual_suggestions": ["v1"],
  "voice": "es-MX-DaliaNeural",
  "speech_rate": "+15%",
  "description": "desc",
  "tags": ["t1"],
  "estimated_duration_seconds": 55
}}
"""

LONG_SCRIPT_PROMPT = """
Eres un guionista experto en videos largos de YouTube en español.
Tema del video: {topic}
Idea: {idea}
Canal: {channel}

Responde ÚNICAMENTE con JSON válido.
"""

class ScriptGenerator:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.channel = os.getenv("CHANNEL_NAME", "El Tío Jota")
        self.default_voice = os.getenv("DEFAULT_VOICE", "es-MX-DaliaNeural")
        self.client = None
        self._configure_gemini()

    def _configure_gemini(self):
        if self.api_key:
            # NUEVA FORMA: Se crea un cliente
            try:
                self.client = genai.Client(api_key=self.api_key)
                logger.info("✅ Cliente Gemini (google-genai) configurado correctamente.")
            except Exception as e:
                logger.error(f"❌ Error al configurar el cliente: {e}")
                self.client = None
        else:
            self.client = None
            logger.warning("⚠️ Sin API Gemini. Usando guión de demo.")

    def generate_full_script(self, trend_data: dict) -> dict:
        fmt = trend_data.get("format", "Short").lower()
        is_short = "short" in fmt
        prompt_template = SHORT_SCRIPT_PROMPT if is_short else LONG_SCRIPT_PROMPT
        
        prompt = prompt_template.format(
            topic=trend_data.get("topic", "curiosidades"),
            idea=trend_data.get("idea", ""),
            hook_idea=trend_data.get("hook_idea", ""),
            channel=self.channel,
            audience=trend_data.get("target_audience", "público general"),
        )

        if not self.client:
            return self._get_demo_script(trend_data, is_short)

        try:
            logger.info(f"Generando guion {'Short' if is_short else 'Long'}...")
            # NUEVA FORMA: Llamada al modelo con el cliente
            response = self.client.models.generate_content(
                model="gemini-1.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.85,
                    max_output_tokens=4096,
                ),
            )
            
            raw = response.text.strip()
            # Limpiar markdown si el modelo lo incluye
            raw = re.sub(r'```json\s*|\s*```', '', raw)
            
            script_data = json.loads(raw)
            
            if "voice" not in script_data:
                script_data["voice"] = self.default_voice
            
            return script_data

        except Exception as e:
            logger.error(f"❌ Error generando guion: {e}")
            return self._get_demo_script(trend_data, is_short)

    def clean_script_for_tts(self, script: str) -> str:
        script = re.sub(r'[^\w\s\.,!?¿¡\-:;áéíóúüñÁÉÍÓÚÜÑ]', '', script)
        script = re.sub(r'\s+', ' ', script).strip()
        return script

    def _get_demo_script(self, trend_data: dict, is_short: bool) -> dict:
        return {
            "title": "Demo Script",
            "hook": "Esto es un video de prueba.",
            "full_script": "Contenido de prueba para el sistema.",
            "segments": [],
            "keywords": ["demo"],
            "visual_suggestions": [],
            "voice": self.default_voice,
            "speech_rate": "+10%",
            "description": "Video generado automáticamente.",
            "tags": ["demo"],
            "estimated_duration_seconds": 60 if is_short else 600,
        }
