import os
import json
import time
import requests
import re
import logging
from src.gemini_api_manager import gemini_api_manager
from typing import Dict, Any, Optional, Set, List

logger = logging.getLogger(__name__)


class ScriptGenerator:
    def __init__(self):
        # Compatibilidad con nombres antiguos + nombre oficial actual
        self.grok_api_key = (
            os.getenv("XAI_API_KEY")
            or os.getenv("GROK_TOKEN")
            or os.getenv("GROK_API_KEY")
        )

        # Endpoint global oficial de xAI
        self.xai_api_base = os.getenv("XAI_API_BASE_URL", "https://api.x.ai").rstrip("/")
        self.xai_timeout = int(os.getenv("XAI_TIMEOUT", "120"))

    def _get_xai_headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.grok_api_key}"
        }

    def _extract_available_models_from_language_models(self, payload: Dict[str, Any]) -> Set[str]:
        available: Set[str] = set()

        for model in payload.get("models", []) or []:
            if not isinstance(model, dict):
                continue

            model_id = model.get("id")
            if isinstance(model_id, str) and model_id.strip():
                available.add(model_id.strip())

            aliases = model.get("aliases", []) or []
            for alias in aliases:
                if isinstance(alias, str) and alias.strip():
                    available.add(alias.strip())
                elif isinstance(alias, dict):
                    alias_id = alias.get("id")
                    if isinstance(alias_id, str) and alias_id.strip():
                        available.add(alias_id.strip())

        return available

    def _extract_available_models_from_models(self, payload: Dict[str, Any]) -> Set[str]:
        available: Set[str] = set()

        for model in payload.get("data", []) or []:
            if not isinstance(model, dict):
                continue

            model_id = model.get("id")
            if isinstance(model_id, str) and model_id.strip():
                available.add(model_id.strip())

        return available

    def _get_available_xai_models(self) -> Set[str]:
        """
        Intenta descubrir los modelos realmente disponibles para la API key.
        Primero usa /v1/language-models (más completo), y si falla, /v1/models.
        """
        if not self.grok_api_key:
            return set()

        headers = self._get_xai_headers()
        available: Set[str] = set()

        # Intento 1: endpoint completo con aliases
        try:
            url = f"{self.xai_api_base}/v1/language-models"
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                data = response.json()
                available |= self._extract_available_models_from_language_models(data)
                if available:
                    logger.info(f"Modelos xAI detectados desde /v1/language-models: {sorted(available)}")
                    return available
            else:
                logger.warning(
                    f"No se pudo obtener /v1/language-models (status {response.status_code}): {response.text}"
                )
        except Exception as e:
            logger.warning(f"Error consultando /v1/language-models: {e}")

        # Intento 2: endpoint básico
        try:
            url = f"{self.xai_api_base}/v1/models"
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                data = response.json()
                available |= self._extract_available_models_from_models(data)
                if available:
                    logger.info(f"Modelos xAI detectados desde /v1/models: {sorted(available)}")
            else:
                logger.warning(
                    f"No se pudo obtener /v1/models (status {response.status_code}): {response.text}"
                )
        except Exception as e:
            logger.warning(f"Error consultando /v1/models: {e}")

        return available

    def _preferred_xai_candidates(self) -> List[str]:
        """
        Modelos actuales y documentados oficialmente para texto/chat.
        Ordenados por prioridad práctica para este caso de uso.
        """
        return [
            "grok-4.20-reasoning",   # Flagship reasoning model
            "grok-4.20",             # Alias for latest stable 4.20
            "grok-4.20-non-reasoning", # Fast 4.20 variant
            "grok-4",                # Stable alias for Grok 4 series
            "grok-4-1-fast-reasoning",
            "grok-4-1-fast",
            "grok-3",
            "grok-3-mini",
        ]

    def _get_xai_candidate_models(self) -> List[str]:
        """
        Devuelve la lista ordenada de modelos a probar:
        1) prioriza candidatos actuales oficiales
        2) filtra por los realmente disponibles en la API key si se pueden descubrir
        3) si no se pueden descubrir, usa la lista preferida directamente
        """
        preferred = self._preferred_xai_candidates()
        available = self._get_available_xai_models()

        if not available:
            logger.warning(
                "No se pudieron descubrir modelos disponibles en xAI. "
                "Se probará la lista de candidatos oficiales por orden."
            )
            return preferred

        ordered = [m for m in preferred if m in available]

        # Añadir otros modelos Grok disponibles por si la cuenta tiene variantes diferentes
        extras = sorted(
            m for m in available
            if isinstance(m, str)
            and m.startswith("grok-")
            and m not in ordered
            and "imagine" not in m
            and "voice" not in m
        )

        candidates = ordered + extras

        if not candidates:
            logger.warning(
                "La API key no devolvió ninguno de los candidatos preferidos; "
                "se reintentará con la lista estática oficial."
            )
            return preferred

        return candidates

    def _parse_xai_json_content(self, content: str, voz: str) -> Dict[str, Any]:
        raw = (content or "").strip()

        # Limpieza por si el modelo devuelve markdown fenced JSON
        raw = re.sub(r"^```json\s*|\s*```$", "", raw, flags=re.IGNORECASE | re.DOTALL).strip()

        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            # Plan B: extraer el primer objeto JSON del texto
            match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
            if not match:
                raise
            result = json.loads(match.group(0))

        if "voice" not in result:
            result["voice"] = voz

        return result

    def _call_llama_fallback(self, prompt: str, voz: str) -> Optional[Dict[str, Any]]:
        """
        Fallback a xAI en caso de que Gemini falle.
        Se mantiene /v1/chat/completions para no romper tu integración actual.
        """
        if not self.grok_api_key:
            logger.warning("XAI_API_KEY/GROK_TOKEN/GROK_API_KEY no configurado. Fallback no disponible.")
            return None

        logger.info(f"Intentando generar guion con xAI (Fallback) usando endpoint global: {self.xai_api_base}")

        url = f"{self.xai_api_base}/v1/chat/completions"
        headers = self._get_xai_headers()
        fallback_models = self._get_xai_candidate_models()

        logger.info(f"Orden de modelos fallback xAI: {fallback_models}")

        for model in fallback_models:
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Eres un experto en guiones de YouTube. "
                            "Responde exclusivamente con un objeto JSON válido."
                        )
                    },
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "response_format": {"type": "json_object"}
            }

            try:
                response = requests.post(url, headers=headers, json=payload, timeout=self.xai_timeout)

                if response.status_code == 200:
                    data = response.json()
                    choices = data.get("choices", [])

                    if choices and choices[0].get("message", {}).get("content"):
                        content = choices[0]["message"]["content"]
                        result = self._parse_xai_json_content(content, voz)
                        logger.info(f"✅ Guion generado exitosamente con el modelo de fallback xAI: {model}")
                        return result

                    logger.warning(f"El modelo {model} respondió 200 pero sin contenido utilizable.")
                    continue

                # Reintento sin response_format si el modelo/endp. lo rechaza
                if response.status_code in (400, 422) and "response_format" in response.text.lower():
                    logger.warning(
                        f"El modelo {model} rechazó response_format. Reintentando sin response_format..."
                    )

                    payload_no_format = {
                        "model": model,
                        "messages": [
                            {
                                "role": "system",
                                "content": (
                                    "Eres un experto en guiones de YouTube. "
                                    "Responde exclusivamente con un objeto JSON válido, sin texto adicional."
                                )
                            },
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.7
                    }

                    retry_response = requests.post(
                        url,
                        headers=headers,
                        json=payload_no_format,
                        timeout=self.xai_timeout
                    )

                    if retry_response.status_code == 200:
                        data = retry_response.json()
                        choices = data.get("choices", [])

                        if choices and choices[0].get("message", {}).get("content"):
                            content = choices[0]["message"]["content"]
                            result = self._parse_xai_json_content(content, voz)
                            logger.info(
                                f"✅ Guion generado exitosamente con el modelo xAI (sin response_format): {model}"
                            )
                            return result

                logger.warning(
                    f"Fallo con el modelo {model} "
                    f"(Status: {response.status_code}). Respuesta: {response.text}"
                )

            except Exception as e:
                logger.error(f"Error intentando fallback con modelo xAI {model}: {e}")

        return None

    def generate_full_script(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Genera un guion optimizado para YouTube utilizando la API de Gemini con fallback a xAI.
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
            # PROMPT DEDICADO PARA SHORTS
            prompt = (
                f"Eres el guionista más viral de YouTube Shorts y TikTok. Tu especialidad es el 'Storytelling de Retención Infinita'.\n"
                f"TEMA: {topic}\n"
                f"CANAL: {canal}\n"
                f"CATEGORÍA: {categoria}\n"
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
            # PROMPT ESPECÍFICO PARA VIDEOS LARGOS
            prompt = (
                f"Eres un experto documentalista y guionista de YouTube para videos de larga duración (8-10 minutos).\n"
                f"TEMA: {topic}\n"
                f"CANAL: {canal}\n"
                f"CATEGORÍA: {categoria}\n"
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
            "\nIMPORTANTE: En 'segmented_script', divide el guion en frases o párrafos pequeños. "
            "La suma de 'estimated_duration' debe coincidir con la duración total esperada."
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
                    if "candidates" in data and len(data["candidates"]) > 0:
                        text_response = data["candidates"][0]["content"]["parts"][0]["text"]
                        return json.loads(text_response)

                gemini_api_manager.rotate_key()
                time.sleep(retry_delay)

            except Exception as e:
                logger.error(f"Error en intento {attempt + 1}: {e}")
                time.sleep(retry_delay)

        # Fallback a xAI
        return self._call_llama_fallback(prompt, voz)
