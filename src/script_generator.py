import json
import logging
import os
import re
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

class ScriptGenerator:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = genai.Client(api_key=self.api_key) if api_key else None

    def generate_full_script(self, trend_data: dict) -> dict:
        prompt = f"Tema: {trend_data.get('topic')}. Responde solo JSON con campos: title, full_script, keywords, voice, description, tags."
        
        if not self.client:
            return {"title": "Demo", "full_script": "Hola", "voice": "es-MX-DaliaNeural"}

        try:
            # Llamada corregida y simplificada para la librería google-genai
            response = self.client.models.generate_content(
                model="gemini-1.5-flash",
                contents=prompt
            )
            raw = re.sub(r'```json\s*|\s*```', '', response.text.strip())
            return json.loads(raw)
        except Exception as e:
            logger.error(f"Error en Gemini: {e}")
            return {"title": "Error", "full_script": "Error al generar", "voice": "es-MX-DaliaNeural"}
