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

    def generate_thumbnail(self, script_data: dict, output_path: str, is_short: bool = False) -> Optional[str]:
        """
        Genera una miniatura atractiva usando DALL-E 3 de OpenAI.
        """
        if not self.api_key:
            logger.warning("No se proporcionó OPENAI_API_KEY. No se puede generar la miniatura con IA.")
            return None

        try:
            title = script_data.get('title', 'Curiosidades')
            description = script_data.get('description', '')
            
            # Prompt optimizado para miniaturas virales de YouTube
            # Se enfoca en generar curiosidad, ser llamativo y atraer clics.
            prompt = (
                "Eres un experto en diseño de miniaturas virales de YouTube con alto CTR. "
                f"Crea una miniatura impactante para un video titulado: '{title}'. "
                f"Contexto del video: {description}. "
                "\n\nESTRATEGIA VISUAL REQUERIDA:\n"
                "1. COMPOSICIÓN: Sujeto principal muy grande y expresivo a un lado (regla de tercios). "
                "2. COLORES: Usa colores vibrantes y contrastes agresivos (ej. Amarillo sobre Negro, Rojo sobre Cian). "
                "3. CURIOSIDAD: Debe haber un elemento misterioso, una flecha señalando algo impactante o un objeto fuera de lugar que genere una pregunta inmediata. "
                "4. EMOCIÓN: Si hay rostros, deben mostrar sorpresa extrema, shock o una emoción intensa. "
                "5. TEXTO: Incluye un texto muy corto (máximo 2-3 palabras) en una fuente ultra-bold, muy grande y legible, con borde o sombra para resaltar. "
                "Ejemplos de texto: '¡ES REAL!', 'EL SECRETO', 'NO LO CREERÁS'. "
                "\n\nESPECIFICACIONES TÉCNICAS:\n"
                f"- Formato: {'Vertical (9:16) para YouTube Shorts' if is_short else 'Horizontal (16:9) para YouTube'}.\n"
                "- Estilo: Fotorrealista, 4K, cinematográfico, alta definición.\n"
                "- Evita: Diseños planos, exceso de texto, elementos pequeños difíciles de ver en móviles."
            )

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }

            # DALL-E 3 genera imágenes cuadradas por defecto (1024x1024).
            # Luego las reencuadramos al formato deseado.
            payload = {
                "model": "dall-e-3",
                "prompt": prompt,
                "n": 1,
                "size": "1024x1024",
                "quality": "hd",
                "style": "vivid"
            }

            logger.info(f"Solicitando generación de miniatura a OpenAI para: {title} ({'Short' if is_short else 'Largo'})")
            response = requests.post(self.url, headers=headers, json=payload, timeout=120)
            
            if response.status_code == 200:
                data = response.json()
                image_url = data['data'][0]['url']
                
                # Descargar la imagen generada
                img_response = requests.get(image_url, timeout=30)
                if img_response.status_code == 200:
                    try:
                        img = Image.open(io.BytesIO(img_response.content))
                        
                        # Convertir a RGB si es necesario
                        if img.mode in ("RGBA", "P"):
                            img = img.convert("RGB")

                        # --- AJUSTE DE TAMAÑO EXACTO ---
                        if is_short:
                            target_w, target_h = 1080, 1920
                        else:
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
                            # La imagen es más alta que el objetivo: ajustar por ancho y recortar altura
                            new_w = target_w
                            new_h = int(new_w / img_ratio)
                            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                            top = (new_h - target_h) / 2
                            img = img.crop((0, top, target_w, top + target_h))
                        
                        # Guardar con compresión progresiva para cumplir límite de 2MB de YouTube
                        quality = 85
                        img.save(output_path, "JPEG", quality=quality, optimize=True)
                        
                        file_size = os.path.getsize(output_path)
                        while file_size > 2 * 1024 * 1024 and quality > 30:
                            quality -= 10
                            img.save(output_path, "JPEG", quality=quality, optimize=True)
                            file_size = os.path.getsize(output_path)
                            
                        logger.info(f"Miniatura OpenAI generada ({file_size/1024/1024:.2f}MB): {output_path}")
                        return output_path
                    except Exception as compress_err:
                        logger.error(f"Error procesando miniatura: {compress_err}")
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
