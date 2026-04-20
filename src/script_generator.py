import os
import json
import time
import requests
import re
import logging
from src.gemini_api_manager import gemini_api_manager
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class ScriptGenerator:
    def __init__(self):
        # El usuario ha especificado que el token se llama GROK_TOKEN en Secrets
        self.grok_api_key = os.getenv("GROK_TOKEN") or os.getenv("GROK_API_KEY")

    def _call_llama_fallback(self, prompt: str, voz: str) -> Optional[Dict[str, Any]]:
        """Llamada de fallback a modelos de X.AI en caso de que Gemini falle."""
        if not self.grok_api_key:
            logger.warning("GROK_TOKEN/GROK_API_KEY no configurado. Fallback no disponible.")
            return None

        logger.info("Intentando generar guion con modelos de X.AI (Fallback)...")
        url = "https://api.x.ai/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.grok_api_key}"
        }
        
        # Nombres de modelos corregidos para X.AI (Grok)
        fallback_models = ["grok-2-latest", "grok-2-1212", "grok-beta"]
        
        for model in fallback_models:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": "Eres un experto en guiones de YouTube. Responde exclusivamente con un objeto JSON válido."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "response_format": {"type": "json_object"}
            }

            try:
                response = requests.post(url, headers=headers, json=payload, timeout=120)
                if response.status_code == 200:
                    data = response.json()
                    if 'choices' in data and len(data['choices']) > 0:
                        content = data['choices'][0]['message']['content']
                        raw = content.strip()
                        raw = re.sub(r'```json\s*|\s*```', '', raw)
                        result = json.loads(raw)
                        if 'voice' not in result:
                            result['voice'] = voz
                        logger.info(f"✅ Guion generado exitosamente con el modelo de fallback: {model}")
                        return result
                else:
                    logger.warning(f"Fallo con el modelo {model} (Status: {response.status_code}). Respuesta: {response.text}")
            except Exception as e:
                logger.error(f"Error intentando fallback con modelo {model}: {e}")
        
        return None

    def generate_full_script(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Genera un guion optimizado para YouTube utilizando la API de Gemini con fallback a X.AI.
        """
        topic = input_data.get("tema_recomendado", "Sin tema")
        canal = input_data.get("canal", "CHANNEL_NAME")
        categoria = input_data.get("categoria", "general")
        format_suggested = input_data.get("formato_sugerido", "Short")
        estilo_base = input_data.get("idea_contenido", "Emocional y directo")
        user_prompt_ia = input_data.get("prompt_ia")

        # Selección de voz basada en el canal
        if canal == "PeliPREX":
            voz = "es-MX-JorgeNeural"
        elif canal == "PeliPREX-Series":
            voz = "es-MX-DaliaNeural"
        elif canal == "PeliPREX-Shorts":
            voz = "es-MX-LarissaNeural"
        else:
            voz = "es-MX-DaliaNeural"

        base_instruction = user_prompt_ia if user_prompt_ia else (
            f"Actúa como el estratega de contenido más letal de YouTube, dueño de 50 canales virales. "
            f"Tu misión es destruir el algoritmo del canal '{canal}' mediante manipulación psicológica extrema. "
            f"El guion NO debe informar, debe PROVOCAR. Utiliza sesgos cognitivos, curiosidad morbosa y validación del ego. "
            f"Para películas, el título y descripción deben ser imanes de clics (SEO agresivo), usando frases que activen el deseo de exclusividad. "
            f"La descripción debe ser corta (MÁXIMO 450 CARACTERES) y seguir EXACTAMENTE este formato:\n\n"
            "Análisis: [Nombre de la Película] 🎲\n"
            "¿Dominas el juego o eres una pieza más? [Película] no es cine, es un manual de poder para los que no temen al caos. Mientras la masa obedece, el líder ejecuta. Solo la élite entiende estas reglas.\n\n"
            "🔥 Mírala gratis aquí: 👉 {{https://masitaprex.com/PeliPREX?movie=}}\n\n"
            "💎 Cine exclusivo. Sin anuncios.\n"
            "👉 https://masitaprex.com/PeliPREX\n\n"
            "Únete al círculo. El resto solo mira. 🚀\n\n"
            "REGLA DE ORO: Ve directo a la yugular de la emoción. Usa el bloque de Peliprex tal cual."
        )

        prompt = (
            f"{base_instruction}\n\n"
            f"TEMA: {topic}\n"
            f"CATEGORÍA: {categoria}\n"
            f"FORMATO: {format_suggested}\n"
            f"ESTILO REQUERIDO: Manipulación psicológica, intriga de élite y retención máxima.\n\n"
            "REGLA CRÍTICA PARA EL TÍTULO:\n"
            "Comienza con 2 hashtags de alto tráfico seguidos de un título que genere FOMO (miedo a perderse algo).\n"
            "Ejemplo: '#cine #misterio Lo que el 99% ignoró de esta escena'\n\n"
            "ESTRUCTURA OBLIGATORIA DEL CONTENIDO (RETENCIÓN RADICAL):\n"
            "1. HOOK EXPLOSIVO (0-5s): Una bofetada verbal. Algo que cuestione la inteligencia del espectador o le prometa un secreto prohibido.\n"
            "2. DESARROLLO DE TENSIÓN: Frases rápidas, estilo 'ritmo cardiaco'. Cada frase debe obligar a escuchar la siguiente. Cero relleno. Habla de 'nosotros' contra 'ellos'.\n"
            "3. EL GIRO MAESTRO: Revela un detalle oscuro o una verdad incómoda que nadie más está diciendo.\n"
            "4. CIERRE DE PODER: Deja al espectador sintiéndose parte de una élite por haber terminado el video.\n"
            "5. CTA SUBLIMINAL: Invita a suscribirse como la única forma de no perder el acceso a esta información única.\n\n"
            "REQUISITOS TÉCNICOS:\n"
            "- IDIOMA: Español natural, directo y autoritario.\n"
            "- KEYWORDS VISUALES (Pexels): Solo términos visuales CRUDOS y POTENTES en inglés (ej: 'angry man shouting', 'dark empty street', 'golden luxury', 'hidden camera', 'burning fire').\n"
            "- BÚSQUEDA DE STOCK (Archive.org): Solo el nombre real de la película/personaje: '{topic}'.\n"
            "- DURACIÓN: " + ("Exactamente 60 segundos (ni un segundo más ni menos)" if "short" in format_suggested.lower() else "Entre 3 y 5 minutos") + ".\n\n"
            "INSTRUCCIÓN ESPECIAL PELIPREX:\n"
            "Extrae solo el sustantivo principal (Película/Serie) para la búsqueda de clips reales.\n\n"
            "Responde ÚNICAMENTE con un objeto JSON que contenga:\n"
            "'title', 'full_script', 'keywords', 'voice', 'description', 'tags', 'prompt_ia', 'estilo_contenido', 'hook', 'estructura', 'segmented_script', 'peliprex_search_term'.\n"
            f"En 'voice' usa siempre: {voz}.\n"
            "En 'peliprex_search_term' coloca el nombre exacto identificado.\n\n"
            "Cada objeto en 'segmented_script' debe tener: 'segment_text', 'keywords' (3-5 términos visuales simples en inglés) y 'estimated_duration'."
        )

        max_retries = 5
        retry_delay = 10
        timeout_seconds = 120

        # Intentar Gemini primero
        for attempt in range(max_retries):
            try:
                headers = {
                    "Content-Type": "application/json",
                    "x-goog-api-key": gemini_api_manager.get_current_key()
                }

                # Payload simplificado para máxima compatibilidad con el endpoint estable
                payload = {
                    "contents": [
                        {
                            "parts": [
                                {"text": prompt}
                            ]
                        }
                    ]
                }

                api_url = gemini_api_manager.get_api_url(model="gemini-2.5-flash")
                response = requests.post(api_url, headers=headers, json=payload, timeout=timeout_seconds)

                if response.status_code in [500, 502, 503, 504, 429]:
                    logger.warning(f"Error temporal de API Gemini ({response.status_code}) en intento {attempt + 1}. Reintentando en {retry_delay}s...")
                    gemini_api_manager.rotate_key()
                    time.sleep(retry_delay)
                    retry_delay *= 1.5
                    continue

                if response.status_code == 400:
                    logger.error(f"Error 400 en Gemini. Respuesta: {response.text}. Saltando al fallback.")
                    break

                response.raise_for_status()
                data = response.json()

                if 'candidates' in data and len(data['candidates']) > 0:
                    text_response = data['candidates'][0]['content']['parts'][0]['text']
                    raw = text_response.strip()
                    # Limpiar markdown
                    raw = re.sub(r'```json\s*|\s*```', '', raw)
                    # Extraer el primer objeto JSON si hay texto adicional
                    match = re.search(r'\{.*\}', raw, re.DOTALL)
                    if match:
                        return json.loads(match.group())
                    return json.loads(raw)
                else:
                    raise Exception(f"Respuesta inesperada de Gemini: {data}")

            except Exception as e:
                logger.error(f"Error en intento {attempt + 1} con Gemini: {e}")
                if attempt < max_retries - 1:
                    gemini_api_manager.rotate_key()
                    time.sleep(retry_delay)
                else:
                    break
        
        # FALLBACK A X.AI (Grok)
        logger.warning("Gemini no disponible. Iniciando fallback a X.AI...")
        xai_result = self._call_llama_fallback(prompt, voz)
        if xai_result:
            return xai_result
            
        raise Exception(f"Fallo crítico: Ni Gemini ni el sistema de fallback (X.AI) pudieron generar el guion.")
