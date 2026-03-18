import logging
import os
import random
import subprocess
import shutil
import requests
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class YouTubeDownloader:
    """
    Busca trailers oficiales en YouTube usando la API de Data v3 y descarga fragmentos específicos.
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("YOUTUBE_API_KEY")
        self.base_url = "https://www.googleapis.com/youtube/v3/search"
        self.session = requests.Session()

    def search_trailer(self, movie_title: str, count: int = 1) -> List[str]:
        """
        Busca el trailer oficial de una película y devuelve una lista de IDs de video.
        """
        if not self.api_key:
            logger.error("YOUTUBE_API_KEY no configurada.")
            return []

        try:
            params = {
                "part": "snippet",
                "q": f"{movie_title} official trailer",
                "type": "video",
                "videoCaption": "any",
                "maxResults": count,
                "key": self.api_key
            }
            resp = self.session.get(self.base_url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            
            video_ids = [item["id"]["videoId"] for item in data.get("items", [])]
            logger.info(f"Encontrados {len(video_ids)} trailers para '{movie_title}'")
            return video_ids
        except Exception as e:
            logger.error(f"Error buscando en YouTube API: {e}")
            return []

    def download_fragment(self, video_id: str, save_path: Path, start_time: int, duration: int) -> bool:
        """
        Descarga un fragmento específico de un video de YouTube.
        """
        try:
            yt_url = f"https://www.youtube.com/watch?v={video_id}"
            yt_dlp_path = shutil.which("yt-dlp") or "yt-dlp"
            
            # Comando optimizado para descargar solo el fragmento necesario
            cmd = [
                yt_dlp_path,
                "-f", "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]",
                "--external-downloader", "ffmpeg",
                "--external-downloader-args", f"ffmpeg_i:-ss {start_time} -t {duration}",
                "--output", str(save_path),
                yt_url
            ]
            
            logger.info(f"Descargando fragmento de {yt_url} ({start_time}s - {start_time + duration}s)")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0 and save_path.exists():
                return True
            else:
                logger.error(f"Error al descargar fragmento: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Excepción descargando fragmento de YT: {e}")
            return False

    def fetch_trailer_clips(self, movie_title: str, save_dir: Path, clips_needed: int = 3) -> List[Dict]:
        """
        Busca trailers y descarga múltiples fragmentos.
        """
        video_ids = self.search_trailer(movie_title, count=2)
        if not video_ids:
            return []

        downloaded_clips = []
        # Tiempos sugeridos para trailers: acción (10-17s), primer plano (45-50s), etc.
        suggested_ranges = [
            (10, 7),  # Clip 1: 10s - 17s
            (45, 5),  # Clip 2: 45s - 50s
            (80, 6),  # Clip 3: 80s - 86s
            (120, 5)  # Clip 4: 120s - 125s
        ]

        for i in range(clips_needed):
            video_id = video_ids[i % len(video_ids)]
            start, dur = suggested_ranges[i % len(suggested_ranges)]
            
            # Añadir un pequeño factor aleatorio al inicio para variar
            actual_start = max(0, start + random.randint(-2, 2))
            
            output_path = save_dir / f"yt_trailer_{i:03d}.mp4"
            if self.download_fragment(video_id, output_path, actual_start, dur):
                downloaded_clips.append({
                    "path": str(output_path),
                    "type": "video",
                    "duration": float(dur),
                    "keyword": movie_title,
                    "source": "youtube_trailer",
                    "width": 1280,
                    "height": 720
                })
        
        return downloaded_clips
