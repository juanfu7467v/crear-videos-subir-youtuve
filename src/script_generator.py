import json
import logging
import requests
import os

logger = logging.getLogger(__name__)

class ScriptGenerator:
    def __init__(self, api_key: str):
        self.api_key = api_key.strip()
        # Usamos la versión estable sin v1beta
        self.model = "gemini-1.5-flash"
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"

    def generate_full_script(self, trend_data: dict) -> dict:
        topic = trend_data.get('topic', 'curiosidades')
        
        # Prompt optimizado para ser directo
        prompt = (
            f"Tema: {topic}. Genera un guion para un YouTube Short de 60 segundos sobre '{topic}' para el canal 'El Tío Jota'. "
            "El guion debe ser cautivador, educativo y divertido. "
            "DEBES responder EXCLUSIVAMENTE con un objeto JSON (sin markdown, sin bloques de código, sin texto adicional). "
            "Estructura obligatoria: "
            "{ 'title': 'titulo', 'full_script': 'guion detallado de 150 palabras', 'keywords': 'tag1, tag2', 'voice': 'random', 'description': 'desc', 'tags': 'tag1, tag2' }"
        )
        
        payload = {
            "contents": [{"parts": [{"text": prompt}]}]
        }
        
        try:
            response = requests.post(self.url, json=payload, timeout=60)
            
            if response.status_code == 200:
                data = response.json()
                text = data['candidates'][0]['content']['parts'][0]['text']
                
                # Limpiar el texto de basura markdown
                text = text.replace("```json", "").replace("```", "").strip()
                return json.loads(text)
            else:
                logger.error(f"Error API {response.status_code}: {response.text}")
                return self._get_fallback(topic)
                
        except Exception as e:
            logger.error(f"Error en Gemini: {e}")
            return self._get_fallback(topic)

    def _get_fallback(self, topic):
        return {
            "title": f"Datos curiosos de {topic}",
            "full_script": "¡Hola a todos! Bienvenidos a El Tío Jota. Hoy vamos a descubrir datos fascinantes sobre " + topic + ". Prepárate para sorprenderte con esta información increíble. No olvides suscribirte para más contenido viral como este.",
            "keywords": topic + ", viral, datos",
            "voice": "random",
            "description": "Explorando " + topic + " con El Tío Jota.",
            "tags": "curiosidades, viral, shorts"
        }
