import logging
import random
import requests
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class ArchiveOrgDownloader:
    def __init__(self):
        self.base_search_url = "https://archive.org/advancedsearch.php"
        self.base_metadata_url = "https://archive.org/metadata/"
        self.base_download_url = "https://archive.org/download/"
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "ElTioJota-AutoVideo/1.0"})

    def search_video(self, query: str) -> List[Dict]:
        """Busca videos en Archive.org por palabras clave."""
        if not query:
            return []

        try:
            # Búsqueda más flexible por palabras clave, limitando a películas y formatos comunes
            params = {
                "q": f'"{query}" AND mediatype:movies AND (format:h.264 OR format:MPEG4)',
                "fl": "identifier,title,description,publicdate,creator,subject,runtime,avg_rating,num_reviews",
                "sort[]": "downloads desc",
                "output": "json",
                "rows": 15,
            }
            logger.info(f"Buscando en Archive.org: {query}")
            resp = self.session.get(self.base_search_url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            
            docs = data.get("response", {}).get("docs", [])
            logger.info(f"Encontrados {len(docs)} resultados en Archive.org para '{query}'.")
            return docs

        except Exception as e:
            logger.error(f"Error buscando en Archive.org API para '{query}': {e}")
            return []

    def get_video_metadata(self, identifier: str) -> Optional[Dict]:
        """Obtiene metadatos detallados y URL de descarga de un video."""
        try:
            metadata_url = f"{self.base_metadata_url}{identifier}"
            resp = self.session.get(metadata_url, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            files = data.get("files", [])
            # Priorizar h.264 (MP4) que suele ser más compatible
            video_files = [f for f in files if f.get("format") in ["h.264", "MPEG4"] and f.get("name", "").endswith(".mp4")]
            
            if video_files:
                # Ordenar por tamaño para intentar obtener mejor calidad, pero evitar archivos excesivamente grandes
                # Filtramos archivos que tengan duración y dimensiones si están disponibles
                video_files.sort(key=lambda x: int(x.get("size", 0)), reverse=True)
                
                # Intentar encontrar uno con dimensiones razonables (cerca de 720p o 1080p)
                chosen_file = video_files[0]
                for f in video_files:
                    height = int(f.get("height", 0))
                    if 480 <= height <= 1080:
                        chosen_file = f
                        break
                
                file_name = chosen_file.get("name")
                if file_name:
                    download_url = f"{self.base_download_url}{identifier}/{file_name}"
                    
                    # Extraer duración si está disponible en el archivo
                    duration = float(chosen_file.get("length", 0))
                    if duration == 0:
                        # Intentar obtener de los metadatos generales del item
                        runtime_str = data.get("metadata", {}).get("runtime")
                        duration = self._parse_runtime(runtime_str) if runtime_str else 60.0

                    return {
                        "url": download_url,
                        "duration": duration,
                        "width": int(chosen_file.get("width", 1280)),
                        "height": int(chosen_file.get("height", 720)),
                        "format": chosen_file.get("format")
                    }
            return None
        except Exception as e:
            logger.error(f"Error obteniendo metadatos de Archive.org para '{identifier}': {e}")
            return None

    def _parse_runtime(self, runtime_str: str) -> float:
        """Convierte strings de tiempo (HH:MM:SS o MM:SS) a segundos."""
        try:
            parts = [int(p) for p in str(runtime_str).split(':')]
            if len(parts) == 3: # HH:MM:SS
                return float(parts[0] * 3600 + parts[1] * 60 + parts[2])
            elif len(parts) == 2: # MM:SS
                return float(parts[0] * 60 + parts[1])
            elif len(parts) == 1: # SS o solo minutos
                return float(parts[0])
        except (ValueError, TypeError):
            pass
        return 60.0

    def fetch_archive_org_video(self, keyword: str, save_dir: Path, prefix: str) -> Optional[Dict]:
        """Busca, selecciona y descarga un video de Archive.org."""
        results = self.search_video(keyword)
        if not results:
            # Reintento con búsqueda menos estricta si falla
            if " " in keyword:
                simple_kw = keyword.split()[0]
                results = self.search_video(simple_kw)
            
        if not results:
            return None

        # Probar con los 3 mejores resultados hasta encontrar un link de descarga válido
        for result in results[:3]:
            identifier = result.get("identifier")
            video_meta = self.get_video_metadata(identifier)
            
            if video_meta and video_meta.get("url"):
                filename = save_dir / f"{prefix}_archiveorg.mp4"
                if self._download_file(video_meta["url"], str(filename)):
                    return {
                        "path": str(filename),
                        "type": "video",
                        "duration": video_meta["duration"],
                        "keyword": keyword,
                        "source": "archive.org",
                        "title": result.get("title", keyword),
                        "width": video_meta["width"],
                        "height": video_meta["height"]
                    }
        return None

    def _download_file(self, url: str, path: str) -> bool:
        """Descarga un archivo desde una URL a una ruta específica."""
        try:
            resp = self.session.get(url, stream=True, timeout=60)
            resp.raise_for_status()
            with open(path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=16384):
                    f.write(chunk)
            logger.info(f"Archivo de Archive.org descargado: {path}")
            return True
        except Exception as e:
            logger.error(f"Error descargando de Archive.org: {e}")
            return False
