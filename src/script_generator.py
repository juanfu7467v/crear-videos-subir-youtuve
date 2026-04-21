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
        is_short = "short" in format_suggested.lower()

        # Selección de voz basada en el canal
        if canal == "PeliPREX":
            voz = "es-MX-JorgeNeural"
        elif canal == "PeliPREX-Series":
            voz = "es-MX-DaliaNeural"
        elif canal == "PeliPREX-Shorts":
            voz = "es-MX-LarissaNeural"
        else:
            voz = "es-MX-DaliaNeural"

        if is_short:
            # PROMPT DEDICADO PARA SHORTS (VIRALIDAD EXTREMA Y CIERRE PERFECTO)
            prompt = (
                f"Eres el guionista más viral de YouTube Shorts y TikTok. Tu especialidad es el 'Storytelling de Retención Infinita'.\n"
                f"TEMA: {topic}\n"
                f"CANAL: {canal}\n"
                f"REGLA DE ORO: El guion debe ser una historia completa con INICIO, NUDO y DESENLACE PERFECTAMENTE CERRADO en máximo 55 segundos de locución.\n"
                "\nESTRUCTURA PARA SHORTS:\n"
                "1. EL GANCHO (0-3s): Una pregunta o afirmación que detenga el scroll inmediatamente. Ej: '¿Sabías que has estado viviendo una mentira?'\n"
                "2. EL CONFLICTO: Presenta el problema o la curiosidad de forma rápida y rítmica.\n"
                "3. LA REVELACIÓN: El dato o momento clave que nadie esperaba.\n"
                "4. CIERRE MAESTRO: Una conclusión potente que no deje al espectador con dudas, pero sí con ganas de ver más contenido tuyo.\n"
                "\nREQUISITOS TÉCNICOS:\n"
                "- NARRACIÓN COMPLETA: No cortes el guion. Debe terminar con una frase de impacto.\n"
                "- PALABRAS POR SEGUNDO: El guion debe tener unas 130-150 palabras para durar ~50-55 segundos.\n"
                "- IDIOMA: Español natural, directo, sin palabras complejas.\n"
            )
        else:
            # PROMPT ESPECÍFICO PARA VIDEOS LARGOS (ESTRUCTURA EXTENSA Y PROFUNDIDAD)
            prompt = (
                f"Eres un experto documentalista y guionista de YouTube para videos de larga duración (8-10 minutos).\n"
                f"TEMA: {topic}\n"
                f"CANAL: {canal}\n"
                f"REGLA DE ORO: Crea un guion profundo, educativo y entretenido que mantenga la atención durante minutos.\n"
                "\nESTRUCTURA PARA VIDEOS LARGOS:\n"
                "1. INTRODUCCIÓN CINEMATOGRÁFICA: Plantea el tema y por qué es importante.\n"
                "2. DESARROLLO POR CAPÍTULOS: Divide la información en puntos lógicos y fáciles de seguir.\n"
                "3. ANÁLISIS PROFUNDO: Aporta datos, curiosidades o teorías que no sean obvias.\n"
                "4. CONCLUSIÓN Y REFLEXIÓN: Resume lo aprendido y deja una pregunta abierta a la audiencia.\n"
                "\nREQUISITOS TÉCNICOS:\n"
                "- DURACIÓN: Guion para 5-8 minutos de locución (aprox. 800-1200 palabras).\n"
                "- TONO: Profesional, autoritario pero cercano.\n"
            )

        prompt += (
            "\nINSTRUCCIÓN DE SALIDA (JSON):\n"
            "Responde ÚNICAMENTE con un objeto JSON que contenga:\n"
            "'title': Un título imán de clics con emojis,\n"
            "'full_script': El guion completo listo para leer,\n"
            "'description': Una descripción SEO optimizada,\n"
            "'tags': Lista de 10 tags virales,\n"
            "'voice': '" + voz + "',\n"
            "'segmented_script': Una lista de objetos con 'segment_text' (párrafos cortos) y 'estimated_duration' (en segundos),\n"
            "'peliprex_search_term': El nombre de la película o tema principal para buscar visuales.\n"
            "\nIMPORTANTE: En 'segmented_script', divide el guion en frases o párrafos pequeños. La suma de 'estimated_duration' debe coincidir con la duración total esperada."
        )

        max_retries = 5
        retry_delay = 5

        for attempt in range(max_retries):
            try:
                headers = {
                    "Content-Type": "application/json",
                    "x-goog-api-key": gemini_api_manager.get_current_key()
                }
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"responseMimeType": "application/json"}
                }

                api_url = gemini_api_manager.get_api_url(model="gemini-2.5-flash")
                response = requests.post(api_url, headers=headers, json=payload, timeout=120)

                if response.status_code == 200:
                    data = response.json()
                    if 'candidates' in data and len(data['candidates']) > 0:
                        text_response = data['candidates'][0]['content']['parts'][0]['text']
                        return json.loads(text_response)
                
                gemini_api_manager.rotate_key()
                time.sleep(retry_delay)
            except Exception as e:
                logger.error(f"Error en intento {attempt + 1}: {e}")
                time.sleep(retry_delay)
        
        # Fallback
        return self._call_llama_fallback(prompt, voz)
