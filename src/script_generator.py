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
        topic = trend_data.get(\'tema_recomendado\') or trend_data.get(\'topic\', \'curiosidades\')
        canal = trend_data.get(\'canal\', \'El Tío Jota\')
        categoria = trend_data.get(\'categoria\', \'general\').lower()
        user_prompt_ia = trend_data.get(\'prompt_ia\')
        format_suggested = trend_data.get(\'formato_sugerido\', \'Short\').lower()
        
        if "Criterio" in canal or "películas" in categoria:
            estilo_base = "emocional, intrigante, directo, con un inicio impactante y frases cortas tipo TikTok. Genera curiosidad constante y evita el lenguaje académico. Habla directamente al espectador."
            voz = "es-MX-JorgeNeural"
        else:
            estilo_base = "emocional, intrigante, directo, con un inicio impactante y frases cortas tipo TikTok. Genera curiosidad constante y evita el lenguaje académico. Habla directamente al espectador."
            voz = "es-MX-DaliaNeural"

        base_instruction = user_prompt_ia if user_prompt_ia else (
            f"Actúa como un experto creador de contenido para YouTube y estratega de viralidad. "
            f"Tu objetivo es crear un guion para el canal \'{canal}\' que logre enganchar, emocionar y retener al espectador hasta el último segundo. El guion NO debe ser informativo, sino emocional, intrigante y directo. "
            f"Para la categoría de películas, los títulos y descripciones deben estar **altamente optimizados para SEO en YouTube**, utilizando frases que la gente busca diariamente. El título debe ser **emocional, intrigante y generar curiosidad**, como si fuera un secreto que el espectador está a punto de descubrir. "
            f"La descripción debe ser una **experiencia emocional**, no una explicación. Debe generar intriga y conectar con el espectador a un nivel personal, usando un estilo como: \'Spider-Man no es solo un superhéroe... Es un reflejo de lo que tú estás viviendo ahora mismo. En este video descubrirás el mensaje oculto que millones no entendieron... y que puede cambiar tu forma de ver la vida.\' "
            f"Debe incluir un placeholder \'{{PELIPREX_LINK}}\' donde se insertará el enlace a la película, y al final, el siguiente bloque de texto con los enlaces de forma literal:\n\n"
            "🔥 Mírala GRATIS ahora:\n"
            "👉 {{PELIPREX_LINK}}\n\n"
            "💎 Cine exclusivo, sin anuncios:\n"
            "👉 https://masitaprex.com/PeliPREX\n\n"
            "Únete y disfruta más contenido."
        )

        prompt = (
            f"{base_instruction}\n\n"
            f"TEMA: {topic}\n"
            f"CATEGORÍA: {categoria}\n"
            f"FORMATO: {format_suggested}\n"
            f"ESTILO REQUERIDO: {estilo_base}\n\n"
            "ESTRUCTURA OBLIGATORIA DEL CONTENIDO:\n"
            "1. INICIO IMPACTANTE (HOOK): Una frase poderosa en los primeros 5 segundos, que sea emocional, intrigante y directo. \n"
            "2. DESARROLLO INTERESANTE: Frases cortas (tipo TikTok), incluyendo preguntas al espectador y generando curiosidad constante. Evita el lenguaje académico y habla como si conversaras con una persona.\n"
            "3. GIRO O MOMENTO LLAMATIVO: Introduce algo inesperado.\n"
            "4. CONCLUSIÓN PODEROSA: Un mensaje final claro.\n"
            "5. LLAMADA A LA ACCIÓN (CTA): Invita a suscribirse.\n\n"
            "REQUISITOS TÉCNICOS:\n"
            "- IDIOMA: Español natural.\n"
            "- KEYWORDS VISUALES: Para cada segmento, proporciona palabras clave en inglés que sean SIMPLES, VISUALES y CONCRETAS. "
            "Pexels no entiende conceptos abstractos. Usa términos como: \'man thinking\', \'city traffic\', \'cinematic landscape\', \'close up face\', \'technology\', \'dark room\'. "
            "EVITA términos como \'paradox\', \'spider-men\', \'comic book\' (si no son comunes en stock), \'fate\', \'destiny\'.\n"
            "- DURACIÓN: " + ("Máximo 55 segundos" if "short" in format_suggested else "Entre 3 y 5 minutos") + ".\n\n"
            "INSTRUCCIÓN ESPECIAL PARA BÚSQUEDA DE PELÍCULAS:\n"
            "Analiza profundamente el tema del video y extrae únicamente el nombre de la película principal.\n"
            "Ejemplo: si el tema es sobre el multiverso de Spider-Man, el resultado debe ser \'Spider-Man\'.\n"
            "No incluyas frases ni descripciones, solo el nombre exacto de la película.\n\n"
            "Responde ÚNICAMENTE con un objeto JSON que contenga:\n"
            "\'title\', \'full_script\', \'keywords\', \'voice\', \'description\', \'tags\', \'prompt_ia\', \'estilo_contenido\', \'hook\', \'estructura\', \'segmented_script\', \'peliprex_search_term\'.\n"
            f"En \'voice\' usa siempre: {voz}.\n"
            "En \'peliprex_search_term\' coloca el nombre exacto de la película principal identificada.\n"
            "Si la categoría es \'películas\', la descripción debe incluir un placeholder \'{{PELIPREX_LINK}}\' donde se insertará el enlace a la película, y el bloque de texto final con los enlaces de Peliprex.\n\n"
            "Cada objeto en \'segmented_script\' debe tener: \'segment_text\', \'keywords\' (lista de 3-5 términos visuales simples en inglés) and \'estimated_duration\'."
        )
        
        max_retries = 3
        retry_delay = 5
        timeout_seconds = 90

        for attempt in range(max_retries):
            try:
                logger.info(f"Intento {attempt + 1}/{max_retries} de generación de guion...")
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
                text_response = data[\'candidates\'][0][\'content\'][\'parts\'][0][\'text\']
                
                raw = re.search(r\'\\{.*\\}\'\', text_response, re.DOTALL)
                data = json.loads(raw.group(0)) if raw else json.loads(text_response)

                if \'full_script\' in data:
                    real_name = "El Tío Jota"
                    if canal and "Criterio" in canal:
                        real_name = "El Criterio"
                    
                    data[\'full_script\'] = data[\'full_script\'].replace("CHANNEL_NAME_2", real_name)
                    data[\'full_script\'] = data[\'full_script\'].replace("CHANNEL_NAME", real_name)
                
                return data
                
            except Exception as e:
                logger.error(f"Error en intento {attempt + 1}: {e}")
                time.sleep(retry_delay)

        return None
