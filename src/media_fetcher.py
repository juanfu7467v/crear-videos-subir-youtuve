import logging
import os
import random
import time
import subprocess
import json
from pathlib import Path
from typing import Optional, Dict, List
import requests
from src.movie_clips_fetcher import MovieClipsFetcher
from src.peliprex_downloader import PeliprexDownloader
from src.archive_org_downloader import ArchiveOrgDownloader
from src.archive_downloader import ArchiveDownloader

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
        self.movie_clips_fetcher = MovieClipsFetcher()
        self.peliprex_downloader = PeliprexDownloader()
        self.archive_org_downloader = ArchiveOrgDownloader()
        self.archive_smart_downloader = ArchiveDownloader()
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
        categoria: Optional[str] = None,
        script_data: Optional[Dict] = None
    ) -> list:
        save_dir = Path(save_dir) / video_id
        save_dir.mkdir(parents=True, exist_ok=True)

        media_list = []
        
        format_label = "Short" if is_short else "Largo"
        logger.info(f"Buscando clips para {target_duration}s de video ({format_label}) con patrón intercalado.")
        
        # 1. Obtener el término de búsqueda real de la película
        movie_title = ""
        if script_data and script_data.get("peliprex_search_term"):
            movie_title = script_data.get("peliprex_search_term")
            logger.info(f"Usando peliprex_search_term: {movie_title}")
        else:
            raw_title = video_id
            if segmented_script and segmented_script[0].get("segment_text"):
                raw_title = segmented_script[0].get("segment_text", "")
            movie_title = self.peliprex_downloader.clean_movie_title(raw_title)
            logger.info(f"Usando limpieza de texto para título: {movie_title}")
        
        # 2. Descargar clips de Película (PeliPrex y Archive.org como respaldo)
        # Necesitamos aproximadamente la mitad del video en clips de película de 7s
        movie_clips_needed = (target_duration // 14) + 2
        logger.info(f"Descargando clips de película para: {movie_title} (Necesarios: {movie_clips_needed})")
        
        peliprex_clips = self.peliprex_downloader.fetch_movie_clips(movie_title, save_dir, movie_clips_needed)
        
        archive_clips = []
        if len(peliprex_clips) < movie_clips_needed:
            needed_from_archive = movie_clips_needed - len(peliprex_clips)
            logger.info(f"PeliPrex insuficiente ({len(peliprex_clips)}/{movie_clips_needed}), buscando en Archive.org")
            archive_clips = self.archive_smart_downloader.fetch_smart_clips(movie_title, save_dir, needed_from_archive)
            
            if not archive_clips:
                legacy_item = self.archive_org_downloader.fetch_archive_org_video(movie_title, save_dir, "archive_legacy")
                if legacy_item:
                    archive_clips = [legacy_item]

        movie_pool = peliprex_clips + archive_clips
        logger.info(f"Pool de clips de película listo: {len(movie_pool)} clips.")

        # 3. Implementar patrón intercalado hasta completar la duración
        current_total_duration = 0
        segment_index = 0
        
        while current_total_duration < target_duration:
            # --- FASE 1: PELÍCULA (7 segundos) ---
            if movie_pool:
                visual_item = movie_pool.pop(0)
                visual_item["segment_duration"] = 7.0
                media_list.append(visual_item)
                current_total_duration += 7.0
                logger.info(f"Añadido clip de PELÍCULA (7s). Total: {current_total_duration:.1f}s")
            
            if current_total_duration >= target_duration: break
            
            # --- FASE 2: STOCK (7 segundos o menos) ---
            # Buscamos keywords del guion segmentado si están disponibles
            kw = movie_title
            if segment_index < len(segmented_script):
                keywords = process_keywords(segmented_script[segment_index].get("keywords", []))
                if keywords: kw = random.choice(keywords)
                segment_index += 1
            
            orientation = "portrait" if is_short else "landscape"
            stock_item = None
            
            if self.pexels_key:
                stock_item = self._fetch_pexels_video(kw, save_dir, f"stock_{len(media_list)}", orientation)
            if not stock_item and self.pixabay_key:
                stock_item = self._fetch_pixabay_video(kw, save_dir, f"stock_{len(media_list)}")
            
            # Fallback si falla el stock: Usar película si queda, o imagen AI
            if not stock_item:
                if movie_pool:
                    stock_item = movie_pool.pop(0)
                else:
                    stock_item = self._fetch_pollinations_image(kw, save_dir, f"ai_{len(media_list)}", is_short)
            
            if stock_item:
                # Duración de stock: intentamos que sea 7s pero si falta poco para el final lo ajustamos
                stock_duration = min(7.0, target_duration - current_total_duration)
                stock_item["segment_duration"] = stock_duration
                media_list.append(stock_item)
                current_total_duration += stock_duration
                logger.info(f"Añadido clip de STOCK ({stock_duration}s). Total: {current_total_duration:.1f}s")

            # Pequeña pausa para APIs
            time.sleep(0.1)

        logger.info(f"Media total procesada: {len(media_list)} elementos en patrón intercalado.")
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
            logger.error(f"Error en Pexels: {e}")
            return None

    def _fetch_pixabay_video(self, keyword: str, save_dir: Path, prefix: str) -> Optional[dict]:
        if not self.pixabay_key: return None
        try:
            url = f"{PIXABAY_BASE}/videos/"
            params = {"key": self.pixabay_key, "q": keyword, "per_page": 10, "safesearch": "true"}
            resp = self.session.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            hits = data.get("hits", [])
            if not hits: return None
            video = random.choice(hits[:5])
            videos_map = video.get("videos", {})
            target = videos_map.get("medium") or videos_map.get("small") or videos_map.get("large") or videos_map.get("tiny")
            if not target: return None
            video_url = target["url"]
            filename = save_dir / f"{prefix}_pixabay.mp4"
            if self._download_file(video_url, str(filename)):
                return {"path": str(filename), "type": "video", "duration": video.get("duration", 10), "keyword": keyword, "source": "pixabay", "width": target.get("width", 1280), "height": target.get("height", 720)}
            return None
        except Exception as e:
            logger.error(f"Error en Pixabay: {e}")
            return None

    def _fetch_pollinations_image(self, keyword: str, save_dir: Path, prefix: str, is_short: bool = True) -> Optional[dict]:
        try:
            width, height = (1080, 1920) if is_short else (1920, 1080)
            encoded_kw = requests.utils.quote(keyword)
            url = f"{POLLINATIONS}/{encoded_kw}?width={width}&height={height}&model=flux&nologo=true"
            filename = save_dir / f"{prefix}_pollinations.jpg"
            if self._download_file(url, str(filename)):
                return {"path": str(filename), "type": "image", "duration": 5.0, "keyword": keyword, "source": "pollinations", "width": width, "height": height}
            return None
        except Exception as e:
            logger.error(f"Error en Pollinations: {e}")
            return None

    def _download_file(self, url: str, save_path: str) -> bool:
        try:
            resp = self.session.get(url, stream=True, timeout=30)
            resp.raise_for_status()
            with open(save_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk: f.write(chunk)
            return os.path.exists(save_path) and os.path.getsize(save_path) > 1024
        except Exception as e:
            logger.error(f"Error descargando {url}: {e}")
            return False

    def generate_thumbnail(self, movie_title: str, video_title: str, save_path: str, categoria: str = "general") -> bool:
        """
        Genera una miniatura usando TMDB para películas o Pollinations como fallback.
        """
        try:
            # Fallback a Pollinations para la miniatura
            width, height = (1080, 1920) # Forzamos resolución vertical para shorts si es necesario
            prompt = f"Cinematic movie poster for {movie_title}, {video_title}, high quality, 4k, professional design"
            encoded_prompt = requests.utils.quote(prompt)
            url = f"{POLLINATIONS}/{encoded_prompt}?width={width}&height={height}&model=flux&nologo=true"
            
            return self._download_file(url, save_path)
        except Exception as e:
            logger.error(f"Error generando miniatura: {e}")
            return False
