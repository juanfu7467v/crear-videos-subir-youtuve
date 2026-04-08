import logging
import os
import requests
from pathlib import Path
from typing import Optional
from PIL import Image
import io

logger = logging.getLogger(__name__)

class ThumbnailGenerator:
    """
    Generador de miniaturas independiente utilizando la API de OpenAI (DALL-E 3).
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.url = "https://api.openai.com/v1/images/generations"

    def generate_thumbnail(self, script_data: dict, output_path: str) -> Optional[str]:
        """
        Genera una miniatura atractiva usando DALL-E 3 de OpenAI.
        """
        if not self.api_key:
            logger.warning("No se proporcionó OPENAI_API_KEY. No se puede generar la miniatura con IA.")
            return None

        try:
            title = script_data.get('title', 'Curiosidades')
            keywords = script_data.get('keywords', '')
            if isinstance(keywords, list):
                keywords = ", ".join(keywords)

            # Prompt optimizado para miniaturas virales de YouTube (Mejorado)
            description = script_data.get('description', '')
            prompt = (
                "Actúa como un psicólogo de masas y experto en CTR de YouTube con más de 50 canales millonarios. "
                "Crea una miniatura de alto impacto diseñada para la 'parada de pulgar' instantánea. "
                f"Basado en esta descripción: {description}. "
                "🔥 ESTRATEGIA DE MANIPULACIÓN VISUAL: "
                "1. COMPOSICIÓN: Aplica la regla de tercios con un sujeto dominante a un lado. El fondo debe contar una historia de misterio o caos. "
                "2. PSICOLOGÍA DEL COLOR: Usa contrastes agresivos de 'Poder y Peligro' (Amarillo/Negro, Rojo/Cian, Neón/Oscuridad profunda). Saturación al máximo. "
                "3. EMOCIÓN PRIMAL: Si hay rostros, deben mostrar un shock extremo, miedo o una sonrisa maliciosa. Si son objetos, deben verse prohibidos o legendarios. "
                "4. GATILLO DE CURIOSIDAD: Crea un 'espacio vacío' mental. Algo debe estar roto, brillando o siendo señalado para que el espectador necesite la respuesta. "
                "👁️ REQUISITOS TÉCNICOS DE ÉLITE: "
                "Texto: Máximo 3 palabras. Fuente 'Ultra-Bold'. Legibilidad perfecta en móviles (20% del tamaño de pantalla). "
                "Ejemplos de texto: 'ESTÁN MINTIENDO', 'EL FIN.', 'NADIE VIO ESTO'. "
                "Iluminación: Estilo cinematográfico oscuro (Rim lighting) con sombras dramáticas que den profundidad 3D. "
                "📐 FORMATO: 1280 x 720 px, Relación 16:9, Calidad 4K fotorrealista. "
                "🚀 OBJETIVO FINAL: El usuario debe sentir que si no hace clic, se está perdiendo el secreto más grande de su vida. "
                "⚠️ PROHIBICIÓN: Cero diseños planos. Prohibido el estilo corporativo. Evitar elementos genéricos. Prioriza la tensión visual."
            )

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }

            payload = {
                "model": "dall-e-3",
                "prompt": prompt,
                "n": 1,
                "size": "1024x1024", # DALL-E 3 genera 1024x1024 por defecto, luego se puede reencuadrar o usar así
                "quality": "hd",
                "style": "vivid"
            }

            logger.info(f"Solicitando generación de miniatura a OpenAI para: {title}")
            response = requests.post(self.url, headers=headers, json=payload, timeout=90)
            
            if response.status_code == 200:
                data = response.json()
                image_url = data['data'][0]['url']
                
                # Descargar la imagen generada
                img_response = requests.get(image_url, timeout=30)
                if img_response.status_code == 200:
                    # Comprimir la imagen para asegurar que pese menos de 2MB (límite de YouTube)
                    try:
                        img = Image.open(io.BytesIO(img_response.content))
                        
                        # Convertir a RGB si es necesario (DALL-E suele devolver PNG o WEBP que pueden ser RGBA)
                        if img.mode in ("RGBA", "P"):
                            img = img.convert("RGB")

                        # --- AJUSTE DE TAMAÑO EXACTO 1280x720 (16:9) ---
                        target_w, target_h = 1280, 720
                        target_ratio = target_w / target_h
                        img_w, img_h = img.size
                        img_ratio = img_w / img_h

                        if img_ratio > target_ratio:
                            # La imagen es más ancha que el objetivo: ajustar por altura y recortar ancho
                            new_h = target_h
                            new_w = int(new_h * img_ratio)
                            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                            left = (new_w - target_w) / 2
                            img = img.crop((left, 0, left + target_w, target_h))
                        else:
                            # La imagen es más alta que el objetivo (o igual): ajustar por ancho y recortar altura
                            new_w = target_w
                            new_h = int(new_w / img_ratio)
                            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                            top = (new_h - target_h) / 2
                            img = img.crop((0, top, target_w, top + target_h))
                        
                        # Guardar con compresión progresiva
                        quality = 85
                        img.save(output_path, "JPEG", quality=quality, optimize=True)
                        
                        # Verificar tamaño y re-comprimir si es necesario
                        file_size = os.path.getsize(output_path)
                        while file_size > 2 * 1024 * 1024 and quality > 30:
                            quality -= 10
                            img.save(output_path, "JPEG", quality=quality, optimize=True)
                            file_size = os.path.getsize(output_path)
                            
                        logger.info(f"Miniatura OpenAI generada y comprimida ({file_size/1024/1024:.2f}MB, calidad {quality}): {output_path}")
                        return output_path
                    except Exception as compress_err:
                        logger.error(f"Error comprimiendo miniatura: {compress_err}. Guardando original...")
                        with open(output_path, "wb") as f:
                            f.write(img_response.content)
                        return output_path
                else:
                    logger.error(f"Error descargando la imagen de OpenAI: {img_response.status_code}")
            else:
                logger.error(f"Error en la API de OpenAI (Status: {response.status_code}): {response.text}")
            
            return None
        except Exception as e:
            logger.error(f"Excepción generando miniatura con OpenAI: {e}")
            return None
