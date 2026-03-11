import json
import logging
import os
import re
import requests

logger = logging.getLogger(__name__)

class ScriptGenerator:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-preview-09-2025:generateContent?key={self.api_key}"

    def generate_full_script(self, trend_data: dict) -> dict:
        prompt = f"Tema: {trend_data.get('topic')}. Responde solo JSON con campos: title, full_script, keywords, voice, description, tags."
        
        if not self.api_key:
            return {"title": "Demo", "full_script": "Hola", "voice": "es-MX-DaliaNeural"}

        try:
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt}
                        ]
                    }
                ]
            }
            headers = {'Content-Type': 'application/json'}
            
            response = requests.post(self.url, headers=headers, json=payload)
            response.raise_for_status()
            
            data = response.json()
            
            # Extraer el texto de la respuesta de Gemini
            if 'candidates' in data and len(data['candidates']) > 0:
                text_response = data['candidates'][0]['content']['parts'][0]['text']
                raw = re.sub(r'```json\s*|\s*```', '', text_response.strip())
                return json.loads(raw)
            else:
                logger.error(f"Respuesta inesperada de Gemini: {data}")
                raise ValueError("No se encontró contenido en la respuesta de Gemini")

        except Exception as e:
            logger.error(f"Error en Gemini API: {e}")
            return {"title": "Error", "full_script": "Error al generar", "voice": "es-MX-DaliaNeural"}
