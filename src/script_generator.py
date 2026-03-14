import json
import logging
import re
import requests
import os

logger = logging.getLogger(__name__)

class ScriptGenerator:
    def __init__(self, api_key: str):
        self.api_key = api_key.strip()
        # Cambiado a gemini-1.5-flash por ser el estándar estable actual
        self.model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        self.url = f"{self.base_url}/{self.model}:generateContent?key={self.api_key}"

    def generate_full_script(self, trend_data: dict) -> dict:
        topic = trend_data.get('topic', 'curiosidades interesantes')
        
        # Prompt mejorado para forzar estructura y estabilidad
        prompt = (
            f"Eres un experto creador de contenido para YouTube Shorts. "
            f"Tema del video: '{topic}'. "
            "Reglas estrictas: "
            "1. El guion debe iniciar con un 'Hook' impactante de 3 segundos para el canal 'El Tío Jota'. "
            "2. El contenido debe ser emocionante, informativo y viral. "
            "3. Responde ÚNICAMENTE en formato JSON plano (sin bloques de código markdown, sin texto extra). "
            "Estructura del JSON: { "
            "'title': 'Título llamativo', "
            "'full_script': 'Guion completo del video', "
            "'keywords': 'palabras clave separadas por comas', "
            "'voice': 'random', "
            "'description': 'Descripción optimizada para YouTube', "
            "'tags': 'etiquetas separadas por comas' "
            "}"
        )
        
        try:
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "response_mime_type": "application/json",
                    "temperature": 0.7
                }
            }
            
            response = requests.post(self.url, json=payload, timeout=45)
            
            if response.status_code != 200:
                logger.error(f"Error API {response.status_code}: {response.text}")
                return self._get_fallback(topic)

            data = response.json()
            # Acceso seguro a la respuesta
            text_response = data['candidates'][0]['content']['parts'][0]['text']
            
            # Limpieza de cualquier residuo de formato markdown si existiera
            cleaned_text = re.sub(r'^```json\s*|\s*```$', '', text_response.strip(), flags=re.MULTILINE)
            
            return json.loads(cleaned_text)
            
        except Exception as e:
            logger.error(f"Error crítico en la generación con Gemini: {e}")
            return self._get_fallback(topic)

    def _get_fallback(self, topic: str):
        """Estructura de respaldo en caso de fallo técnico."""
        return {
            "title": f"Increíble: {topic}", 
            "full_script": f"¡No vas a creer esto sobre {topic}! Bienvenidos a El Tío Jota. Hoy analizamos por qué este tema está causando tanto revuelo.", 
            "voice": "random", 
            "keywords": f"{topic}, viral, datos curiosos", 
            "description": f"Explorando {topic} en El Tío Jota.", 
            "tags": "curiosidades, viral, shorts, eltiojota"
        }
