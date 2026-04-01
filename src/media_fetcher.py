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
        # Eliminamos la dependencia de YouTube API key
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
        logger.info(f"Buscando clips para {target_duration}s de video ({format_label}) con nueva lógica de prioridad.")
        
        # 1. Obtener el término de búsqueda real de la película
        movie_title = ""
        if script_data and script_data.get("peliprex_search_term"):
            movie_title = script_data.get("peliprex_search_term")
            logger.info(f"Prioridad 1: Usando peliprex_search_term: {movie_title}")
        else:
            raw_title = video_id
            if segmented_script and segmented_script[0].get("segment_text"):
                raw_title = segmented_script[0].get("segment_text", "")
            movie_title = self.peliprex_downloader.clean_movie_title(raw_title)
            logger.info(f"Prioridad 1: Usando limpieza de texto: {movie_title}")
        
        # 2. Intentar obtener clips de Peliprex (Prioridad 1)
        # Calculamos cuántos ciclos de 7-10-7 caben, pero pediremos suficientes clips para cubrir la duración
        # Si cada ciclo es ~17s, necesitamos target_duration / 17 ciclos.
        # Cada ciclo usa 1 clip de Peliprex y 1 de Stock.
        clips_needed_each = (target_duration // 17) + 2
        
        logger.info(f"Intentando obtener clips de Peliprex para: {movie_title}")
        peliprex_clips = self.peliprex_downloader.fetch_movie_clips(movie_title, save_dir, clips_needed_each)
        
        # 3. Intentar obtener clips de Archive.org (Prioridad 2 - Stock Principal)
        logger.info(f"Prioridad 2: Buscando en Archive.org para: {movie_title}")
        archive_clips = self.archive_smart_downloader.fetch_smart_clips(movie_title, save_dir, clips_needed_each)
        
        # Si Archive Smart falla, intentar Archive Legacy
        if not archive_clips:
            logger.info(f"Archive Smart falló, intentando Archive Legacy para: {movie_title}")
            legacy_item = self.archive_org_downloader.fetch_archive_org_video(movie_title, save_dir, "archive_legacy")
            if legacy_item:
                archive_clips = [legacy_item]

        # 4. Recopilar palabras clave para fallback (Prioridad 3: Pixabay/Pexels)
        all_keywords = []
        for segment in segmented_script:
            all_keywords.extend(process_keywords(segment.get("keywords", "")))
        if not all_keywords: all_keywords = ["cinematic movie scene"]

        # 5. Composición Dinámica
        current_total_duration = 0
        clip_index = 0
        
        # Listas para rastrear qué hemos usado y evitar repetición inmediata
        used_peliprex = []
        used_archive = []
        
        while current_total_duration < target_duration:
            # --- FASE A: CLIP DE PELÍCULA (7s) ---
            media_item = None
            
            # Intentar Peliprex primero
            if peliprex_clips:
                media_item = peliprex_clips.pop(0)
                used_peliprex.append(media_item)
                logger.info(f"Composición: Usando clip de Peliprex (7s).")
            # Si no hay Peliprex, intentar Archive.org como fallback de película
            elif archive_clips:
                media_item = archive_clips.pop(0)
                used_archive.append(media_item)
                logger.info(f"Composición: Usando clip de Archive.org como fallback de película (7s).")
            # Si ambos fallan, intentar MovieClipsFetcher (GetYarn) si es categoría películas
            elif categoria and "películas" in categoria.lower():
                yarn_clips = self.movie_clips_fetcher.fetch_movie_clips(movie_title, save_dir, 1)
                if yarn_clips:
                    media_item = yarn_clips[0]
                    logger.info(f"Composición: Usando clip de GetYarn como fallback (7s).")
            
            # Si aún no hay nada, usar Pexels/Pixabay con el nombre de la película
            if not media_item:
                orientation = "portrait" if is_short else "landscape"
                media_item = self._fetch_pexels_video(movie_title, save_dir, f"fallback_movie_{clip_index}", orientation)
                if not media_item:
                    media_item = self._fetch_pixabay_video(movie_title, save_dir, f"fallback_movie_{clip_index}")
                if media_item:
                    logger.info(f"Composición: Usando Pexels/Pixabay con '{movie_title}' como fallback (7s).")

            if media_item:
                media_item["segment_duration"] = 7.0
                media_list.append(media_item)
                current_total_duration += 7.0
            
            if current_total_duration >= target_duration: break

            # --- FASE B: CLIP DE STOCK (10s) ---
            stock_item = None
            
            # Prioridad 2: Archive.org como stock principal
            if archive_clips:
                stock_item = archive_clips.pop(0)
                used_archive.append(stock_item)
                logger.info(f"Composición: Usando clip de Archive.org como stock principal (10s).")
            
            # Prioridad 3: Pixabay y Pexels (Fallback)
            if not stock_item:
                kw = random.choice(all_keywords)
                orientation = "portrait" if is_short else "landscape"
                logger.info(f"Prioridad 3: Buscando fallback en Pexels/Pixabay para '{kw}'")
                
                if self.pexels_key:
                    stock_item = self._fetch_pexels_video(kw, save_dir, f"stock_{clip_index:03d}", orientation)
                
                if not stock_item and self.pixabay_key:
                    stock_item = self._fetch_pixabay_video(kw, save_dir, f"stock_{clip_index:03d}")
            
            # Fallback final: Imagen AI
            if not stock_item:
                kw = random.choice(all_keywords)
                logger.info(f"Fallback final: Generando imagen AI para '{kw}'")
                stock_item = self._fetch_pollinations_image(kw, save_dir, f"ai_{clip_index:03d}", is_short)

            if stock_item:
                stock_item["segment_duration"] = 10.0
                media_list.append(stock_item)
                current_total_duration += 10.0
            
            clip_index += 1
            time.sleep(0.1)

        # Si la lista está vacía, generar fallbacks de emergencia
        if not media_list:
            logger.warning("No se pudo descargar ningún media. Generando imágenes AI de fallback...")
            for i in range(5):
                kw_fallback = "cinematic movie scene"
                item = self._fetch_pollinations_image(kw_fallback, save_dir, f"fallback_{i}", is_short)
                if item:
                    item["segment_duration"] = 10.0
                    media_list.append(item)

        logger.info(f"Media total descargada: {len(media_list)} elementos con lógica dinámica.")
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

    def _fetch_pollinations_image(self, keyword: str, save_dir: Path, prefix: str, is_short: bool = True) -> Optional[dict]:
        try:
            width = 1080 if is_short else 1920
            height = 1920 if is_short else 1080
            encoded_kw = requests.utils.quote(keyword)
            img_url = f"{POLLINATIONS}/{encoded_kw}?width={width}&height={height}&model=flux&nologo=true"
            filename = save_dir / f"{prefix}_ai.jpg"
            if self._download_file(img_url, str(filename)):
                return {"path": str(filename), "type": "image", "duration": 5, "keyword": keyword, "source": "pollinations", "width": width, "height": height}
            return None
        except Exception as e:
            logger.debug(f"Pollinations error para '{keyword}': {e}")
            return None

    def _download_file(self, url: str, save_path: str) -> bool:
        try:
            resp = self.session.get(url, stream=True, timeout=30)
            resp.raise_for_status()
            with open(save_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            return os.path.exists(save_path) and os.path.getsize(save_path) > 0
        except Exception as e:
            logger.debug(f"Download error: {e}")
            return False

    def generate_thumbnail(self, movie_title: str, video_title: str, save_path: str, categoria: str = "general") -> bool:
        """
        Intenta generar una miniatura profesional.
        Si es de películas, intenta obtener el póster de TMDB.
        """
        try:
            if "películas" in categoria.lower():
                # Intentar buscar en TMDB (vía Peliprex o similar si hubiera API, pero aquí simulamos búsqueda simple)
                # Por ahora usamos Pollinations con un prompt optimizado para miniaturas de cine
                prompt = f"Professional movie poster for '{movie_title}', cinematic lighting, high resolution, 4k, masterpiece, no text"
                return self._fetch_pollinations_image(prompt, Path(save_path).parent, Path(save_path).stem, is_short=False) is not None
            
            return False
        except Exception as e:
            logger.error(f"Error generando miniatura: {e}")
            return False
