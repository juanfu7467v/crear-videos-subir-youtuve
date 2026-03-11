import json
import logging
import os
import re
import requests
import time  # Importamos time para la pausa

logger = logging.getLogger(__name__)

class ScriptGenerator:
    def __init__(self, api_key: str):
        self.api_key = api_key
        # Usamos gemini-2.0-flash
        self.model = "gemini-2.0-flash"
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"

    def generate_full_script(self, trend_data: dict) -> dict:
        topic = trend_data.get('topic', 'Tema interesante')
        
        prompt = (
            f"Genera un guion para un video de YouTube sobre: {topic}. "
            "Es obligatorio que respondas EXCLUSIVAMENTE en formato JSON con la siguiente estructura: "
            '{"title": "...", "full_script": "...", "keywords": ["...", "..."], "voice": "es-MX-DaliaNeural", "description": "...", "tags": ["...", "..."]}. '
            "No incluyas explicaciones ni bloques de código Markdown."
        )
        
        if not self.api_key:
            logger.warning("No se detectó GEMINI_API_KEY. Usando datos de prueba.")
            return {"title": "Demo", "full_script": "Hola, este es un video de prueba.", "voice": "es-MX-DaliaNeural"}

        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0.7,
                "response_mime_type": "application/json"
            }
        }
        headers = {'Content-Type': 'application/json'}

        # Ciclo de reintentos para manejar el error 429
        for attempt in range(3):
            try:
                response = requests.post(self.url, headers=headers, json=payload, timeout=30)
                
                # Si el error es 429, el bloque 'except' lo capturará
                response.raise_for_status()
                
                data = response.json()
                if 'candidates' in data and len(data['candidates']) > 0:
                    text_response = data['candidates'][0]['content']['parts'][0]['text']
                    raw = re.sub(r'```json\s*|\s*```', '', text_response.strip())
                    return json.loads(raw)
                else:
                    raise ValueError(f"Respuesta vacía de la API: {data}")

            except requests.exceptions.HTTPError as e:
                # Verificamos si es un error de "Too Many Requests" (429)
                if response.status_code == 429:
                    logger.warning(f"Límite de API alcanzado (Intento {attempt + 1}/3). Esperando 15s...")
                    time.sleep(15)
                    continue # Salta a la siguiente iteración del ciclo for
                else:
                    logger.error(f"Error HTTP en ScriptGenerator: {e}")
                    break # Si es otro error (ej. 400 o 500), no reintentamos
            except Exception as e:
                logger.error(f"Error crítico en ScriptGenerator: {e}")
                break

        # Fallback si todos los intentos fallan
        return {
            "title": f"Video sobre {topic}",
            "full_script": f"Hoy vamos a hablar sobre {topic}. Es un tema fascinante.",
            "voice": "es-MX-DaliaNeural",
            "keywords": [topic],
            "description": "Video generado automáticamente.",
            "tags": [topic]
        }
