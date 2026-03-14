import json
import logging
import re
import requests
import os

logger = logging.getLogger(__name__)

class ScriptGenerator:
    def __init__(self, api_key: str):
        self.api_key = api_key.strip()
        # Usar modelo por defecto: alias estable más reciente de Gemini Flash
        self.model = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
        # Usar la versión estable de la API (v1)
        self.api_version = "v1"
        self.base_url = f"https://generativelanguage.googleapis.com/{self.api_version}"
        # Endpoint inicial para generar contenido
        self.url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"

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
            # Intentar generar contenido; si falla con 404, actualizar modelo
            for attempt in range(2):
                response = requests.post(self.url, json=payload, timeout=60)
                # Éxito en llamada a la API
                if response.status_code == 200:
                    break
                # Si el modelo no existe (404) en primer intento, obtener lista de modelos
                if response.status_code == 404 and attempt == 0:
                    logger.warning(f"Modelo '{self.model}' no encontrado. Obteniendo lista de modelos disponibles...")
                    list_url = f"{self.base_url}/models?key={self.api_key}"
                    try:
                        list_resp = requests.get(list_url, timeout=10)
                        if list_resp.status_code == 200:
                            models = list_resp.json().get("models", [])
                            best_model = None
                            best_version = (0, 0)
                            # Seleccionar el modelo Gemini Flash estable de mayor versión
                            for m in models:
                                name = m.get("name", "")
                                if not name.startswith("models/gemini-"):
                                    continue
                                short_name = name.split("/", 1)[1]  # quitar prefijo "models/"
                                parts = short_name.split("-")
                                if len(parts) < 3 or parts[0] != "gemini" or parts[2] != "flash":
                                    continue
                                # Evitar versiones de preview, experimental o flash-lite
                                if any(x in parts for x in ["preview", "exp", "lite"]):
                                    continue
                                # Extraer versión mayor y menor
                                ver_parts = parts[1].split(".")
                                try:
                                    major = int(ver_parts[0])
                                    minor = int(ver_parts[1]) if len(ver_parts) > 1 else 0
                                except ValueError:
                                    continue
                                if (major, minor) > best_version:
                                    best_version = (major, minor)
                                    best_model = short_name
                            if best_model:
                                logger.info(f"Actualizando modelo a '{best_model}'.")
                                self.model = best_model
                                self.url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"
                                continue  # reintentar con el nuevo modelo
                    except Exception as e_list:
                        logger.error(f"Error al obtener lista de modelos: {e_list}")
                # Otros errores
                logger.error(f"Error API {response.status_code}: {response.text}")
                return self._get_fallback(topic)
            # Tras intentos, verificar respuesta
            if response.status_code != 200:
                logger.error(f"Fallo después de reintentos, estado {response.status_code}.")
                return self._get_fallback(topic)

            data = response.json()
            # Extraer texto del candidato
            text_response = data['candidates'][0]['content']['parts'][0]['text']

            # Limpiar posibles delimitadores de bloque JSON
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
