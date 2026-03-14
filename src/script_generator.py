import json
import logging
import re
import requests
import os

logger = logging.getLogger(__name__)

class ScriptGenerator:
    def __init__(self, api_key: str):
        self.api_key = api_key.strip()
        # Cambiamos a la forma 'models/gemini-1.5-flash' que es el identificador oficial 
        # que evita el error 404 de "not found" en v1beta
        self.model = os.getenv("GEMINI_MODEL", "models/gemini-1.5-flash")
        
        # La URL correcta para el endpoint generativo es esta:
        self.url = f"https://generativelanguage.googleapis.com/v1beta/{self.model}:generateContent?key={self.api_key}"

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
            
            # Si el código no es 200, logueamos el error y devolvemos fallback
            if response.status_code != 200:
                logger.error(f"Error API {response.status_code}: {response.text}")
                return self._get_fallback(topic)

            data = response.json()
            
            # Verificación de que la respuesta tenga contenido
            if 'candidates' not in data or not data['candidates']:
                raise ValueError("La API no devolvió candidatos.")
                
            text_response = data['candidates'][0]['content']['parts'][0]['text']
            
            # Limpieza profunda de formato markdown si existiera
            cleaned_text = re.sub(r'^```json\s*|\s*```$', '', text_response.strip(), flags=re.MULTILINE)
            
            return json.loads(cleaned_text)
            
        except Exception as e:
            logger.error(f"Error crítico en la generación con Gemini: {e}")
            return self._get_fallback(topic)

    def _get_fallback(self, topic: str):
        """Estructura de respaldo detallada para evitar videos cortos si la API falla."""
        return {
            "title": f"Increíble: {topic}", 
            "full_script": f"¡Detente! ¿Alguna vez te has preguntado sobre {topic}? En este video de El Tío Jota, vamos a explorar los datos más sorprendentes y menos conocidos. Prepárate porque esto te volará la cabeza. Si te gustan los datos curiosos, suscríbete ahora para no perderte ningún video. ¡Vamos allá!", 
            "voice": "random", 
            "keywords": f"{topic}, viral, datos curiosos, historia", 
            "description": f"Descubre los secretos de {topic} con El Tío Jota. Datos increíbles que no conocías.", 
            "tags": "curiosidades, viral, shorts, eltiojota, educativo"
        }
