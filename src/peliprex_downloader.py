import logging
import os
import random
import subprocess
import requests
import time
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class PeliprexDownloader:
    """
    Busca películas en la API de Peliprex y descarga fragmentos cortos usando ffmpeg.
    Optimizado para bajo uso de RAM y ancho de banda mediante descargas parciales.
    """
    def __init__(self):
        self.base_url = "https://peliprex-31wrsa.fly.dev/search"
        self.session = requests.Session()
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ]

    def search_movie(self, movie_title: str) -> List[Dict]:
        """Busca una película en la API de Peliprex."""
        try:
            params = {"q": movie_title}
            headers = {"User-Agent": random.choice(self.user_agents)}
            resp = self.session.get(self.base_url, params=params, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            
            if isinstance(data, list):
                logger.info(f"Encontrados {len(data)} resultados en Peliprex para '{movie_title}'")
                return data
            return []
        except Exception as e:
            logger.error(f"Error buscando en Peliprex API: {e}")
            return []

    def download_fragment(self, video_url: str, save_path: Path, start_time: int, duration: int) -> bool:
        """Descarga un fragmento corto del video usando ffmpeg directamente desde la URL."""
        # Formatear tiempo para ffmpeg (HH:MM:SS)
        start_str = time.strftime('%H:%M:%S', time.gmtime(start_time))
        
        # Intentar primero con copy (rápido, bajo CPU/RAM)
        # Usamos -ss antes de -i para descarga parcial real (Input Seeking)
        cmd = [
            'ffmpeg', '-y',
            '-ss', start_str,
            '-t', str(duration),
            '-i', video_url,
            '-c', 'copy',
            '-map', '0:v:0',
            '-map', '0:a:0',
            '-avoid_negative_ts', 'make_zero',
            str(save_path)
        ]

        logger.info(f"Descargando fragmento de {duration}s desde {start_str}...")
        
        try:
            # Ejecutar con timeout para evitar bloqueos
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0 and save_path.exists() and save_path.stat().st_size > 10240:
                logger.info(f"Fragmento guardado exitosamente: {save_path.name}")
                return True
            
            # Si falla el 'copy', intentar recodificando (más robusto pero usa más recursos)
            logger.warning(f"Fallo 'copy', reintentando con recodificación para {save_path.name}...")
            cmd_recode = [
                'ffmpeg', '-y',
                '-ss', start_str,
                '-t', str(duration),
                '-i', video_url,
                '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28',
                '-c:a', 'aac', '-b:a', '128k',
                '-maxrate', '2M', '-bufsize', '2M', # Limitar bitrate para RAM/ancho de banda
                str(save_path)
            ]
            result = subprocess.run(cmd_recode, capture_output=True, text=True, timeout=180)
            
            if result.returncode == 0 and save_path.exists() and save_path.stat().st_size > 10240:
                logger.info(f"Fragmento recodificado exitosamente: {save_path.name}")
                return True
                
            logger.error(f"Error descargando fragmento: {result.stderr[:200]}")
            return False
        except Exception as e:
            logger.error(f"Excepción en Peliprex download: {e}")
            return False

    def fetch_movie_clips(self, movie_title: str, save_dir: Path, clips_needed: int = 3) -> List[Dict]:
        """Busca y descarga varios clips cortos de una película en Peliprex."""
        search_query = movie_title.split(".")[0].replace("_", " ").replace("-", " ")
        results = self.search_movie(search_query)
        
        if not results:
            logger.warning(f"No se encontraron resultados en Peliprex para '{search_query}'")
            return []

        # MEJORA 1: Filtrado Estricto por Título
        # Implementar una validación de similitud para evitar clips de películas erróneas.
        filtered_results = []
        for res in results:
            res_title = res.get('titulo', '').lower()
            if search_query.lower() in res_title or any(word in res_title for word in search_query.lower().split()):
                filtered_results.append(res)
        
        # Si el filtrado estricto no devuelve nada, intentamos con los primeros 3 resultados originales como fallback
        # pero priorizamos la coincidencia exacta si existe.
        if not filtered_results:
            logger.warning(f"No hay coincidencias exactas para '{search_query}', probando resultados generales.")
            target_results = results[:3]
        else:
            logger.info(f"Filtrado estricto: {len(filtered_results)} coincidencias para '{search_query}'")
            target_results = filtered_results[:3]

        downloaded_clips = []
        
        # MEJORA 2: Evitar el "Inicio en Negro" (Offset de Tiempo)
        # No extraer desde el segundo 0. Configurar un punto de inicio entre el minuto 10 y el 60.
        # 10 min = 600s, 60 min = 3600s
        suggested_starts = [600, 1200, 1800, 2400, 3000, 3600]
        random.shuffle(suggested_starts)

        for i in range(clips_needed):
            # Rotar entre los mejores resultados
            result = target_results[i % len(target_results)]
            video_url = result.get("pelicula_url")
            
            if not video_url:
                continue

            # Usar offset de tiempo (mínimo 10 minutos)
            start_time = suggested_starts[i % len(suggested_starts)] + random.randint(0, 300)
            duration = 7 # MEJORA 3: Clips de Peliprex de máximo 7 segundos según Ritmo 7-10-7
            
            output_path = save_dir / f"peliprex_{len(downloaded_clips):03d}.mp4"
            
            if self.download_fragment(video_url, output_path, start_time, duration):
                downloaded_clips.append({
                    "path": str(output_path),
                    "type": "video",
                    "duration": float(duration),
                    "keyword": movie_title,
                    "source": "peliprex",
                    "width": 1280,
                    "height": 720
                })
            
            if len(downloaded_clips) >= clips_needed:
                break
        
        logger.info(f"Total de clips de Peliprex obtenidos: {len(downloaded_clips)}")
        return downloaded_clips
