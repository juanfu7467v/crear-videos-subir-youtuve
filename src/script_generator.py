import json
import logging
import re
import requests
import os

logger = logging.getLogger(__name__)

class ScriptGenerator:
    """
    Controlador de generación de contenido mediante la API REST de Gemini.
    Optimizado para evitar errores 404 mediante el uso de modelos de la serie 2.5/3.1.
    """
    def __init__(self, api_key: str):
        self.api_key = api_key.strip()
        # En marzo de 2026, gemini-1.5-flash ya no es el estándar. 
        # Migramos a gemini-2.5-flash o gemini-3.1-flash-lite para asegurar disponibilidad.[span_28](start_span)[span_28](end_span)
        self.model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        
        # Limpieza del nombre del modelo para evitar duplicidad de prefijos en la URL [span_29](start_span)[span_29](end_span)
        clean_model_name = self.model.replace("models/", "")
        
        # URL estructurada según especificaciones de Google AI Studio v1beta [span_30](start_span)[span_30](end_span)
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/{clean_model_name}:generateContent?key={self.api_key}"

    def generate_full_script(self, trend_data: dict) -> dict:
        topic = trend_data.get('topic', 'curiosidades interesantes')
        
        # El prompt se ha refinado para aprovechar las capacidades de razonamiento de los modelos 2.5+
        prompt = (
            f"Actúa como un productor senior de YouTube para el canal 'El Tío Jota'. "
            f"Crea un guion de video corto (Short) sobre: '{topic}'. "
            "Requisitos técnicos obligatorios: "
            "1. Duración: 60 segundos de lectura (aprox. 160 palabras). "
            "2. Estructura: Hook inicial impactante, 3 datos curiosos y cierre con CTA. "
            "3. Formato: Devuelve ÚNICAMENTE un objeto JSON puro. Sin markdown, sin texto extra. "
            "Esquema JSON: { "
            "\"title\": \"título\", \"full_script\": \"guion detallado\", "
            "\"keywords\": \"palabras clave\", \"voice\": \"random\", "
            "\"description\": \"descripción SEO\", \"tags\": \"etiquetas\" "
            "}"
        )
        
        try:
            # Configuración de generación para forzar salida JSON y controlar la creatividad
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "response_mime_type": "application/json", # Característica de v1beta para JSON estable 
         [span_27](start_span)[span_27](end_span)           "temperature": 0.75,
                    "topP": 0.95,
                    "maxOutputTokens": 1024
                }
            }
            
            response = requests.post(self.url, json=payload, timeout=50)
            
            if response.status_code!= 200:
                logger.error(f"Error crítico en Gemini API {response.status_code}: {response.text}")
                # Manejo específico del error 404 para alertar sobre obsolescencia del modelo
                if response.status_code == 404:
                    logger.warning("El modelo especificado ha sido retirado o la URL es incorrecta.")
                return self._get_fallback(topic)

            data = respo[span_4](start_span)[span_4](end_span)nse.json()
            
            # Extracción segura del contenido generado [span_31](start_span)[span_31](end_span)
            if 'candidates' in data and len(data['candidates']) > 0:
                text_response = data['candidates']['content']['parts']['text']
                
                # Limpieza de posibles residuos de formato markdown que el modelo pudiera añadir
                cleaned_text = re.sub(r'^```json\s*|\s*```$', '', text_response.strip(), flags=re.MULTILINE)
                
                try:
                    return json.loads(cleaned_text)
                except json.JSONDecodeError:
                    logger.error("Fallo al decodificar la respuesta JSON de la IA.")
                    return self._get_fallback(topic)
            else:
                logger.error("La API no devolvió candidatos válidos.")
                return self._get_fallback(topic)
            
        except Exception as e:
            logger.error(f"Excepción en la generación con Gemini: {e}")
            return self._get_fallback(topic)

    def _get_fallback(self, topic: str):
        """Genera un guion de emergencia para evitar la detención del pipeline."""
        return {
            "title": f"Misterios de {topic}", 
            "full_script": (
                f"¡Bienvenidos a El Tío Jota! ¿Sabías que {topic} esconde secretos fascinantes? "
                "Hoy desglosamos los datos más increíbles que te dejarán pensando todo el día. "
                "Desde su origen hasta las curiosidades más extrañas, te lo contamos todo en 60 segundos. "
                "No olvides suscribirte para más contenido diario."
            ), 
            "voice": "random", 
            "keywords": f"{topic}, viral, datos curiosos, aprendizaje", 
            "description": f"Descubre los secretos de {topic} en este video exclusivo de El Tío Jota.", 
            "tags": "curiosidades, viral, shorts, eltiojota, educativo"
        }
