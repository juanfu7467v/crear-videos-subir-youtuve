import logging
import random
import requests
import subprocess
import time
import re
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class ArchiveDownloader:
    """
    Nueva clase para interactuar con Internet Archive (Archive.org) de forma inteligente.
    Busca contenido basado en metadatos, colecciones y palabras clave para maximizar la diversidad.
    """
    def __init__(self):
        self.base_search_url = "https://archive.org/advancedsearch.php"
        self.base_metadata_url = "https://archive.org/metadata/"
        self.base_download_url = "https://archive.org/download/"
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "ElTioJota-AutoVideo/2.0 (ArchiveDownloader)"})
        
        # Colecciones populares de video en Archive.org para diversificar
        self.curated_collections = [
            "feature_films", "prelinger", "animationandcartoons", 
            "sci-fihorror", "classic_tv", "stock_footage",
            "moviesandfilms", "silent_films"
        ]

    def search_by_metadata(self, query: str, limit: int = 10) -> List[Dict]:
        """
        Realiza una búsqueda avanzada combinando palabras clave y metadatos.
        """
        if not query:
            return []

        try:
            # Limpiar query para evitar caracteres especiales que rompan la API
            clean_query = re.sub(r'[^a-zA-Z0-9\s]', '', query)
            
            # Construir una consulta que busque en título, descripción y temas
            # Priorizamos mediatype:movies y formatos MP4
            search_query = f'(title:("{clean_query}") OR description:("{clean_query}") OR subject:("{clean_query}")) AND mediatype:movies'
            
            params = {
                "q": search_query,
                "fl": "identifier,title,description,subject,runtime,avg_rating,downloads,collection",
                "sort[]": "downloads desc", # Priorizar lo más popular para asegurar calidad
                "output": "json",
                "rows": limit,
            }
            
            logger.info(f"Búsqueda inteligente en Archive.org (Real-time): {clean_query}")
            resp = self.session.get(self.base_search_url, params=params, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            
            docs = data.get("response", {}).get("docs", [])
            
            # Si no hay resultados, intentar una búsqueda más relajada (palabras sueltas)
            if not docs and " " in clean_query:
                words = clean_query.split()
                # Usar las 2 palabras más largas (suelen ser las más descriptivas)
                words.sort(key=len, reverse=True)
                simple_query = " OR ".join(words[:2])
                params["q"] = f'({simple_query}) AND mediatype:movies'
                logger.info(f"Reintentando búsqueda relajada en Archive.org: {simple_query}")
                resp = self.session.get(self.base_search_url, params=params, timeout=20)
                docs = resp.json().get("response", {}).get("docs", [])

            return docs

        except Exception as e:
            logger.error(f"Error en búsqueda por metadatos Archive.org: {e}")
            return []

    def get_best_video_file(self, identifier: str) -> Optional[Dict]:
        """
        Analiza los archivos de un item y selecciona el mejor MP4 disponible.
        """
        try:
            metadata_url = f"{self.base_metadata_url}{identifier}"
            resp = self.session.get(metadata_url, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            files = data.get("files", [])
            # Filtrar archivos MP4
            video_files = [f for f in files if f.get("name", "").lower().endswith(".mp4")]
            
            if not video_files:
                return None

            # Criterios de selección:
            # 1. Preferir formatos h.264 o MPEG4
            # 2. Preferir archivos con dimensiones conocidas (ej. 720p)
            # 3. Evitar archivos demasiado pequeños (baja calidad) o gigantes (lento)
            
            best_file = None
            max_score = -1

            for f in video_files:
                score = 0
                fmt = f.get("format", "").lower()
                size = int(f.get("size", 0))
                height = int(f.get("height", 0))
                
                if "h.264" in fmt or "mpeg4" in fmt: score += 10
                if 480 <= height <= 1080: score += 20
                if size > 5 * 1024 * 1024: score += 5 # Al menos 5MB
                
                if score > max_score:
                    max_score = score
                    best_file = f

            if best_file:
                file_name = best_file.get("name")
                duration = float(best_file.get("length", 0))
                if duration == 0:
                    # Intentar parsear runtime de metadatos generales
                    runtime_str = data.get("metadata", {}).get("runtime", "")
                    duration = self._parse_runtime(runtime_str)

                return {
                    "url": f"{self.base_download_url}{identifier}/{file_name}",
                    "duration": duration,
                    "width": int(best_file.get("width", 1280)),
                    "height": int(best_file.get("height", 720)),
                    "identifier": identifier,
                    "title": data.get("metadata", {}).get("title", identifier)
                }
            
            return None
        except Exception as e:
            logger.error(f"Error obteniendo mejor archivo de Archive.org ({identifier}): {e}")
            return None

    def _parse_runtime(self, runtime_str: str) -> float:
        if not runtime_str: return 60.0
        try:
            parts = [int(p) for p in str(runtime_str).split(':')]
            if len(parts) == 3: return float(parts[0] * 3600 + parts[1] * 60 + parts[2])
            if len(parts) == 2: return float(parts[0] * 60 + parts[1])
            if len(parts) == 1: return float(parts[0])
        except: pass
        return 60.0

    def download_fragment(self, video_url: str, save_path: Path, duration: int = 10) -> bool:
        """
        Descarga un fragmento aleatorio del video para evitar repeticiones.
        """
        # Intentamos obtener la duración total para elegir un punto de inicio aleatorio
        # Si no la tenemos, empezamos en el segundo 60 (evitar intros)
        # Para Archive.org, a veces es mejor empezar más adelante para evitar intros largas
        start_time = random.randint(120, 600) 
        
        start_str = time.strftime('%H:%M:%S', time.gmtime(start_time))
        
        logger.info(f"Descargando fragmento real de Archive.org ({duration}s) desde {start_str}...")
        
        cmd = [
            'ffmpeg', '-y',
            '-ss', start_str,
            '-t', str(duration),
            '-i', video_url,
            '-c:v', 'libx264', 
            '-preset', 'ultrafast', 
            '-crf', '30', # Un poco más de compresión para velocidad
            '-c:a', 'aac', 
            '-strict', 'experimental',
            '-pix_fmt', 'yuv420p',
            '-movflags', '+faststart',
            '-maxrate', '1.5M', 
            '-bufsize', '3M',
            str(save_path)
        ]
        
        try:
            # Timeout de 2 minutos para Archive.org (puede ser lento)
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0 and save_path.exists() and save_path.stat().st_size > 5000:
                return True
            return False
        except Exception as e:
            logger.error(f"Error descargando fragmento de Archive.org: {e}")
            return False

    def fetch_smart_clips(self, keyword: str, save_dir: Path, clips_needed: int = 1) -> List[Dict]:
        """
        Flujo principal: busca, selecciona y descarga clips variados.
        """
        results = self.search_by_metadata(keyword, limit=15)
        if not results:
            # Fallback: buscar en una colección aleatoria con la palabra clave
            coll = random.choice(self.curated_collections)
            results = self.search_by_metadata(f"collection:({coll}) {keyword}", limit=5)
        
        if not results:
            return []

        random.shuffle(results)
        downloaded = []
        
        for res in results:
            if len(downloaded) >= clips_needed:
                break
                
            video_info = self.get_best_video_file(res['identifier'])
            if not video_info:
                continue
                
            output_path = save_dir / f"archive_{res['identifier']}_{len(downloaded)}.mp4"
            
            # Intentar descargar un fragmento de 10 segundos (ritmo stock)
            if self.download_fragment(video_info['url'], output_path, duration=10):
                downloaded.append({
                    "path": str(output_path),
                    "type": "video",
                    "duration": 10.0,
                    "keyword": keyword,
                    "source": "archive_org_smart",
                    "title": video_info['title'],
                    "width": video_info['width'],
                    "height": video_info['height']
                })
                
        return downloaded
