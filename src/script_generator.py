import json
import logging
import re
import requests

logger = logging.getLogger(__name__)

class ScriptGenerator:
    def __init__(self, api_key: str):
        self.api_key = api_key
        # Usamos gemini-1.5-flash-8b, es el más compatible con cuentas nuevas/gratuitas
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-8b:generateContent?key={self.api_key}"

    def generate_full_script(self, trend_data: dict) -> dict:
        prompt = f"Tema: {trend_data.get('topic')}. Responde SOLO un JSON con: title, full_script, keywords, voice, description, tags."
        
        try:
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            response = requests.post(self.url, json=payload, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"Error API {response.status_code}: {response.text}")
                # Fallback para no detener el bot
                return {"title": "Misterios", "full_script": "Descubre los misterios.", "voice": "mx_male", "keywords": "misterio", "description": "...", "tags": "..."}

            data = response.json()
            text_response = data['candidates'][0]['content']['parts'][0]['text']
            raw = re.search(r'\{.*\}', text_response, re.DOTALL).group(0)
            return json.loads(raw)
            
        except Exception as e:
            logger.error(f"Error en Gemini: {e}")
            return {"title": "Error", "full_script": "Error al generar", "voice": "mx_male", "keywords": "", "description": "", "tags": ""}
