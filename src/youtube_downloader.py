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
    Implementa medidas anti-bot: User-Agents reales y soporte para cookies/OAuth2.
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("YOUTUBE_API_KEY")
        self.base_url = "https://www.googleapis.com/youtube/v3/search"
        self.session = requests.Session()
        
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0"
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
            logger.info(f"Encontrados {len(video_ids)} trailers potenciales para \'{movie_title}\'")
            return video_ids
        except Exception as e:
            logger.error(f"Error buscando en YouTube API: {e}")
            return []

    def download_fragment(self, video_id: str, save_path: Path, start_time: int, duration: int) -> bool:
        yt_url = f"https://www.youtube.com/watch?v={video_id}"
        yt_dlp_path = shutil.which("yt-dlp") or "yt-dlp"
        user_agent = random.choice(self.user_agents)
        
        # Construcción del comando yt-dlp con las mejoras sugeridas
        cmd = [
            yt_dlp_path,
            "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]", # Forzar MP4
            "--user-agent", user_agent,
            "--no-check-certificate",
            "--geo-bypass",
            "--extractor-args", "youtube:player_client=web", # Forzar cliente web
            "--external-downloader", "ffmpeg",
            "--external-downloader-args", f"ffmpeg_i:-ss {start_time} -t {duration}",
            "--output", str(save_path),
            yt_url
        ]
        
        # Archivo temporal para las credenciales OAuth2
        # yt-dlp puede usar un archivo .netrc para la autenticación de YouTube con refresh_token
        netrc_file_path = Path("youtube_netrc")
        
        try:
            oauth2_data = get_valid_oauth2_data()
            if oauth2_data and oauth2_data.get('refresh_token'):
                logger.info("Usando YOUTUBE_OAUTH2_DATA (refresh_token) para autenticación en la descarga.")
                # Crear un archivo .netrc temporal con el refresh_token
                # yt-dlp buscará 'youtube' en el .netrc para el refresh_token
                netrc_content = f"machine youtube\n  login {oauth2_data['client_id']}\n  password {oauth2_data['client_secret']}\n  account {oauth2_data['refresh_token']}\n"
                netrc_file_path.write_text(netrc_content)
                # Añadir la opción --netrc-location a yt-dlp para que use el archivo temporal
                cmd.extend(["--netrc-location", str(netrc_file_path)])
                # También podemos añadir --username oauth2 si el plugin está instalado, pero --netrc-location es más genérico.
                # cmd.extend(["--username", "oauth2"])
            
            elif self.cookies_path.exists():
                logger.info(f"Usando cookies de YouTube desde: {self.cookies_path}")
                cmd.extend(["--cookies", str(self.cookies_path)])
                
            else:
                env_cookies = os.getenv("YOUTUBE_COOKIES_CONTENT")
                if env_cookies:
                    temp_cookies = Path("temp_cookies.txt")
                    temp_cookies.write_text(env_cookies)
                    cmd.extend(["--cookies", str(temp_cookies)])
                    logger.info("Usando cookies desde variable de entorno.")

            logger.info(f"Iniciando descarga de fragmento: {video_id} (Inicio: {start_time}s, Duración: {duration}s)")
            
            max_retries = 2
            for attempt in range(max_retries):
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
                
                if result.returncode == 0 and save_path.exists() and save_path.stat().st_size > 1024:
                    logger.info(f"Descarga exitosa: {save_path.name}")
                    return True
                
                error_msg = result.stderr if result.stderr else result.stdout
                logger.warning(f"Intento {attempt + 1} fallido para {video_id}. Error: {error_msg[:500]}")
                
                time.sleep(2)
                cmd[cmd.index("--user-agent") + 1] = random.choice(self.user_agents)
            
            return False
        except Exception as e:
            logger.error(f"Excepción en download_fragment para {video_id}: {e}")
            return False
        finally:
            # Limpieza de archivos temporales
            if netrc_file_path.exists():
                try: netrc_file_path.unlink()
                except: pass
            if Path("temp_cookies.txt").exists():
                try: Path("temp_cookies.txt").unlink()
                except: pass

    def fetch_trailer_clips(self, movie_title: str, save_dir: Path, clips_needed: int = 3) -> List[Dict]:
        search_query = movie_title.split(".")[0].replace("_", " ").replace("-", " ")
        video_ids = self.search_trailer(search_query, count=3)
        
        if not video_ids:
            logger.warning(f"No se encontraron videos para \'{search_query}\'")
            return []

        downloaded_clips = []
        suggested_starts = [15, 60, 100, 30, 140]
        
        for i in range(clips_needed):
            video_id = video_ids[i % len(video_ids)]
            base_start = suggested_starts[i % len(suggested_starts)]
            actual_start = max(5, base_start + random.randint(-5, 15))
            duration = random.randint(6, 10)
            
            output_path = save_dir / f"yt_trailer_{i:03d}.mp4"
            
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
                time.sleep(1)
            
            if len(downloaded_clips) >= clips_needed:
                break
        
        logger.info(f"Total de clips de YouTube obtenidos: {len(downloaded_clips)}")
        return downloaded_clips
