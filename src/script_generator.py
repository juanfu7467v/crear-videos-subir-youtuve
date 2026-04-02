import os
import json
import time
import requests
from typing import Dict, Any, Optional

class ScriptGenerator:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.api_url = "https://api.openai.com/v1/chat/completions"

    def generate_script(self, topic: str, canal: str, categoria: str, format_suggested: str, estilo_base: str, user_prompt_ia: Optional[str] = None) -> Dict[str, Any]:
        """
        Genera un guion optimizado para YouTube utilizando la API de OpenAI.
        """
        
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
            f"Actúa como un experto creador de contenido para YouTube y estratega de viralidad. "  
            f"Tu objetivo es crear un guion para el canal '{canal}' que logre enganchar, emocionar y retener al espectador hasta el último segundo. El guion NO debe ser informativo, sino emocional, intrigante y directo. "  
            f"Para la categoría de películas, los títulos y descripciones deben estar **altamente optimizados para SEO en YouTube**, utilizando frases que la gente busca diariamente. El título debe ser **emocional, intrigante y generar curiosidad**, como si fuera un secreto que el espectador está a punto de descubrir. "  
            f"La descripción debe ser extremadamente corta (MÁXIMO 450 CARACTERES) y seguir EXACTAMENTE este formato de ejemplo:\n\n"  
            "Análisis: [Nombre de la Película] 🎲\n"  
            "¿Dominas el juego o dejas que el miedo te consuma? [Película] no es una película, es una lección de supervivencia para los que no temen al caos. Mientras la masa se distrae, el líder analiza y conquista. Solo los que entienden las reglas del poder sobreviven.\n\n"  
            "🔥 Mírala gratis aquí: 👉 {{PELIPREX_LINK}}\n\n"  
            "💎 Cine exclusivo. Sin anuncios.\n"  
            "👉 https://masitaprex.com/PeliPREX\n\n"  
            "Únete al círculo. El resto solo mira. 🚀\n\n"  
            "REGLA DE ORO: No te extiendas, ve directo a la emoción y usa el bloque de Peliprex tal cual se muestra arriba."  
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
            "Pexels no entiende conceptos abstractos. Usa términos como: 'man thinking', 'city traffic', 'cinematic landscape', 'close up face', 'technology', 'dark room'. "  
            "EVITA términos como 'paradox', 'fate', 'destiny'.\n"  
            "- BÚSQUEDA DE STOCK: Para Archive.org, usa SIEMPRE el nombre real de la película o tema central (ej. 'Rambo', 'The Godfather') para obtener clips relacionados. No uses términos genéricos como 'triste' o 'silueta' para esta fuente.\n"  
            "- DURACIÓN: " + ("Máximo 55 segundos" if "short" in format_suggested else "Entre 3 y 5 minutos") + ".\n\n"  
            "INSTRUCCIÓN ESPECIAL PARA BÚSQUEDA DE CONTENIDO (PeliPREX):\n"  
            "Analiza profundamente el tema del video y extrae únicamente el nombre exacto del contenido principal (película, serie, personaje o tema central).\n"  
            "Ejemplo: si el tema es sobre el multiverso de Spider-Man, el resultado debe ser 'Spider-Man'. Si es sobre Batman, 'Batman'.\n"  
            "No incluyas frases ni descripciones, solo el nombre exacto para buscar clips visuales reales.\n\n"  
            "Responde ÚNICAMENTE con un objeto JSON que contenga:\n"  
            "'title', 'full_script', 'keywords', 'voice', 'description', 'tags', 'prompt_ia', 'estilo_contenido', 'hook', 'estructura', 'segmented_script', 'peliprex_search_term'.\n"  
            f"En 'voice' usa siempre: {voz}.\n"  
            "En 'peliprex_search_term' coloca el nombre exacto del contenido principal identificado para la búsqueda de clips.\n"  
            "Si la categoría es 'películas', la descripción debe incluir un placeholder '{{PELIPREX_LINK}}' donde se insertará el enlace a la película, y el bloque de texto final con los enlaces de Peliprex.\n\n"  
            "Cada objeto en 'segmented_script' debe tener: 'segment_text', 'keywords' (lista de 3-5 términos visuales simples en inglés) and 'estimated_duration'."  
        )  
          
        max_retries = 3  
        retry_delay = 5  
        timeout_seconds = 90  
  
        for attempt in range(max_retries):  
            try:  
                headers = {  
                    "Content-Type": "application/json",  
                    "Authorization": f"Bearer {self.api_key}"  
                }  
  
                data = {  
                    "model": "gpt-4-turbo-preview",  
                    "messages": [  
                        {"role": "system", "content": "Eres un experto en guiones virales para YouTube. Responde siempre en formato JSON."},  
                        {"role": "user", "content": prompt}  
                    ],  
                    "response_format": {"type": "json_object"},  
                    "temperature": 0.7  
                }  
  
                response = requests.post(self.api_url, headers=headers, json=data, timeout=timeout_seconds)  
                response.raise_for_status()  
                  
                result = response.json()  
                content = result['choices'][0]['message']['content']  
                return json.loads(content)  
  
            except Exception as e:  
                print(f"Error en intento {attempt + 1}: {e}")  
                if attempt < max_retries - 1:  
                    time.sleep(retry_delay)  
                else:  
                    raise Exception(f"No se pudo generar el guion después de {max_retries} intentos: {e}")
