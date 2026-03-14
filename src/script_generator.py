import json
import logging
import re
import requests
import os

logger = logging.getLogger(__name__)

class ScriptGenerator:
    """
    Generador de guiones optimizado para la API v1 de Gemini y modelos de la serie 2.5.
    Mantiene compatibilidad con el pipeline de video existente.
    """
    def __init__(self, api_key: str):
        self.api_key = api_key.strip()
        # En marzo de 2026, gemini-2.5-flash es el modelo estable recomendado.
        # Se puede usar 'gemini-flash-latest' para apuntar siempre a la última versión estable.
        self.model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        
        # Corrección Crítica: Se utiliza el endpoint estable 'v1' en lugar de 'v1beta'.
        # El prefijo 'models/' es requerido por la especificación de la API de Google.
        self.url = f"https://generativelanguage.googleapis.com/v1/models/{self.model}:generateContent?key={self.api_key}"

    def generate_full_script(self, trend_data: dict) -> dict:
        """
        Genera guiones en formato JSON utilizando el modo nativo de la API.
        """
        topic = trend_data.get('topic', 'curiosidades interesantes')
        
        # Prompt optimizado para evitar texto explicativo innecesario
        prompt = (
            f"Actúa como un experto guionista de YouTube Shorts para el canal 'El Tío Jota'. "
            f"Tema: '{topic}'. "
            "Requerimientos: "
            "1. Guion de 60 segundos exactos con un hook inicial potente. "
            "2. Estilo educativo, viral y dinámico. "
            "3. La respuesta debe ser exclusivamente el objeto JSON sin formato markdown."
            "Campos requeridos: title, full_script, keywords, voice, description, tags."
        )
        
        try:
            # Configuración de generación para asegurar salida JSON pura
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    # Activación del modo JSON nativo soportado en la API v1
                    "response_mime_type": "application/json",
                    "temperature": 0.7,
                    "top_p": 0.95,
                    "maxOutputTokens": 2048
                }
            }
            
            # Timeout de 60 segundos para permitir el razonamiento del modelo 2.5
            response = requests.post(self.url, json=payload, timeout=60)
            
            if response.status_code!= 200:
                logger.error(f"Error de API (Status {response.status_code}): {response.text}")
                return self._get_fallback(topic)

            data = response.json()
            
            # Validación de la existencia de candidatos en la respuesta
            if not data.get('candidates') or not data['candidates'].get('content'):
                logger.error("La API devolvió una respuesta vacía o bloqueada por seguridad.")
                return self._get_fallback(topic)
                
            text_response = data['candidates']['content']['parts']['text']
            
            # Limpieza defensiva en caso de que el modelo incluya caracteres extra
            cleaned_text = re.sub(r'^```json\s*|\s*```$', '', text_response.strip(), flags=re.MULTILINE)
            
            return json.loads(cleaned_text)
            
        except json.JSONDecodeError as jde:
            logger.error(f"Fallo al decodificar JSON: {jde}. Respuesta cruda: {text_response}")
            return self._get_fallback(topic)
        except Exception as e:
            logger.error(f"Error crítico en la generación con Gemini: {e}")
            return self._get_fallback(topic)

    def _get_fallback(self, topic: str):
        """
        Mecanismo de seguridad para garantizar que el pipeline siempre tenga contenido.
        """
        return {
            "title": f"Secretos revelados: {topic}", 
            "full_script": (
                f"¡Oye tú! ¿Sabías esto sobre {topic}? En este video de El Tío Jota "
                "vamos a descubrir datos que te dejarán con la boca abierta. Quédate "
                "hasta el final porque el último dato es simplemente increíble. "
                "No olvides suscribirte para tu dosis diaria de conocimiento."
            ), 
            "voice": "random", 
            "keywords": f"{topic}, viral, shorts, curiosidades", 
            "description": f"Descubre todo sobre {topic} en este Short de El Tío Jota.", 
            "tags": "curiosidades, viral, shorts, eltiojota, educativo"
        }
