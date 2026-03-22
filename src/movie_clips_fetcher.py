import logging
import os
import random
import requests
import subprocess
import shutil
from pathlib import Path
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

class MovieClipsFetcher:
    """
    Busca y descarga clips de películas usando KinoCheck API, GetYarn y Pexels.
    Se ha eliminado la dependencia de YouTube.
    """
    def __init__(self):
        self.kinocheck_base = "https://api.kinocheck.com"
        self.tmdb_search_url = "https://api.themoviedb.org/3/search/movie"
        self.tmdb_api_key = os.getenv("TMDB_API_KEY")
        self.session = requests.Session()

    def fetch_movie_clips(self, movie_title: str, save_dir: Path, clips_needed: int = 5) -> List[Dict]:
        """
        Busca una película, obtiene sus clips de fuentes alternativas a YouTube.
        """
        logger.info(f"🎬 Buscando clips alternativos para: {movie_title}")
        
        downloaded_clips = []
        
        # 1. Fallback a GetYarn (Clips cortos de películas)
        logger.info(f"Buscando clips en GetYarn para '{movie_title}'...")
        yarn_clips = self._fetch_yarn_clips(movie_title, save_dir, clips_needed)
        downloaded_clips.extend(yarn_clips)
            
        # 2. Fallback a Pexels (Stock) si aún faltan clips
        if len(downloaded_clips) < clips_needed:
            logger.info(f"Buscando clips de stock en Pexels para '{movie_title}'...")
            pexels_clips = self._fetch_pexels_fallback(movie_title, save_dir, clips_needed - len(downloaded_clips))
            downloaded_clips.extend(pexels_clips)

        return downloaded_clips

    def _fetch_pexels_fallback(self, keyword: str, save_dir: Path, count: int) -> List[Dict]:
        """Descarga clips de Pexels como recurso de stock."""
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
                    
                    target = next((f for f in video_files if f.get("width", 0) <= 1920), video_files[0])
                    video_url = target.get("link")
                    filename = save_dir / f"pexels_fallback_{len(clips):03d}.mp4"
                    
                    r = self.session.get(video_url, stream=True)
                    with open(filename, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                            
                    clips.append({
                        "path": str(filename),
                        "type": "video",
                        "duration": v.get("duration", 10),
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
            unique_matches = list(dict.fromkeys(matches))
            
            for i, clip_id in enumerate(unique_matches[:count]):
                video_url = f"https://y.yarn.co/{clip_id}.mp4"
                filename = save_dir / f"yarn_clip_{len(clips):03d}.mp4"
                
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
