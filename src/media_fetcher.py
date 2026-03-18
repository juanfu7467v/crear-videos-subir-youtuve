import logging
import os
import random
import time
import subprocess
import json
from pathlib import Path
from typing import Optional
import requests
from src.movie_clips_fetcher import MovieClipsFetcher

logger = logging.getLogger(__name__)

def process_keywords(keywords_data):
    """
    Procesa las palabras clave asegurando que el resultado sea siempre una lista de strings.
    Acepta tanto una lista de strings como una cadena separada por comas.
    """
    if not keywords_data:
        return []
    
    if isinstance(keywords_data, list):
        # Si ya es una lista, nos aseguramos de que todos los elementos sean strings y no estén vacíos
        return [str(kw).strip() for kw in keywords_data if str(kw).strip()]
    
    if isinstance(keywords_data, str):
        # Si es un string, lo dividimos por comas o ", "
        # Reemplazamos ", " por "," para normalizar
        normalized = keywords_data.replace(", ", ",")
        return [kw.strip() for kw in normalized.split(",") if kw.strip()]
    
    # Para cualquier otro tipo, intentamos convertir a string y procesar, o devolvemos lista vacía
    try:
        str_data = str(keywords_data)
        normalized = str_data.replace(", ", ",")
        return [kw.strip() for kw in normalized.split(",") if kw.strip()]
    except Exception:
        return []

PEXELS_BASE   = "https://api.pexels.com"
PIXABAY_BASE  = "https://pixabay.com/api"
POLLINATIONS  = "https://image.pollinations.ai/prompt"

