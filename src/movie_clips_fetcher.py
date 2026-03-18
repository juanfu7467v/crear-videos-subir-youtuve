import logging
import os
import random
import requests
import subprocess
from pathlib import Path
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

class MovieClipsFetcher:
    """
    Busca y descarga clips reales de películas usando KinoCheck API y yt-dlp.
    """
    def __init__(self):
        self.kinocheck_base = "https://api.kinocheck.com"
        self.tmdb_search_url = "https://api.themoviedb.org/3/search/movie"
        # Usamos una clave pública de prueba si no hay una en el entorno
        self.tmdb_api_key = os.getenv("TMDB_API_KEY", "8baba8ab6b8bbe247645bcae7df63d0d")
        self.session = requests.Session()

    def fetch_movie_clips(self, movie_title: str, save_dir: Path, clips_needed: int = 5) -> List[Dict]:
        """
        Busca una película, obtiene sus trailers/clips de KinoCheck y descarga fragmentos.
        """
        logger.info(f"🎬 Buscando clips reales para la película: {movie_title}")
        
        # 1. Buscar el TMDB ID de la película
        tmdb_id = self._get_tmdb_id(movie_title)
        if not tmdb_id:
            logger.warning(f"No se encontró TMDB ID para '{movie_title}'")
            return []

        # 2. Obtener videos de KinoCheck
        videos = self._get_kinocheck_videos(tmdb_id)
        logger.info(f"Se encontraron {len(videos)} videos en KinoCheck.")
        if not videos:
            logger.warning(f"No se encontraron videos en KinoCheck para TMDB ID {tmdb_id}")
            return []

        # 3. Descargar fragmentos cortos de los videos encontrados
        downloaded_clips = []
        
        # Priorizar clips sobre trailers si están disponibles
        sorted_videos = sorted(videos, key=lambda v: 1 if "Clip" in v.get("categories", []) else 2)
        
        for i, video in enumerate(sorted_videos):
            if len(downloaded_clips) >= clips_needed:
                break
                
            yt_id = video.get("youtube_video_id")
            if not yt_id:
                continue
                
            output_path = save_dir / f"movie_clip_{i:03d}.mp4"
            success = self._download_yt_fragment(yt_id, output_path)
            
            if success:
                downloaded_clips.append({
                    "path": str(output_path),
                    "type": "video",
                    "duration": 8, # Fragmento de 8s por defecto
                    "keyword": movie_title,
                    "source": "kinocheck_yt",
                    "width": 1280,
                    "height": 720
                })
                logger.info(f"✓ Clip descargado de YouTube: {output_path}")
        
        # 4. Fallback a GetYarn si no hay suficientes clips
        if len(downloaded_clips) < clips_needed:
            logger.info(f"Buscando clips adicionales en GetYarn para '{movie_title}'...")
            yarn_clips = self._fetch_yarn_clips(movie_title, save_dir, clips_needed - len(downloaded_clips))
            downloaded_clips.extend(yarn_clips)
            
        # 5. Fallback final a Pexels (Stock) si seguimos sin clips
        if len(downloaded_clips) < clips_needed:
            logger.info(f"Buscando clips de stock en Pexels como fallback para '{movie_title}'...")
            pexels_clips = self._fetch_pexels_fallback(movie_title, save_dir, clips_needed - len(downloaded_clips))
            downloaded_clips.extend(pexels_clips)

        return downloaded_clips

    def _fetch_pexels_fallback(self, keyword: str, save_dir: Path, count: int) -> List[Dict]:
        """Descarga clips de Pexels como último recurso."""
        pexels_key = os.getenv("PEXELS_API_KEY")
        if not pexels_key: return []
        
        clips = []
        try:
            url = "https://api.pexels.com/videos/search"
            headers = {"Authorization": pexels_key}
            params = {"query": keyword, "per_page": count}
            resp = self.session.get(url, headers=headers, params=params, timeout=10)
            if resp.status_code == 200:
                videos = resp.json().get("videos", [])
                for i, v in enumerate(videos):
                    video_files = v.get("video_files", [])
                    if not video_files: continue
                    
                    # Tomar el archivo de video con mejor calidad pero no gigante
                    target = next((f for f in video_files if f.get("width", 0) <= 1920), video_files[0])
                    video_url = target.get("link")
                    filename = save_dir / f"pexels_fallback_{i:03d}.mp4"
                    
                    r = self.session.get(video_url, stream=True)
                    with open(filename, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                            
                    clips.append({
                        "path": str(filename),
                        "type": "video",
                        "duration": v.get("duration", 5),
                        "keyword": keyword,
                        "source": "pexels_fallback",
                        "width": target.get("width", 1280),
                        "height": target.get("height", 720)
                    })
        except Exception as e:
            logger.error(f"Error en Pexels fallback: {e}")
        return clips

    def _fetch_yarn_clips(self, keyword: str, save_dir: Path, count: int) -> List[Dict]:
        import re
        clips = []
        try:
            search_url = f"https://getyarn.io/yarn-find?text={requests.utils.quote(keyword)}"
            resp = self.session.get(search_url, timeout=10)
            if resp.status_code != 200: return []
            
            matches = re.findall(r'/yarn-clip/([a-f0-9\-]+)', resp.text)
            unique_matches = list(dict.fromkeys(matches)) # Preservar orden y quitar duplicados
            
            for i, clip_id in enumerate(unique_matches[:count]):
                video_url = f"https://y.yarn.co/{clip_id}.mp4"
                filename = save_dir / f"yarn_clip_{i:03d}.mp4"
                
                # Descarga simple
                r = self.session.get(video_url, stream=True)
                if r.status_code == 200:
                    with open(filename, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                    
                    clips.append({
                        "path": str(filename),
                        "type": "video",
                        "duration": 5,
                        "keyword": keyword,
                        "source": "getyarn",
                        "width": 1280,
                        "height": 720
                    })
                    logger.info(f"✓ Clip descargado de GetYarn: {filename}")
        except Exception as e:
            logger.error(f"Error en GetYarn: {e}")
        return clips

    def _get_tmdb_id(self, title: str) -> Optional[int]:
        try:
            params = {
                "api_key": self.tmdb_api_key,
                "query": title,
                "language": "es-ES"
            }
            resp = self.session.get(self.tmdb_search_url, params=params, timeout=10)
            resp.raise_for_status()
            results = resp.json().get("results", [])
            if results:
                return results[0].get("id")
        except Exception as e:
            logger.error(f"Error buscando TMDB ID: {e}")
        return None

    def _get_kinocheck_videos(self, tmdb_id: int) -> List[Dict]:
        try:
            # Intentar en inglés para más resultados
            url = f"{self.kinocheck_base}/movies?tmdb_id={tmdb_id}&language=en"
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            
            videos = data.get("videos", [])
            # También incluir el trailer principal si existe
            if data.get("trailer"):
                videos.insert(0, data["trailer"])
                
            return videos
        except Exception as e:
            logger.error(f"Error obteniendo videos de KinoCheck: {e}")
        return []

    def _download_yt_fragment(self, yt_id: str, output_path: Path) -> bool:
        """
        Descarga un fragmento de 8 segundos de un video de YouTube usando yt-dlp.
        """
        try:
            yt_url = f"https://www.youtube.com/watch?v={yt_id}"
            
            # Seleccionar un punto de inicio aleatorio entre el segundo 20 y 60 (evitar intros)
            start_time = random.randint(20, 60)
            
            # Comando para descargar fragmento sin descargar todo el video
            # Usamos ffmpeg a través de yt-dlp para descargar solo la parte necesaria
            cmd = [
                "yt-dlp",
                "-f", "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]",
                "--external-downloader", "ffmpeg",
                "--external-downloader-args", f"ffmpeg_i:-ss {start_time} -t 8",
                "--output", str(output_path),
                yt_url
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0 and output_path.exists():
                return True
            else:
                logger.error(f"Error yt-dlp (Return code {result.returncode}): {result.stderr}")
                logger.error(f"yt-dlp stdout: {result.stdout}")
                return False
        except Exception as e:
            logger.error(f"Error descargando fragmento de YT: {e}")
            return False
