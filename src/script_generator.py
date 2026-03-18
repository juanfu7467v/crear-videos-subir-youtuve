import json
import logging
import re
import requests
import os
import time

logger = logging.getLogger(__name__)

class ScriptGenerator:
    def __init__(self, api_key: str):
        self.api_key = api_key.strip()
        self.model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )

    def generate_full_script(self, trend_data: dict) -> dict:
        topic = trend_data.get('tema_recomendado') or trend_data.get('topic', 'curiosidades')
        canal = trend_data.get('canal', 'El Tío Jota')
        categoria = trend_data.get('categoria', 'general').lower()
        user_prompt_ia = trend_data.get('prompt_ia')
        format_suggested = trend_data.get('formato_sugerido', 'Short').lower()
        
        # Definir estilo base según el canal y categoría
        if "Criterio" in canal or "películas" in categoria:
            estilo_base = "serio, analítico, profesional y directo. Enfocado en la verdad y el análisis crítico."
            voz = "es-MX-JorgeNeural"
        else:
            estilo_base = "entusiasta, curioso, cercano y muy dinámico. Enfocado en sorprender al espectador con datos increíbles."
            voz = "es-MX-DaliaNeural"

        base_instruction = user_prompt_ia if user_prompt_ia else (
            f"Actúa como un experto creador de contenido para YouTube y estratega de viralidad. "
            f"Tu objetivo es crear un guion para el canal '{canal}' que logre enganchar, emocionar y retener al espectador hasta el último segundo."
        )

        prompt = (
            f"{base_instruction}\n\n"
            f"TEMA: {topic}\n"
            f"CATEGORÍA: {categoria}\n"
            f"FORMATO: {format_suggested}\n"
            f"ESTILO REQUERIDO: {estilo_base}\n\n"
            "ESTRUCTURA OBLIGATORIA DEL CONTENIDO:\n"
            "1. INICIO IMPACTANTE (HOOK): Una frase poderosa en los primeros 5 segundos que genere una curiosidad irresistible o rompa un patrón.\n"
            "2. DESARROLLO INTERESANTE: Explicación clara con datos sorprendentes, ritmo ágil y sin rellenos. Usa frases cortas para mantener el dinamismo.\n"
            "3. GIRO O MOMENTO LLAMATIVO: Introduce algo inesperado, un dato poco conocido o un cambio de ritmo que mantenga la atención alta a mitad del video.\n"
            "4. CONCLUSIÓN PODEROSA: Un mensaje final claro, una reflexión impactante o un resumen que deje al espectador satisfecho.\n"
            "5. LLAMADA A LA ACCIÓN (CTA): Invita de forma creativa a suscribirse o ver más contenido, integrada naturalmente en el cierre.\n\n"
            "REQUISITOS TÉCNICOS:\n"
            "- IDIOMA: Español natural, claro y directo.\n"
            "- LIMPIEZA: No uses símbolos como (*, _, -, #) en el 'full_script'. Sin acotaciones de escena.\n"
            "- KEYWORDS: 8-10 términos descriptivos en inglés para búsqueda de material visual.\n"
            "- DURACIÓN: " + ("Máximo 55 segundos de locución (aprox 130-140 palabras)" if "short" in format_suggested else "Entre 3 y 5 minutos de locución (aprox 450-750 palabras)") + ".\n"
            "- CAMPOS ADICIONALES: Debes incluir 'prompt_ia', 'estilo_contenido', 'hook' y 'estructura' en el JSON.\n\n"
            "Responde ÚNICAMENTE con un objeto JSON que contenga las siguientes llaves:\n"
            "'title', 'full_script', 'keywords', 'voice', 'description', 'tags', 'prompt_ia', 'estilo_contenido', 'hook', 'estructura', 'segmented_script'.\n"
            f"En 'voice' usa siempre: {voz}.\n\n"
            "Para cada segmento del 'full_script', proporciona un 'segment_text', 'keywords' (3-5 términos en inglés) y 'estimated_duration' (en segundos, basándose en la longitud del texto y un ritmo de habla normal de 150 palabras por minuto). La suma de 'estimated_duration' debe ser aproximadamente la duración total del guion.\n\n"
            "'segmented_script' debe ser una lista de objetos, cada uno con 'segment_text', 'keywords' and 'estimated_duration'."
        )
        
        max_retries = 3
        retry_delay = 5
        timeout_seconds = 90

        for attempt in range(max_retries):
            try:
                logger.info(f"Intento {attempt + 1}/{max_retries} de generación de guion (timeout: {timeout_seconds}s)...")
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"response_mime_type": "application/json"}
                }
                
                response = requests.post(self.url, json=payload, timeout=timeout_seconds)
                
                if response.status_code != 200:
                    logger.error(f"Error API {response.status_code}: {response.text}")
                    if response.status_code in [429, 500, 502, 503, 504]:
                        time.sleep(retry_delay * (attempt + 1))
                        continue
                    return None

                data = response.json()
                text_response = data['candidates'][0]['content']['parts'][0]['text']
                
                raw = re.search(r'\{.*\}', text_response, re.DOTALL)
                data = json.loads(raw.group(0)) if raw else json.loads(text_response)

                if 'full_script' in data:
                    real_name = "El Tío Jota"
                    if canal and "Criterio" in canal:
                        real_name = "El Criterio"
                    
                    data['full_script'] = data['full_script'].replace("CHANNEL_NAME_2", real_name)
                    data['full_script'] = data['full_script'].replace("CHANNEL_NAME", real_name)
                
                return data
                
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout en intento {attempt + 1}. Reintentando...")
                time.sleep(retry_delay)
            except Exception as e:
                logger.error(f"Error en intento {attempt + 1}: {e}")
                time.sleep(retry_delay)

        logger.error("Se agotaron los reintentos para generar el guion.")
        return None
