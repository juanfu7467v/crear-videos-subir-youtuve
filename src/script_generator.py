import json
import logging
import re
import requests
import os

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
        
        # Definir estilo según el canal y categoría
        if "Criterio" in canal or "películas" in categoria:
            estilo = "serio, analítico, profesional y directo. Enfocado en la verdad y el análisis crítico."
            voz = "es-MX-JorgeNeural" # Voz masculina más seria
        else:
            estilo = "entusiasta, curioso, cercano y muy dinámico. Enfocado en sorprender al espectador con datos increíbles."
            voz = "es-MX-DaliaNeural" # Voz femenina carismática

        # MEJORA: Prompt ultra-detallado para coherencia, SEO y viralidad
        prompt = (
            f"Actúa como un experto guionista y estratega de YouTube. Crea un guion para el canal '{canal}'.\n"
            f"Tema: {topic}\n"
            f"Categoría: {categoria}\n"
            f"Estilo: {estilo}\n\n"
            "REQUISITOS DEL CONTENIDO:\n"
            "1. IDIOMA: Todo el contenido DEBE estar en ESPAÑOL CLARO, NATURAL Y FÁCIL DE ENTENDER. Evita tecnicismos innecesarios o frases complejas.\n"
            "2. TÍTULO: Debe ser irresistible, llamativo, creativo y divertido. Diseñado para captar la atención desde el inicio (Clickbait honesto).\n"
            "3. DESCRIPCIÓN: Atractiva, incluye un resumen que genere curiosidad, usa emojis de forma profesional y llamados a la acción.\n"
            "4. HOOK (0-3s): Empieza con una pregunta o dato impactante que obligue a seguir viendo.\n"
            "5. DESARROLLO: Narración fluida, sin rellenos, manteniendo la tensión o el interés. Usa frases cortas y directas para una mejor dicción del narrador.\n"
            "6. CIERRE: Un llamado a la acción rápido integrado en la narrativa.\n"
            "7. LIMPIEZA: No uses símbolos como (*, _, -, #) dentro del 'full_script'. No incluyas acotaciones de escena ni nombres de personajes antes de sus diálogos.\n"
            "8. COHERENCIA VISUAL: El campo 'keywords' debe contener 8-10 términos descriptivos en inglés "
            "separados por comas que representen visualmente lo que se narra. Si es de películas, incluye nombres de personajes o escenas clave.\n\n"
            "Responde SOLO un JSON con: 'title', 'full_script', 'keywords', 'voice', 'description', 'tags'.\n"
            f"En 'voice' usa: {voz}."
        )
        
        try:
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"response_mime_type": "application/json"}
            }
            
            response = requests.post(self.url, json=payload, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"Error API {response.status_code}: {response.text}")
                return self._get_fallback()

            data = response.json()
            text_response = data['candidates'][0]['content']['parts'][0]['text']
            
            raw = re.search(r'\{.*\}', text_response, re.DOTALL)
            data = json.loads(raw.group(0)) if raw else json.loads(text_response)

            # Corregir CHANNEL_NAME en el guion si es necesario
            if 'full_script' in data:
                real_name = "El Tío Jota"
                if canal and "Criterio" in canal:
                    real_name = "El Criterio"
                
                # Reemplazar CHANNEL_NAME, CHANNEL_NAME_2 y variaciones comunes
                data['full_script'] = data['full_script'].replace("CHANNEL_NAME_2", real_name)
                data['full_script'] = data['full_script'].replace("CHANNEL_NAME", real_name)
            
            return data
            
        except Exception as e:
            logger.error(f"Error crítico en la generación con Gemini: {e}")
            return self._get_fallback()

    def _get_fallback(self):
        """Devuelve una estructura válida si la API falla para no romper el pipeline."""
        return {
            "title": "Misterios Increíbles", 
            "full_script": "¡Detente! ¿Sabías que lo que estás a punto de ver cambiará tu forma de pensar? Bienvenidos a El Tío Jota, hoy exploramos un tema fascinante.", 
            "voice": "random", 
            "keywords": "misterio, viral, curiosidades", 
            "description": "Explorando misterios con El Tío Jota.", 
            "tags": "misterio, viral, curiosidades, shorts"
        }
