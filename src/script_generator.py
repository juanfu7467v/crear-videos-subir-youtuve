"""
script_generator.py
────────────────────
Genera guiones completos con hooks de 3s, estructura narrativa
y palabras clave para buscar clips de video.
"""

import json
import logging
import os
import re
import google.generativeai as genai

logger = logging.getLogger(__name__)


SHORT_SCRIPT_PROMPT = """
Eres un guionista experto en YouTube Shorts virales en español.

Tema del video: {topic}
Idea: {idea}
Hook sugerido: {hook_idea}
Canal: {channel}
Audiencia: {audience}

Crea un guion COMPLETO para un YouTube Short de 45-60 segundos.

ESTRUCTURA OBLIGATORIA:
1. HOOK (primeros 3 segundos): Frase impactante que detenga el scroll
2. DESARROLLO (40-50 seg): Contenido informativo/entretenido dividido en puntos
3. CTA (últimos 5 seg): Llamada a la acción clara

REGLAS:
- Lenguaje casual, amigable, como si hablaras con un amigo
- Frases cortas (máx 15 palabras por oración)
- Usa números cuando sea posible (genera curiosidad)
- Incluye pausas naturales con comas
- El tono debe ser: emocionado, cercano, genuino

Responde ÚNICAMENTE con JSON válido (sin markdown):
{{
  "title": "título del video",
  "hook": "texto del hook (3 segundos, máx 2 oraciones)",
  "full_script": "guion completo incluyendo hook, desarrollo y CTA",
  "segments": [
    {{"time": "0-3s", "text": "texto del hook"}},
    {{"time": "3-50s", "text": "desarrollo"}},
    {{"time": "50-60s", "text": "CTA"}}
  ],
  "keywords": ["palabra1", "palabra2", "palabra3", "palabra4", "palabra5"],
  "visual_suggestions": ["sugerencia visual 1", "sugerencia visual 2"],
  "voice": "es-MX-DaliaNeural",
  "speech_rate": "+15%",
  "description": "descripción para YouTube (máx 500 chars)",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7"],
  "estimated_duration_seconds": 55
}}
"""

LONG_SCRIPT_PROMPT = """
Eres un guionista experto en videos de YouTube de formato largo en español.

Tema del video: {topic}
Idea: {idea}
Hook sugerido: {hook_idea}
Canal: {channel}
Audiencia: {audience}

Crea un guion COMPLETO para un video de YouTube de 8-12 minutos.

ESTRUCTURA OBLIGATORIA:
1. HOOK (0-10s): Frase o pregunta que genere curiosidad inmediata
2. INTRO (10-30s): Presentación del canal y adelanto del contenido
3. PUNTOS PRINCIPALES (5-7 puntos de 60-90s cada uno)
4. CONCLUSIÓN (60s): Resumen + reflexión
5. CTA FINAL (20s): Suscribirse, dar like, comentar

REGLAS:
- Voz narrativa, fluida, entretenida
- Transiciones naturales entre secciones
- Anécdotas o ejemplos concretos cuando sea posible
- Generación de misterio y anticipación constante

Responde ÚNICAMENTE con JSON válido (sin markdown):
{{
  "title": "título del video",
  "hook": "texto del hook (10 segundos)",
  "full_script": "guion completo con todas las secciones",
  "segments": [
    {{"time": "0-10s", "text": "hook", "section": "hook"}},
    {{"time": "10-30s", "text": "intro", "section": "intro"}},
    {{"time": "30-600s", "text": "desarrollo", "section": "main"}},
    {{"time": "600-660s", "text": "conclusión", "section": "outro"}}
  ],
  "keywords": ["palabra1", "palabra2", "palabra3", "palabra4", "palabra5", "palabra6"],
  "visual_suggestions": ["sugerencia 1", "sugerencia 2", "sugerencia 3"],
  "voice": "es-MX-DaliaNeural",
  "speech_rate": "+5%",
  "description": "descripción para YouTube (máx 1000 chars)",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8"],
  "estimated_duration_seconds": 600
}}
"""

VOICES_ES = [
    "es-MX-DaliaNeural",      # México - Femenina
    "es-MX-JorgeNeural",      # México - Masculina
    "es-ES-ElviraNeural",     # España - Femenina
    "es-ES-AlvaroNeural",     # España - Masculina
    "es-AR-ElenaNeural",      # Argentina - Femenina
    "es-AR-TomasNeural",      # Argentina - Masculina
    "es-CO-SalomeNeural",     # Colombia - Femenina
    "es-CO-GonzaloNeural",    # Colombia - Masculina
]