class MediaFetcher:
    def __init__(self, pexels_key: str, pixabay_key: str):
        self.pexels_key  = pexels_key
        self.pixabay_key = pixabay_key
        self.movie_clips_fetcher = MovieClipsFetcher()
        self.session     = requests.Session()
        self.session.headers.update({"User-Agent": "ElTioJota-AutoVideo/1.0"})

    def fetch_media_for_video(
        self,
        segmented_script: list,
        target_duration: int,
        save_dir: str,
        video_id: str,
        prefer_video: bool = True,
        is_short: bool = True,
        categoria: Optional[str] = None
    ) -> list:
        save_dir = Path(save_dir) / video_id
        save_dir.mkdir(parents=True, exist_ok=True)

        media_list = []
        total_clips_needed = len(segmented_script)

        format_label = "Short" if is_short else "Largo"
        logger.info(f"Buscando {total_clips_needed} clips para {target_duration}s de video ({format_label}) basado en el script segmentado.")
        
        for i, segment in enumerate(segmented_script):
            segment_keywords = process_keywords(segment.get("keywords", ""))
            segment_duration = segment.get("estimated_duration", 5)
            segment_text = segment.get("segment_text", "")

            if not segment_keywords or segment_keywords == ['']:
                logger.warning(f"Segmento {i+1} sin palabras clave. Saltando.")
                continue
            
            kw = random.choice(segment_keywords)
            logger.info(f"Buscando media para segmento {i+1} (duración {segment_duration}s) con palabra clave: {kw}")

            try:
                media_item = None
                orientation = "portrait" if is_short else "landscape"

                if categoria and "películas" in categoria.lower():
                    movie_title = segment_text.split(" ")[0] if segment_text else video_id
                    movie_clips = self.movie_clips_fetcher.fetch_movie_clips(movie_title, save_dir, 1)
                    if movie_clips:
                        media_item = movie_clips[0]
                        logger.info(f"✓ Se obtuvo clip real de película para segmento {i+1}.")

                if not media_item:
                    if prefer_video and self.pexels_key:
                        media_item = self._fetch_pexels_video(kw, save_dir, f"clip_{i:03d}", orientation)
                    
                    if not media_item and self.pixabay_key:
                        media_item = self._fetch_pixabay_video(kw, save_dir, f"clip_{i:03d}")
                
                if not media_item:
                    media_item = self._fetch_pollinations_image(kw, save_dir, f"ai_{i:03d}", is_short)

                if not media_item and self.pexels_key:
                    media_item = self._fetch_pexels_image(kw, save_dir, f"img_{i:03d}", orientation)

                if media_item:
                    media_item["segment_duration"] = segment_duration
                    media_list.append(media_item)
                    media_path = media_item['path']
                    logger.debug(f"  [{i+1}/{total_clips_needed}] ✓ {kw}: {media_path}")

                time.sleep(0.2)

            except Exception as e:
                logger.warning(f"Error descargando media para '{kw}' en segmento {i+1}: {e}")
                continue

        if not media_list:
            logger.warning("No se pudo descargar ningún media. Generando imágenes AI de fallback...")
            for i, segment in enumerate(segmented_script[:5]):
                kw_fallback = random.choice(process_keywords(segment.get("keywords", "fallback")))
                item = self._fetch_pollinations_image(kw_fallback, save_dir, f"fallback_{i}", is_short)
                if item:
                    item["segment_duration"] = segment.get("estimated_duration", 5)
                    media_list.append(item)

        logger.info(f"Media total descargada: {len(media_list)} elementos")
        return media_list

    def _fetch_pexels_video(self, keyword: str, save_dir: Path, prefix: str, orientation: str = "portrait") -> Optional[dict]:
        if not self.pexels_key: return None
        try:
            url = f"{PEXELS_BASE}/videos/search"
            params = {"query": keyword, "per_page": 15, "orientation": orientation, "size": "medium"}
            headers = {"Authorization": self.pexels_key}
            resp = self.session.get(url, params=params, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            videos = data.get("videos", [])
            if not videos:
                params["orientation"] = "landscape"
                resp = self.session.get(url, params=params, headers=headers, timeout=15)
                videos = resp.json().get("videos", [])
            if not videos: return None
            video = random.choice(videos[:5])
            video_files = sorted(video.get("video_files", []), key=lambda x: x.get("width", 0))
            target = next((f for f in video_files if f.get("width", 0) <= 1280 and f.get("height", 0) >= 480), video_files[0] if video_files else None)
            if not target: return None
            video_url = target["link"]
            filename = save_dir / f"{prefix}_pexels.mp4"
            if self._download_file(video_url, str(filename)):
                return {"path": str(filename), "type": "video", "duration": video.get("duration", 8), "keyword": keyword, "source": "pexels", "width": target.get("width", 1280), "height": target.get("height", 720)}
            return None
        except Exception as e:
            logger.debug(f"Pexels video error para '{keyword}': {e}")
            return None

    def _fetch_pexels_image(self, keyword: str, save_dir: Path, prefix: str, orientation: str = "portrait") -> Optional[dict]:
        if not self.pexels_key: return None
        try:
            url = f"{PEXELS_BASE}/v1/search"
            params = {"query": keyword, "per_page": 10, "orientation": orientation}
            headers = {"Authorization": self.pexels_key}
            resp = self.session.get(url, params=params, headers=headers, timeout=15)
            resp.raise_for_status()
            photos = resp.json().get("photos", [])
            if not photos: return None
            photo = random.choice(photos[:5])
            img_url = photo.get("src", {}).get("large", photo.get("src", {}).get("original"))
            if not img_url: return None
            filename = save_dir / f"{prefix}_pexels.jpg"
            if self._download_file(img_url, str(filename)):
                return {"path": str(filename), "type": "image", "duration": 5, "keyword": keyword, "source": "pexels", "width": photo.get("width", 1080), "height": photo.get("height", 1920)}
            return None
        except Exception as e:
            logger.debug(f"Pexels image error para '{keyword}': {e}")
            return None

    def _fetch_pixabay_video(self, keyword: str, save_dir: Path, prefix: str) -> Optional[dict]:
        if not self.pixabay_key: return None
        try:
            params = {"key": self.pixabay_key, "q": keyword, "video_type": "film", "per_page": 10, "safesearch": "true", "lang": "es"}
            resp = self.session.get(f"{PIXABAY_BASE}/videos/", params=params, timeout=15)
            resp.raise_for_status()
            hits = resp.json().get("hits", [])
            if not hits:
                params["lang"] = "en"
                resp = self.session.get(f"{PIXABAY_BASE}/videos/", params=params, timeout=15)
                hits = resp.json().get("hits", [])
            if not hits: return None
            hit = random.choice(hits[:5])
            videos = hit.get("videos", {})
            vid = videos.get("medium") or videos.get("small") or videos.get("large")
            if not vid or not vid.get("url"): return None
            filename = save_dir / f"{prefix}_pixabay.mp4"
            if self._download_file(vid["url"], str(filename)):
                return {"path": str(filename), "type": "video", "duration": hit.get("duration", 8), "keyword": keyword, "source": "pixabay", "width": vid.get("width", 1280), "height": vid.get("height", 720)}
            return None
        except Exception as e:
            logger.debug(f"Pixabay video error para '{keyword}': {e}")
            return None

    def _fetch_pollinations_image(self, keyword: str, save_dir: Path, prefix: str, is_short: bool) -> Optional[dict]:
        try:
            w, h = (1080, 1920) if is_short else (1920, 1080)
            encoded_kw = requests.utils.quote(keyword)
            url = f"{POLLINATIONS}/{encoded_kw}?width={w}&height={h}&model=flux&nologo=true"
            filename = save_dir / f"{prefix}_ai.jpg"
            if self._download_file(url, str(filename)):
                return {"path": str(filename), "type": "image", "duration": 5, "keyword": keyword, "source": "pollinations", "width": w, "height": h}
            return None
        except Exception as e:
            logger.debug(f"AI Image error para '{keyword}': {e}")
            return None

    def _validate_video(self, path: str) -> bool:
        """
        Valida que el video no esté corrupto usando ffprobe.
        """
        if not path.endswith(('.mp4', '.mov', '.avi')):
            return True # Asumimos que imágenes son válidas si pasaron el check de tamaño
            
        try:
            cmd = [
                'ffprobe', 
                '-v', 'error', 
                '-show_entries', 'format=duration', 
                '-of', 'default=noprint_wrappers=1:nokey=1', 
                path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                logger.warning(f"ffprobe detectó error en {path}: {result.stderr}")
                return False
            
            duration = float(result.stdout.strip())
            if duration <= 0:
                logger.warning(f"Video con duración cero detectado: {path}")
                return False
                
            return True
        except Exception as e:
            logger.warning(f"Error validando video {path} con ffprobe: {e}")
            return False

    def _download_file(self, url: str, path: str) -> bool:
        """
        Descarga un archivo y valida que no esté vacío o corrupto.
        Retorna True si la descarga fue exitosa y válida.
        """
        try:
            resp = self.session.get(url, stream=True, timeout=30)
            resp.raise_for_status()
            
            with open(path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            # 1. Validación básica: tamaño de archivo
            file_size = os.path.getsize(path)
            if file_size < 1024:  # Menos de 1KB es sospechoso
                logger.warning(f"Archivo descargado demasiado pequeño ({file_size} bytes): {path}")
                if os.path.exists(path): os.remove(path)
                return False
            
            # 2. Validación avanzada para videos: ffprobe
            if not self._validate_video(path):
                logger.warning(f"Video corrupto detectado por ffprobe: {path}")
                if os.path.exists(path): os.remove(path)
                return False
                
            return True
        except Exception as e:
            logger.error(f"Error descargando {url}: {e}")
            if os.path.exists(path):
                os.remove(path)
            return False

    def generate_thumbnail(self, topic: str, title: str, output_path: str, categoria: str = "general") -> bool:
        try:
            w, h = (1280, 720)
            prompt = f"YouTube Thumbnail for video about {topic}, title: {title}, cinematic, high quality, professional"
            encoded_prompt = requests.utils.quote(prompt)
            url = f"{POLLINATIONS}/{encoded_prompt}?width={w}&height={h}&model=flux&nologo=true"
            self._download_file(url, output_path)
            return True
        except Exception as e:
            logger.error(f"Error generando miniatura: {e}")
            return False
