import json
import logging
import re
import requests
import os

logger = logging.getLogger(__name__)

class ScriptGenerator:
    def __init__(self, api_key: str):
        self.api_key = api_key.strip()
        self.model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self.url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )

    def generate_full_script(self, trend_data: dict) -> dict:
        topic = trend_data.get('topic', 'curiosidades')
        
        # MEJORA: Instrucción explícita para el Hook de 3 segundos
        prompt = (
            f"Tema: {topic}. Genera un guion para un video de YouTube Short. "
            "IMPORTANTE: El guion DEBE comenzar con un 'Hook' (gancho) impactante de aproximadamente 3 segundos "
            "que llame la atención del espectador de inmediato para el canal 'El Tío Jota'. "
            "Responde SOLO un JSON sin formato markdown, con estos campos: "
            "'title', 'full_script', 'keywords', 'voice', 'description', 'tags'. "
            "En el campo 'voice', pon siempre 'random'."
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
            text_response = data['candidates'][0]['content']['parts'][0]['text']
            
            raw = re.search(r'\{.*\}', text_response, re.DOTALL)
            if raw:
                return json.loads(raw.group(0))
            return json.loads(text_response)
            
        except Exception as e:
            logger.error(f"Error crítico en la generación con Gemini: {e}")
            return self._get_fallback()

    def _get_fallback(self):
        """Devuelve una estructura válida si la API falla para no romper el pipeline."""
        return {
            "title": "Misterios Increíbles", 
            "full_script": "¡Detente! ¿Sabías que lo que estás a punto de ver cambiará tu forma de pensar? Bienvenidos a El Tío Jota, hoy exploramos un tema fascinante.", 
            "voice": "random", 
            "keywords": "misterio, viral, curiosidades", 
            "description": "Explorando misterios con El Tío Jota.", 
            "tags": "misterio, viral, curiosidades, shorts"
        }
