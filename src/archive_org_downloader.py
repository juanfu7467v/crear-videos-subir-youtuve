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
        """Busca videos en Archive.org por nombre exacto."""
        if not query:
            return []

        try:
            params = {
                "q": f'title:"{query}" AND mediatype:movies',
                "fl": "identifier,title,description,publicdate,creator,subject,runtime",
                "output": "json",
                "rows": 5, # Limitar a 5 resultados para relevancia
            }
            logger.info(f"Buscando en Archive.org: {query}")
            resp = self.session.get(self.base_search_url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            
            docs = data.get("response", {}).get("docs", [])
            
            # Filtrar por coincidencia exacta de título si es posible
            exact_matches = [doc for doc in docs if doc.get("title", "").lower() == query.lower()]
            if exact_matches:
                logger.info(f"Encontradas {len(exact_matches)} coincidencias exactas en Archive.org para '{query}'.")
                return exact_matches
            
            logger.info(f"Encontrados {len(docs)} resultados en Archive.org para '{query}'.")
            return docs

        except Exception as e:
            logger.error(f"Error buscando en Archive.org API para '{query}': {e}")
            return []

    def get_video_download_url(self, identifier: str) -> Optional[str]:
        """Obtiene la URL de descarga directa de un video MP4 para un identificador dado."""
        try:
            metadata_url = f"{self.base_metadata_url}{identifier}"
            resp = self.session.get(metadata_url, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            files = data.get("files", [])
            video_files = [f for f in files if f.get("format") == "h.264" and f.get("name", "").endswith(".mp4")]
            
            if not video_files:
                video_files = [f for f in files if f.get("format") == "MPEG4" and f.get("name", "").endswith(".mp4")]

            if video_files:
                # Priorizar archivos de mayor tamaño o con 'original' en el nombre si es posible
                video_files.sort(key=lambda x: int(x.get("size", 0)), reverse=True)
                chosen_file = video_files[0]
                
                file_name = chosen_file.get("name")
                if file_name:
                    download_url = f"{self.base_download_url}{identifier}/{file_name}"
                    logger.info(f"URL de descarga de Archive.org encontrada para '{identifier}': {download_url}")
                    return download_url
            return None
        except Exception as e:
            logger.error(f"Error obteniendo URL de descarga de Archive.org para '{identifier}': {e}")
            return None

    def fetch_archive_org_video(self, movie_title: str, save_dir: Path, prefix: str) -> Optional[Dict]:
        """Busca y descarga un video de Archive.org."""
        results = self.search_video(movie_title)
        if not results:
            logger.warning(f"No se encontraron videos en Archive.org para '{movie_title}'.")
            return None

        # Intentar con el primer resultado o uno aleatorio si hay varios
        chosen_result = random.choice(results)
        identifier = chosen_result.get("identifier")
        title = chosen_result.get("title", movie_title)
        runtime_str = chosen_result.get("runtime")
        duration = 0
        if runtime_str:
            try:
                parts = [int(p) for p in runtime_str.split(':')]
                if len(parts) == 3: # HH:MM:SS
                    duration = parts[0] * 3600 + parts[1] * 60 + parts[2]
                elif len(parts) == 2: # MM:SS
                    duration = parts[0] * 60 + parts[1]
                elif len(parts) == 1: # SS
                    duration = parts[0]
            except ValueError:
                logger.debug(f"No se pudo parsear la duración '{runtime_str}'.")
        
        if duration == 0: # Fallback a duración por defecto si no se pudo obtener
            duration = 60 # Asumir 60 segundos si no se especifica

        video_url = self.get_video_download_url(identifier)
        if not video_url:
            return None

        filename = save_dir / f"{prefix}_archiveorg.mp4"
        if self._download_file(video_url, str(filename)):
            return {
                "path": str(filename),
                "type": "video",
                "duration": float(duration),
                "keyword": movie_title,
                "source": "archive.org",
                "title": title,
                "width": 1280, # Valores por defecto, pueden ser ajustados si se obtienen de metadata
                "height": 720
            }
        return None

    def _download_file(self, url: str, path: str) -> bool:
        """Descarga un archivo desde una URL a una ruta específica."""
        try:
            resp = self.session.get(url, stream=True, timeout=30)
            resp.raise_for_status()
            with open(path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            logger.info(f"Archivo descargado exitosamente: {path}")
            return True
        except Exception as e:
            logger.error(f"Error descargando archivo desde '{url}' a '{path}': {e}")
            return False
