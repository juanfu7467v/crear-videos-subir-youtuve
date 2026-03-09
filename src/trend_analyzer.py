"""
trend_analyzer.py
─────────────────
Analiza tendencias actuales y recomienda temas para videos.
Usa Gemini + búsqueda web para detectar lo que está viral.
"""

import json
import logging
import os
from datetime import datetime
import google.generativeai as genai

logger = logging.getLogger(__name__)


TREND_PROMPT = """
Eres un experto en marketing de contenido digital y análisis de tendencias para YouTube en el mercado hispanohablante.

Fecha actual: {date}
Canal: {channel}

Tu tarea es analizar las tendencias ACTUALES de Internet, YouTube, TikTok y redes sociales en español y recomendar el MEJOR tema para crear un video corto hoy.

Considera:
1. Tendencias virales en redes sociales (memes, noticias, eventos)
2. Temas de entretenimiento, curiosidades, humor o vida cotidiana
3. Búsquedas trending en Google en países hispanohablantes
4. Estacionalidad (qué le interesa a la gente HOY específicamente)
5. Potencial de viralidad y retención del espectador

Responde ÚNICAMENTE con un objeto JSON válido (sin markdown, sin texto extra) con esta estructura exacta:
{{
  "topic": "tema principal del video en 1 línea",
  "title": "título atractivo para YouTube (máx 60 chars)",
  "idea": "descripción de la idea del video en 2-3 oraciones",
  "format": "Short o Long",
  "publish_time": "HH:MM",
  "target_audience": "descripción del público objetivo",
  "why_trending": "por qué este tema es tendencia ahora",
  "hook_idea": "idea para el gancho inicial de 3 segundos",
  "thumbnail_concept": "concepto visual para la miniatura",
  "estimated_views": "estimado de vistas en 24h (ej: 1000-5000)",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
  "category": "Entretenimiento/Educación/Humor/Noticias/Lifestyle"
}}
"""

FALLBACK_TOPICS = [
    {
        "topic": "5 curiosidades que NO sabías sobre el café",
        "title": "5 Cosas Increíbles del Café que NO Sabías 🤯",
        "idea": "Video sobre datos sorprendentes del café que la mayoría desconoce.",
        "format": "Short",
        "publish_time": "18:00",
        "target_audience": "Adultos 18-35, amantes del café",
        "why_trending": "El café es siempre un tema popular y universal",
        "hook_idea": "¿Sabías que el café puede salvarte la vida? Mira esto...",
        "thumbnail_concept": "Taza de café humeante con texto amarillo sobre fondo negro",
        "estimated_views": "2000-8000",
        "tags": ["café", "curiosidades", "datos", "viral", "shorts"],
        "category": "Entretenimiento"
    },
    {
        "topic": "Trucos psicológicos que usan las tiendas para hacerte gastar más",
        "title": "Así te Engañan las Tiendas Para que Gastes Más 💸",
        "idea": "Revelar las técnicas de manipulación psicológica que usan los supermercados.",
        "format": "Short",
        "publish_time": "19:00",
        "target_audience": "Adultos 20-45 interesados en psicología y economía",
        "why_trending": "Contenido que genera indignación y compartición",
        "hook_idea": "Las tiendas te manipulan todos los días y no lo sabes...",
        "thumbnail_concept": "Carrito de supermercado lleno con dinero saliendo",
        "estimated_views": "5000-20000",
        "tags": ["psicología", "dinero", "trucos", "consumo", "viral"],
        "category": "Educación"
    }
]


class TrendAnalyzer:
    """
    Analiza tendencias y devuelve el mejor tema para un video.
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.channel = os.getenv("CHANNEL_NAME", "El Tío Jota")
        self._configure_gemini()

    def _configure_gemini(self):
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                generation_config=genai.GenerationConfig(
                    temperature=0.9,
                    max_output_tokens=1024,
                ),
            )
        else:
            self.model = None
            logger.warning("GEMINI_API_KEY no configurada. Usando temas de respaldo.")

    def get_trending_content(self) -> dict:
        """
        Consulta Gemini para obtener el tema trending del momento.
        Retorna un dict con toda la información del video.
        """
        if not self.model:
            return self._get_fallback_topic()

        prompt = TREND_PROMPT.format(
            date=datetime.now().strftime("%A, %d de %B de %Y, %H:%M"),
            channel=self.channel,
        )

        try:
            logger.info("Consultando Gemini para análisis de tendencias...")
            response = self.model.generate_content(prompt)
            raw = response.text.strip()

            # Limpiar posibles bloques markdown
            raw = raw.replace("```json", "").replace("```", "").strip()

            trend_data = json.loads(raw)
            logger.info(f"Tema obtenido: {trend_data.get('topic', 'desconocido')}")
            return trend_data

        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON de Gemini: {e}")
            logger.debug(f"Respuesta cruda: {raw[:500]}")
            return self._get_fallback_topic()

        except Exception as e:
            logger.error(f"Error en Gemini trend analysis: {e}")
            return self._get_fallback_topic()

    def _get_fallback_topic(self) -> dict:
        """Retorna un tema de respaldo si Gemini falla."""
        import random
        topic = random.choice(FALLBACK_TOPICS)
        logger.info(f"Usando tema de respaldo: {topic['topic']}")
        return topic

    def get_multiple_options(self, count: int = 3) -> list:
        """
        Genera múltiples opciones de temas para elegir el mejor.
        """
        if not self.model:
            import random
            return random.sample(FALLBACK_TOPICS, min(count, len(FALLBACK_TOPICS)))

        prompt = f"""
Genera {count} ideas DIFERENTES de videos trending para YouTube en español.
Fecha: {datetime.now().strftime("%d/%m/%Y")}
Canal: {self.channel}

Responde con un array JSON de {count} objetos, cada uno con las mismas claves del formato anterior.
Solo JSON válido, sin markdown.
"""
        try:
            response = self.model.generate_content(prompt)
            raw = response.text.strip().replace("```json", "").replace("```", "").strip()
            options = json.loads(raw)
            return options if isinstance(options, list) else [options]
        except Exception as e:
            logger.error(f"Error obteniendo múltiples opciones: {e}")
            return FALLBACK_TOPICS[:count]
