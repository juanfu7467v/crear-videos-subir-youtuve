import logging
import os
import random
import subprocess
import shutil
import requests
import time
import json
from pathlib import Path
from typing import List, Dict, Optional
from src.oauth2_utils import get_valid_oauth2_data

logger = logging.getLogger(__name__)

class YouTubeDownloader:
    """
    Busca trailers oficiales en YouTube usando la API de Data v3 y descarga fragmentos específicos.
    Implementa medidas anti-bot: User-Agents reales, rotación de clientes y soporte para OAuth2.
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("YOUTUBE_API_KEY")
        self.base_url = "https://www.googleapis.com/youtube/v3/search"
        self.session = requests.Session()
        
        # User-Agents modernos y variados para simular navegadores reales
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edge/121.0.0.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0"
        ]
        
        self.cookies_path = Path("credentials/youtube_cookies.txt")

    def search_trailer(self, movie_title: str, count: int = 2) -> List[str]:
        if not self.api_key:
            logger.error("YOUTUBE_API_KEY no configurada.")
            return []

        try:
            params = {
                "part": "snippet",
                "q": f"{movie_title} official trailer",
                "type": "video",
                "maxResults": count,
                "key": self.api_key
            }
            headers = {"User-Agent": random.choice(self.user_agents)}
            resp = self.session.get(self.base_url, params=params, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            
            video_ids = [item["id"]["videoId"] for item in data.get("items", [])]
            logger.info(f"Encontrados {len(video_ids)} trailers potenciales para '{movie_title}'")
            return video_ids
        except Exception as e:
            logger.error(f"Error buscando en YouTube API: {e}")
            return []

    def download_fragment(self, video_id: str, save_path: Path, start_time: int, duration: int) -> bool:
        yt_url = f"https://www.youtube.com/watch?v={video_id}"
        yt_dlp_path = shutil.which("yt-dlp") or "yt-dlp"
        
        # Clientes de YouTube para rotar en caso de bloqueo
        # ios y mweb suelen ser más permisivos con IPs de centros de datos
        clients = ["ios", "mweb", "web", "android"]
        
        # Archivo temporal para las credenciales OAuth2 (.netrc)
        netrc_file_path = Path("youtube_netrc")
        oauth2_data = get_valid_oauth2_data()
        
        if oauth2_data and oauth2_data.get('refresh_token'):
            netrc_content = (
                f"machine youtube\n"
                f"  login {oauth2_data['client_id']}\n"
                f"  password {oauth2_data['client_secret']}\n"
                f"  account {oauth2_data['refresh_token']}\n"
            )
            netrc_file_path.write_text(netrc_content)

        max_retries = 3
        for attempt in range(max_retries):
            user_agent = random.choice(self.user_agents)
            client = clients[attempt % len(clients)]
            
            cmd = [
                yt_dlp_path,
                "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]",
                "--user-agent", user_agent,
                "--no-check-certificate",
                "--geo-bypass",
                "--extractor-args", f"youtube:player_client={client}",
                "--external-downloader", "ffmpeg",
                "--external-downloader-args", f"ffmpeg_i:-ss {start_time} -t {duration}",
                "--output", str(save_path),
                "--quiet", "--no-warnings",
                yt_url
            ]

            if netrc_file_path.exists():
                cmd.extend(["--netrc-location", str(netrc_file_path)])
            elif self.cookies_path.exists():
                cmd.extend(["--cookies", str(self.cookies_path)])

            logger.info(f"Intento {attempt + 1}/{max_retries}: Descargando {video_id} con cliente '{client}'")
            
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
                
                if result.returncode == 0 and save_path.exists() and save_path.stat().st_size > 1024:
                    logger.info(f"Descarga exitosa: {save_path.name}")
                    return True
                
                error_msg = result.stderr if result.stderr else result.stdout
                logger.warning(f"Fallo en intento {attempt + 1} para {video_id}: {error_msg[:200]}...")
                
                # Pausa exponencial entre reintentos para evitar detección
                time.sleep(2 * (attempt + 1))
            except subprocess.TimeoutExpired:
                logger.warning(f"Timeout en intento {attempt + 1} para {video_id}")
            except Exception as e:
                logger.error(f"Error inesperado en download_fragment: {e}")

        # Limpieza final
        if netrc_file_path.exists():
            try: netrc_file_path.unlink()
            except: pass
            
        return False

    def fetch_trailer_clips(self, movie_title: str, save_dir: Path, clips_needed: int = 3) -> List[Dict]:
        search_query = movie_title.split(".")[0].replace("_", " ").replace("-", " ")
        video_ids = self.search_trailer(search_query, count=5) # Buscamos más para tener opciones
        
        if not video_ids:
            logger.warning(f"No se encontraron videos para '{search_query}'")
            return []

        downloaded_clips = []
        suggested_starts = [15, 60, 100, 30, 140, 45, 80]
        
        # Barajamos los videos para no descargar siempre los mismos
        random.shuffle(video_ids)
        
        for i in range(min(len(video_ids), clips_needed * 2)): # Intentamos con el doble de lo necesario
            video_id = video_ids[i]
            base_start = random.choice(suggested_starts)
            actual_start = max(5, base_start + random.randint(-5, 15))
            duration = random.randint(6, 10)
            
            output_path = save_dir / f"yt_trailer_{len(downloaded_clips):03d}.mp4"
            
            if self.download_fragment(video_id, output_path, actual_start, duration):
                downloaded_clips.append({
                    "path": str(output_path),
                    "type": "video",
                    "duration": float(duration),
                    "keyword": movie_title,
                    "source": "youtube_trailer",
                    "width": 1280,
                    "height": 720
                })
                time.sleep(1.5) # Pausa entre videos
            
            if len(downloaded_clips) >= clips_needed:
                break
        
        logger.info(f"Total de clips de YouTube obtenidos: {len(downloaded_clips)}")
        return downloaded_clips
