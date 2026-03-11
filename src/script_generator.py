import json
import logging
import os
import re
import requests

logger = logging.getLogger(__name__)

class ScriptGenerator:
    def __init__(self, api_key: str):
        self.api_key = api_key
        # Usamos gemini-1.5-flash, es el modelo más estable y garantizado
        self.model_name = "gemini-1.5-flash"
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"

    def generate_full_script(self, trend_data: dict) -> dict:
        topic = trend_data.get('topic', 'curiosidades')
        prompt = (
            f"Actúa como un experto en YouTube. Escribe un guion corto para un video sobre: {topic}. "
            "Responde estrictamente en formato JSON válido. "
            "El JSON debe tener exactamente estos campos: "
            "{'title': '...', 'full_script': '...', 'keywords': '...', 'voice': 'es-MX-JorgeNeural', 'description': '...', 'tags': '...'}. "
            "No incluyas explicaciones, solo el JSON puro."
        )
        
        if not self.api_key:
            return {"title": "Error", "full_script": "No API Key", "voice": "es-MX-JorgeNeural"}

        try:
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.7}
            }
            headers = {'Content-Type': 'application/json'}
            
            response = requests.post(self.url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if 'candidates' in data:
                text_response = data['candidates'][0]['content']['parts'][0]['text']
                # Limpieza robusta del JSON
                json_match = re.search(r'\{.*\}', text_response, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(0))
                else:
                    return json.loads(text_response)
            
            raise ValueError("Respuesta vacía de Gemini")

        except Exception as e:
            logger.error(f"Error crítico en Gemini API: {e}")
            # Retorno de emergencia para que el pipeline no se rompa
            return {
                "title": "Misterios", 
                "full_script": "Bienvenidos a este nuevo video de misterios.", 
                "voice": "es-MX-JorgeNeural",
                "keywords": "misterio, océano",
                "description": "Video sobre misterios.",
                "tags": "misterio, shorts"
            }
