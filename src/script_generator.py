import json
import logging
import re
import requests
import os

logger = logging.getLogger(__name__)

class ScriptGenerator:
    def __init__(self, api_key: str):
        self.api_key = api_key
        # Configuración extraída de tu proyecto funcional
        self.model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"

    def generate_full_script(self, trend_data: dict) -> dict:
        topic = trend_data.get('topic', 'curiosidades')
        prompt = (
            f"Tema: {topic}. Responde SOLO un JSON sin formato markdown, "
            "con estos campos obligatorios: 'title', 'full_script', 'keywords', 'voice', 'description', 'tags'."
        )
        
        try:
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"response_mime_type": "application/json"}
            }
            
            response = requests.post(self.url, json=payload, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"Error API {response.status_code}: {response.text}")
                return self._get_fallback()

            data = response.json()
            # Acceso seguro a la respuesta
            text_response = data['candidates'][0]['content']['parts'][0]['text']
            
            # Limpieza para asegurar que sea un JSON válido
            raw = re.search(r'\{.*\}', text_response, re.DOTALL)
            if raw:
                return json.loads(raw.group(0))
            return json.loads(text_response)
            
        except Exception as e:
            logger.error(f"Error crítico en Gemini: {e}")
            return self._get_fallback()

    def _get_fallback(self):
        return {
            "title": "Curiosidades", 
            "full_script": "Bienvenidos al canal, hoy exploraremos algo fascinante.", 
            "voice": "es-MX-JorgeNeural", 
            "keywords": "curiosidades, viral", 
            "description": "Video fascinante.", 
            "tags": "curiosidades"
        }
