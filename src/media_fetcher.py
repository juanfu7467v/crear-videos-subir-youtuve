"""
media_fetcher.py
─────────────────
Descarga clips de video e imágenes de APIs gratuitas:
- Pexels API (videos e imágenes HD gratuitos)
- Pixabay API (videos e imágenes gratuitos)
- Pollinations.ai (imágenes generadas por IA, gratis)
"""

import logging
import os
import random
import time
from pathlib import Path
from typing import Optional
import requests

logger = logging.getLogger(__name__)

PEXELS_BASE   = "https://api.pexels.com"
PIXABAY_BASE  = "https://pixabay.com/api"
POLLINATIONS  = "https://image.pollinations.ai/prompt"


class MediaFetcher:
    """
    Descarga media visual (clips e imágenes) de fuentes gratuitas.
    """

    def __init__(self, pexels_key: str, pixabay_key: str):
        self.pexels_key  = pexels_key
        self.pixabay_key = pixabay_key
        self.session     = requests.Session()
        self.session.headers.update({"User-Agent": "ElTioJota-AutoVideo/1.0"})

    # ─── Entry point principal ────────────────────────────────
    def fetch_media_for_video(
        self,
        keywords: list,
        target_duration: int,
        save_dir: str,
        video_id: str,
        prefer_video: bool = True,
    ) -> list:
        """
        Descarga toda la media necesaria para un video.

        Returns:
            Lista de dicts con info de cada elemento:
            [{"path": "...", "type": "video|image", "duration": 5, "keyword": "..."}]
        """
        save_dir = Path(save_dir) / video_id
        save_dir.mkdir(parents=True, exist_ok=True)

        media_list = []
        clips_needed = max(3, target_duration // 8)  # ~8s por clip

        logger.info(f"Buscando {clips_needed} clips para {target_duration}s de video")
        logger.info(f"Keywords: {', '.join(keywords)}")

        # Rotar entre keywords para variedad
        kw_cycle = (keywords * ((clips_needed // len(keywords)) + 2))[:clips_needed]

        for i, kw in enumerate(kw_cycle):
            try:
                media_item = None

                if prefer_video and self.pexels_key:
                    media_item = self._fetch_pexels_video(kw, save_dir, f"clip_{i:03d}")

                if not media_item and self.pixabay_key:
                    media_item = self._fetch_pixabay_video(kw, save_dir, f"clip_{i:03d}")

                if not media_item and self.pexels_key:
                    media_item = self._fetch_pexels_image(kw, save_dir, f"img_{i:03d}")

                if not media_item:
                    media_item = self._fetch_pollinations_image(kw, save_dir, f"ai_{i:03d}")

                if media_item:
                    media_list.append(media_item)
                    logger.debug(f"  [{i+1}/{clips_needed}] ✓ {kw}: {media_item['path']}")

                time.sleep(0.3)  # Rate limiting

            except Exception as e:
                logger.warning(f"Error descargando media para '{kw}': {e}")
                continue

        if not media_list:
            logger.warning("No se pudo descargar ningún media. Generando imágenes AI...")
            for i, kw in enumerate(keywords[:5]):
                item = self._fetch_pollinations_image(kw, save_dir, f"fallback_{i}")
                if item:
                    media_list.append(item)

        logger.info(f"Media total descargada: {len(media_list)} elementos")
        return media_list

    # ─── Pexels Videos ───────────────────────────────────────
    def _fetch_pexels_video(self, keyword: str, save_dir: Path, prefix: str) -> Optional[dict]:
        """Descarga un clip de video de Pexels."""
        if not self.pexels_key:
            return None

        try:
            url = f"{PEXELS_BASE}/videos/search"
            params = {
                "query": keyword,
                "per_page": 10,
                "orientation": "portrait",  # Para Shorts
                "size": "medium",
            }
            headers = {"Authorization": self.pexels_key}

            resp = self.session.get(url, params=params, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            videos = data.get("videos", [])
            if not videos:
                # Intentar landscape si no hay portrait
                params["orientation"] = "landscape"
                resp = self.session.get(url, params=params, headers=headers, timeout=15)
                videos = resp.json().get("videos", [])

            if not videos:
                return None

            video = random.choice(videos[:5])
            # Elegir la versión de menor resolución para ahorrar espacio
            video_files = sorted(
                video.get("video_files", []),
                key=lambda x: x.get("width", 0)
            )
            # Preferir calidad media (720p)
            target = next(
                (f for f in video_files if f.get("width", 0) <= 1280 and f.get("height", 0) >= 480),
                video_files[0] if video_files else None
            )

            if not target:
                return None

            video_url = target["link"]
            filename = save_dir / f"{prefix}_pexels.mp4"

            self._download_file(video_url, str(filename))

            return {
                "path": str(filename),
                "type": "video",
                "duration": video.get("duration", 8),
                "keyword": keyword,
                "source": "pexels",
                "width": target.get("width", 1280),
                "height": target.get("height", 720),
            }

        except Exception as e:
            logger.debug(f"Pexels video error para '{keyword}': {e}")
            return None

    # ─── Pexels Images ────────────────────────────────────────
    def _fetch_pexels_image(self, keyword: str, save_dir: Path, prefix: str) -> Optional[dict]:
        """Descarga una imagen de Pexels."""
        if not self.pexels_key:
            return None

        try:
            url = f"{PEXELS_BASE}/v1/search"
            params = {"query": keyword, "per_page": 10, "orientation": "portrait"}
            headers = {"Authorization": self.pexels_key}

            resp = self.session.get(url, params=params, headers=headers, timeout=15)
            resp.raise_for_status()
            photos = resp.json().get("photos", [])

            if not photos:
                return None

            photo = random.choice(photos[:5])
            img_url = photo.get("src", {}).get("large", photo.get("src", {}).get("original"))

            if not img_url:
                return None

            filename = save_dir / f"{prefix}_pexels.jpg"
            self._download_file(img_url, str(filename))

            return {
                "path": str(filename),
                "type": "image",
                "duration": 5,
                "keyword": keyword,
                "source": "pexels",
                "width": photo.get("width", 1080),
                "height": photo.get("height", 1920),
            }

        except Exception as e:
            logger.debug(f"Pexels image error para '{keyword}': {e}")
            return None

    # ─── Pixabay Videos ──────────────────────────────────────
    def _fetch_pixabay_video(self, keyword: str, save_dir: Path, prefix: str) -> Optional[dict]:
        """Descarga un clip de video de Pixabay."""
        if not self.pixabay_key:
            return None

        try:
            params = {
                "key": self.pixabay_key,
                "q": keyword,
                "video_type": "film",
                "per_page": 10,
                "safesearch": "true",
                "lang": "es",
            }
            resp = self.session.get(f"{PIXABAY_BASE}/videos/", params=params, timeout=15)
            resp.raise_for_status()
            hits = resp.json().get("hits", [])

            if not hits:
                # Intentar en inglés
                params["lang"] = "en"
                resp = self.session.get(f"{PIXABAY_BASE}/videos/", params=params, timeout=15)
                hits = resp.json().get("hits", [])

            if not hits:
                return None

            hit = random.choice(hits[:5])
            videos = hit.get("videos", {})
            # Preferir calidad medium
            vid = videos.get("medium") or videos.get("small") or videos.get("large")

            if not vid or not vid.get("url"):
                return None

            filename = save_dir / f"{prefix}_pixabay.mp4"
            self._download_file(vid["url"], str(filename))

            return {
                "path": str(filename),
                "type": "video",
                "duration": hit.get("duration", 8),
                "keyword": keyword,
                "source": "pixabay",
                "width": vid.get("width", 1280),
                "height": vid.get("height", 720),
            }

        except Exception as e:
            logger.debug(f"Pixabay video error para '{keyword}': {e}")
            return None

    # ─── Pollinations AI Images ───────────────────────────────
    def _fetch_pollinations_image(self, keyword: str, save_dir: Path, prefix: str) -> Optional[dict]:
        """
        Genera imagen IA con Pollinations.ai (totalmente gratis).
        """
        try:
            # Crear prompt mejorado para la imagen
            prompt = self._build_image_prompt(keyword)
            encoded = requests.utils.quote(prompt)

            # Configurar para aspect ratio vertical (Shorts) o horizontal
            url = f"{POLLINATIONS}/{encoded}?width=1080&height=1920&seed={random.randint(1,9999)}&nologo=true"

            filename = save_dir / f"{prefix}_ai.jpg"

            resp = self.session.get(url, timeout=30, stream=True)
            resp.raise_for_status()

            with open(filename, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)

            if filename.stat().st_size < 10000:  # Imagen muy pequeña = error
                filename.unlink(missing_ok=True)
                return None

            return {
                "path": str(filename),
                "type": "image",
                "duration": 5,
                "keyword": keyword,
                "source": "pollinations",
                "width": 1080,
                "height": 1920,
            }

        except Exception as e:
            logger.debug(f"Pollinations error para '{keyword}': {e}")
            return None

    def _build_image_prompt(self, keyword: str) -> str:
        """Crea un prompt mejorado para generación de imagen IA."""
        styles = [
            "cinematic lighting, professional photography",
            "vibrant colors, high contrast",
            "dramatic composition, 4K ultra HD",
            "photorealistic, stunning visual",
            "editorial photography style",
        ]
        style = random.choice(styles)
        return f"{keyword}, {style}, vertical format, no text, no watermark"

    # ─── Descarga genérica ────────────────────────────────────
    def _download_file(self, url: str, save_path: str, max_size_mb: int = 50):
        """Descarga un archivo con límite de tamaño."""
        max_bytes = max_size_mb * 1024 * 1024

        resp = self.session.get(url, timeout=60, stream=True)
        resp.raise_for_status()

        downloaded = 0
        with open(save_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                downloaded += len(chunk)
                if downloaded > max_bytes:
                    logger.warning(f"Archivo muy grande, truncando en {max_size_mb}MB")
                    break
                f.write(chunk)

        size_mb = Path(save_path).stat().st_size / (1024 * 1024)
        logger.debug(f"Descargado: {save_path} ({size_mb:.2f} MB)")

    # ─── Thumbnails ───────────────────────────────────────────
    def generate_thumbnail(
        self,
        topic: str,
        title: str,
        save_path: str,
        style: str = "youtube_thumbnail",
    ) -> Optional[str]:
        """
        Genera una miniatura para YouTube usando Pollinations.ai.
        """
        prompt = (
            f"YouTube thumbnail, {topic}, {style}, "
            f"bold colors, eye-catching, professional, "
            f"16:9 aspect ratio, high quality, no text overlay"
        )

        try:
            encoded = requests.utils.quote(prompt)
            url = f"{POLLINATIONS}/{encoded}?width=1280&height=720&seed={random.randint(1,9999)}&nologo=true"

            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()

            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(resp.content)

            logger.info(f"Thumbnail generada: {save_path}")
            return save_path

        except Exception as e:
            logger.error(f"Error generando thumbnail: {e}")
            return None
