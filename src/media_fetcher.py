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
from src.youtube_downloader import YouTubeDownloader

logger = logging.getLogger(__name__)

def process_keywords(keywords_data):
    """
    Procesa las palabras clave asegurando que el resultado sea siempre una lista de strings.
    """
    if not keywords_data:
        return []
    
    if isinstance(keywords_data, list):
        return [str(kw).strip() for kw in keywords_data if str(kw).strip()]
    
    if isinstance(keywords_data, str):
        normalized = keywords_data.replace(", ", ",")
        return [kw.strip() for kw in normalized.split(",") if kw.strip()]
    
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
    def __init__(self, pexels_key: str, pixabay_key: str, youtube_key: str = None):
        self.pexels_key  = pexels_key
        self.pixabay_key = pixabay_key
        self.youtube_key = youtube_key or os.getenv("YOUTUBE_API_KEY")
        self.movie_clips_fetcher = MovieClipsFetcher()
        self.youtube_downloader = YouTubeDownloader(api_key=self.youtube_key)
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
        
        # Obtener clips reales de la película (trailers)
        movie_clips = []
        # Si no hay categoría explícita, intentamos deducir si es sobre una película por el video_id
        # o simplemente usamos la nueva lógica de trailers para mayor calidad visual
        movie_title = video_id
        if segmented_script and segmented_script[0].get("segment_text"):
            first_text = segmented_script[0].get("segment_text", "")
            movie_title = " ".join(first_text.split()[:3])
        
        # Intentar obtener trailers de YouTube (Paso A y B de la solución)
        logger.info(f"Intentando obtener trailers de YouTube para: {movie_title}")
        movie_clips = self.youtube_downloader.fetch_trailer_clips(movie_title, save_dir, total_clips_needed // 2 + 1)
        
        if not movie_clips and categoria and "películas" in categoria.lower():
            # Fallback al fetcher original si YouTube falla y es explícitamente de películas
            movie_clips = self.movie_clips_fetcher.fetch_movie_clips(movie_title, save_dir, total_clips_needed // 2 + 1)
        
        logger.info(f"Se obtuvieron {len(movie_clips)} clips de trailer/película para alternar.")

        for i, segment in enumerate(segmented_script):
            segment_keywords = process_keywords(segment.get("keywords", ""))
            segment_duration = segment.get("estimated_duration", 5)
            
            # Alternar entre clip real y clip de stock/AI
            # Estructura: Clip A (Real), Clip B (Stock), Clip C (Real), Clip D (Stock)...
            media_item = None
            orientation = "portrait" if is_short else "landscape"

            # Intentar usar un clip real si toca y hay disponibles
            if i % 2 == 0 and movie_clips:
                media_item = movie_clips.pop(0)
                logger.info(f"Segmento {i+1}: Usando clip real de película.")
            
            # Si no hay clip real o toca stock, buscar en Pexels/Pixabay
            if not media_item:
                if not segment_keywords or segment_keywords == ['']:
                    kw = "cinematic"
                else:
                    kw = random.choice(segment_keywords)
                
                logger.info(f"Segmento {i+1}: Buscando clip de stock para '{kw}'")
                
                if prefer_video and self.pexels_key:
                    media_item = self._fetch_pexels_video(kw, save_dir, f"clip_{i:03d}", orientation)
                
                if not media_item and self.pixabay_key:
                    media_item = self._fetch_pixabay_video(kw, save_dir, f"clip_{i:03d}")
                
                if not media_item:
                    media_item = self._fetch_pollinations_image(kw, save_dir, f"ai_{i:03d}", is_short)

            if media_item:
                media_item["segment_duration"] = segment_duration
                media_list.append(media_item)
                logger.debug(f"  [{i+1}/{total_clips_needed}] ✓ {media_item.get('keyword', 'N/A')}: {media_item['path']}")

            time.sleep(0.1)

        if not media_list:
            logger.warning("No se pudo descargar ningún media. Generando imágenes AI de fallback...")
            for i, segment in enumerate(segmented_script[:5]):
                kw_fallback = "cinematic movie scene"
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
                return {"path": str(filename), "type": "video", "duration": video.get("duration", 10), "keyword": keyword, "source": "pexels", "width": target.get("width", 1280), "height": target.get("height", 720)}
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
                return {"path": str(filename), "type": "video", "duration": hit.get("duration", 10), "keyword": keyword, "source": "pixabay", "width": vid.get("width", 1280), "height": vid.get("height", 720)}
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
        if not path.endswith(('.mp4', '.mov', '.avi')):
            return True
            
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
                return False
            
            duration = float(result.stdout.strip())
            if duration <= 0:
                return False
                
            return True
        except Exception as e:
            return False

    def _download_file(self, url: str, path: str) -> bool:
        try:
            resp = self.session.get(url, stream=True, timeout=30)
            resp.raise_for_status()
            
            with open(path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            file_size = os.path.getsize(path)
            if file_size < 1024:
                if os.path.exists(path): os.remove(path)
                return False
            
            if not self._validate_video(path):
                if os.path.exists(path): os.remove(path)
                return False
                
            return True
        except Exception as e:
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
