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
        
        if "Criterio" in canal or "películas" in categoria:
            estilo_base = "emocional, intrigante, directo, con impacto psicológico fuerte, frases cortas tipo TikTok y alta retención."
            voz = "es-MX-JorgeNeural"
        else:
            estilo_base = "emocional, intrigante, directo, con impacto psicológico fuerte, frases cortas tipo TikTok y alta retención."
            voz = "es-MX-DaliaNeural"

        # 🔥 PROMPT MEJORADO (CEREBRO DEL SISTEMA)
        base_instruction = user_prompt_ia if user_prompt_ia else (
            f"Actúa como un creador de contenido viral experto en YouTube, psicología humana y retención de audiencia. "
            f"Tu objetivo NO es informar, es ATRAPAR, GENERAR CURIOSIDAD y hacer que el espectador NO pueda dejar de ver el video. "

            f"Para el canal '{canal}', crea contenido altamente adictivo, emocional y directo. "
            f"Evita sonar como documental o clase aburrida. Habla como si estuvieras revelando un secreto poderoso.\n\n"

            f"Usa técnicas psicológicas:\n"
            f"- Curiosity gap (dejar intriga)\n"
            f"- Open loops (cosas que se revelan después)\n"
            f"- Frases que desafían al espectador\n"
            f"- Sensación de descubrimiento o verdad oculta\n\n"

            f"TÍTULO (CLAVE PARA VIRALIDAD):\n"
            f"- Debe parecer un secreto o algo impactante\n"
            f"- NO genérico\n"
            f"- Debe generar clic inmediato\n\n"

            f"DESCRIPCIÓN (MAX 450 caracteres):\n"
            f"Debe generar intriga y emoción.\n\n"

            "Análisis: [Nombre de la Película] 🎲\n"
            "Esto no es solo una historia… es una advertencia. Lo que estás a punto de ver cambia todo.\n\n"
            "🔥 Mírala gratis aquí: 👉 {{PELIPREX_LINK}}\n\n"
            "💎 Cine exclusivo. Sin anuncios.\n"
            "👉 https://masitaprex.com/PeliPREX\n\n"
            "Solo unos pocos lo entienden… ¿eres uno de ellos? 🚀\n\n"

            "REGLA: No expliques demasiado, genera curiosidad."
        )

        prompt = (
            f"{base_instruction}\n\n"
            f"TEMA: {topic}\n"
            f"CATEGORÍA: {categoria}\n"
            f"FORMATO: {format_suggested}\n"
            f"ESTILO REQUERIDO: {estilo_base}\n\n"

            "ESTRUCTURA OBLIGATORIA DEL CONTENIDO:\n"
            "1. HOOK EXTREMO: Impacto en 3-5 segundos que obligue a seguir viendo.\n"
            "2. DESARROLLO DINÁMICO: Frases cortas, ritmo rápido, preguntas constantes.\n"
            "3. MOMENTO IMPACTANTE: Revelación o giro inesperado.\n"
            "4. FINAL PODEROSO: Mensaje fuerte que deje pensando.\n"
            "5. CTA: Suscribirse con emoción.\n\n"

            "REGLAS DE VIRALIDAD:\n"
            "- Cada 5 segundos debe haber algo interesante.\n"
            "- Evita párrafos largos.\n"
            "- Usa lenguaje emocional.\n"
            "- Genera intriga constante.\n"
            "- Haz sentir que si se va, pierde algo importante.\n\n"

            "REQUISITOS TÉCNICOS:\n"
            "- IDIOMA: Español natural.\n"
            "- DURACIÓN: " + ("Máximo 55 segundos" if "short" in format_suggested else "Entre 3 y 5 minutos") + ".\n\n"

            "- KEYWORDS VISUALES:\n"
            "Usa SOLO términos simples en inglés:\n"
            "'man thinking', 'dark room', 'city night', 'cinematic light', 'close up face'\n"
            "NO uses palabras abstractas.\n\n"

            "INSTRUCCIÓN PELIPREX:\n"
            "Extrae SOLO el nombre exacto del contenido.\n\n"

            "Responde SOLO en JSON con:\n"
            "'title', 'full_script', 'keywords', 'voice', 'description', 'tags', "
            "'prompt_ia', 'estilo_contenido', 'hook', 'estructura', "
            "'segmented_script', 'peliprex_search_term', 'thumbnail_text'.\n\n"

            "thumbnail_text: frase corta (máx 5 palabras) MUY llamativa.\n\n"

            f"voice: {voz}"
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
                
            except Exception as e:
                logger.error(f"Error en intento {attempt + 1}: {e}")
                time.sleep(retry_delay)

        return None
