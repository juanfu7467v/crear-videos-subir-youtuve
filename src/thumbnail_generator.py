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

            # Prompt optimizado para miniaturas virales de YouTube
            prompt = (
                f"Create a high-quality, professional YouTube thumbnail for a video titled: '{title}'. "
                f"Visual elements to include: {keywords}. "
                "Style: Cinematic, ultra-realistic, vibrant colors, high contrast, "
                "dramatic lighting, 8k resolution, centered composition, "
                "generating intense curiosity and mystery. "
                "IMPORTANT: No text, no letters, no words in the image. Just a powerful visual scene."
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
