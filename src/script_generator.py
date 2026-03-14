import json
import logging
import re
import requests
import os

logger = logging.getLogger(__name__)

class ScriptGenerator:
    def __init__(self, api_key: str):
        self.api_key = api_key.strip()
        # Usamos gemini-1.5-flash sin el prefijo 'models/' en la variable
        # para evitar confusiones en la construcción de la URL
        self.model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        # URL corregida: el prefijo 'models/' debe ir en la URL, no en el nombre del modelo
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"

    def generate_full_script(self, trend_data: dict) -> dict:
        topic = trend_data.get('topic', 'curiosidades interesantes')
        
        prompt = (
            f"Eres un experto creador de contenido para YouTube Shorts. "
            f"Tema del video: '{topic}'. "
            "Reglas estrictas: "
            "1. Escribe un guion completo y detallado para un video de 60 segundos. "
            "2. El guion debe iniciar con un 'Hook' impactante de 3 segundos para el canal 'El Tío Jota'. "
            "3. El contenido debe ser emocionante, educativo y viral. "
            "4. Responde ÚNICAMENTE en formato JSON plano (sin bloques de código markdown, sin texto extra). "
            "Estructura del JSON: { "
            "'title': 'Título llamativo', "
            "'full_script': 'Guion extenso y detallado para 60 segundos de narración', "
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
            
            response = requests.post(self.url, json=payload, timeout=60)
            
            if response.status_code != 200:
                logger.error(f"Error API {response.status_code}: {response.text}")
                return self._get_fallback(topic)

            data = response.json()
            text_response = data['candidates'][0]['content']['parts'][0]['text']
            
            # Limpieza profunda de formato
            cleaned_text = re.sub(r'^```json\s*|\s*```$', '', text_response.strip(), flags=re.MULTILINE)
            
            return json.loads(cleaned_text)
            
        except Exception as e:
            logger.error(f"Error crítico en la generación con Gemini: {e}")
            return self._get_fallback(topic)

    def _get_fallback(self, topic: str):
        """Estructura de respaldo detallada para evitar videos cortos."""
        return {
            "title": f"Lo que no sabías de {topic}", 
            "full_script": f"¡Detente! ¿Alguna vez te has preguntado sobre {topic}? En este video de El Tío Jota, vamos a desglosar los datos más alucinantes que cambiarán tu forma de ver este tema. Acompáñame en este recorrido rápido y lleno de información curiosa. No olvides suscribirte para más contenido fascinante cada día.", 
            "voice": "random", 
            "keywords": f"{topic}, viral, datos curiosos, historia", 
            "description": f"Descubre los secretos de {topic} con El Tío Jota. Un video corto pero lleno de información impactante.", 
            "tags": "curiosidades, viral, shorts, eltiojota, educativo"
        }