class ScriptGenerator:
    """
    Genera guiones completos optimizados para YouTube.
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.channel = os.getenv("CHANNEL_NAME", "El Tío Jota")
        self.default_voice = os.getenv("DEFAULT_VOICE", "es-MX-DaliaNeural")
        self._configure_gemini()

    def _configure_gemini(self):
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                generation_config=genai.GenerationConfig(
                    temperature=0.85,
                    max_output_tokens=4096,
                ),
            )
        else:
            self.model = None
            logger.warning("Sin API Gemini. Usando guión de demo.")

    def generate_full_script(self, trend_data: dict) -> dict:
        """
        Genera el guión completo basado en los datos de tendencia.
        """
        fmt = trend_data.get("format", "Short").lower()
        is_short = "short" in fmt

        prompt_template = SHORT_SCRIPT_PROMPT if is_short else LONG_SCRIPT_PROMPT
        prompt = prompt_template.format(
            topic=trend_data.get("topic", "curiosidades"),
            idea=trend_data.get("idea", ""),
            hook_idea=trend_data.get("hook_idea", ""),
            channel=self.channel,
            audience=trend_data.get("target_audience", "público general"),
        )

        if not self.model:
            return self._get_demo_script(trend_data, is_short)

        try:
            logger.info(f"Generando guion {'Short' if is_short else 'Long'}...")
            response = self.model.generate_content(prompt)
            raw = response.text.strip().replace("```json", "").replace("```", "").strip()

            script_data = json.loads(raw)

            # Normalizar voz según configuración
            if os.getenv("FORCE_VOICE"):
                script_data["voice"] = os.getenv("FORCE_VOICE")
            elif "voice" not in script_data:
                script_data["voice"] = self.default_voice

            # Asegurar que el guion incluya al menos el hook
            if not script_data.get("full_script"):
                script_data["full_script"] = self._build_fallback_script(script_data)

            logger.info(f"Guion generado: {len(script_data['full_script'])} chars")
            return script_data

        except json.JSONDecodeError as e:
            logger.error(f"Error parseando guion JSON: {e}")
            return self._get_demo_script(trend_data, is_short)
        except Exception as e:
            logger.error(f"Error generando guion: {e}")
            return self._get_demo_script(trend_data, is_short)

    def _build_fallback_script(self, script_data: dict) -> str:
        """Construye el guion desde los segmentos si full_script está vacío."""
        parts = []
        for seg in script_data.get("segments", []):
            if seg.get("text"):
                parts.append(seg["text"])
        return " ".join(parts) if parts else script_data.get("hook", "Hola, bienvenido.")

    def clean_script_for_tts(self, script: str) -> str:
        """
        Limpia el texto del guion para mejor pronunciación en TTS.
        """
        # Eliminar emojis y caracteres especiales
        script = re.sub(r'[^\w\s\.,!?¿¡\-:;áéíóúüñÁÉÍÓÚÜÑ]', '', script)
        # Eliminar múltiples espacios
        script = re.sub(r'\s+', ' ', script)
        # Asegurar pausas en puntuación
        script = script.replace('...', '... ')
        script = script.strip()
        return script

    def _get_demo_script(self, trend_data: dict, is_short: bool) -> dict:
        """Script de demo cuando no hay API disponible."""
        topic = trend_data.get("topic", "curiosidades increíbles")
        title = trend_data.get("title", f"Lo que nadie te cuenta sobre {topic}")

        if is_short:
            script = (
                f"Espera, ¿sabías esto sobre {topic}? "
                f"Esto te va a cambiar la forma de verlo todo. "
                f"Número uno: la mayoría de la gente no sabe esto. "
                f"Número dos: cuando lo veas, no vas a poder olvidarlo. "
                f"Número tres: esto ocurre más seguido de lo que crees. "
                f"Si no lo sabías, dale like y síguenos para más datos increíbles. "
                f"Nos vemos en el siguiente video."
            )
            duration = 55
        else:
            script = (
                f"¿Alguna vez te preguntaste la verdad detrás de {topic}? "
                f"Hoy en El Tío Jota te cuento todo lo que nadie te dice. "
                f"Quédate hasta el final porque lo mejor viene después. "
                f"Primero, hablemos del origen de todo esto. "
                f"Esto empezó hace muchos años y pocos lo conocen. "
                f"Segundo, hay datos que te van a sorprender completamente. "
                f"La ciencia dice algo muy diferente a lo que creemos. "
                f"Y tercero, esto tiene un impacto directo en tu vida diaria. "
                f"Si llegaste hasta aquí, dale like y suscríbete para no perderte nada. "
                f"Nos vemos en el próximo video."
            )
            duration = 600

        return {
            "title": title,
            "hook": f"Espera, ¿sabías esto sobre {topic}?",
            "full_script": script,
            "segments": [
                {"time": "0-3s", "text": f"¿Sabías esto sobre {topic}?", "section": "hook"},
                {"time": "3-50s", "text": script, "section": "main"},
                {"time": "50-60s", "text": "Dale like y suscríbete.", "section": "cta"},
            ],
            "keywords": topic.split()[:3] + ["curiosidades", "viral"],
            "visual_suggestions": [f"{topic} background", "data visualization"],
            "voice": self.default_voice,
            "speech_rate": "+10%",
            "description": f"¿Sabías todo sobre {topic}? En este video te lo contamos todo. #shorts #{topic.replace(' ', '')}",
            "tags": ["curiosidades", "viral", "datos", "increíble", topic.replace(" ", "")],
            "estimated_duration_seconds": duration,
        }
