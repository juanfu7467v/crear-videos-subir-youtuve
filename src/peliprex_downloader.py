import logging
import os
import random
import subprocess
import requests
import time
import re
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

    def clean_movie_title(self, text: str) -> str:
        """
        Extrae el nombre de la película de un título o frase del guion.
        Nota: Esta función se mantiene por compatibilidad, pero ahora se prefiere peliprex_search_term de la IA.
        """
        if not text: return ""
        
        # 1. Eliminar puntuación inicial y final
        clean = re.sub(r'^[¿¡"\'\s]+|[?!"\'\s:]+$', '', text)
        
        # 2. Lista de palabras que suelen preceder al título real
        prefixes = [
            r'reboots\s+como\s+', r'como\s+', r'sobre\s+', r'de\s+', 
            r'película\s+de\s+', r'película\s+', r'film\s+de\s+', r'film\s+',
            r'historia\s+de\s+', r'resumen\s+de\s+', r'análisis\s+de\s+'
        ]
        
        for prefix in prefixes:
            match = re.search(prefix, clean, re.IGNORECASE)
            if match:
                # Tomamos todo lo que sigue al prefijo
                clean = clean[match.end():].strip()
                break
        
        # 3. Eliminar frases comunes que vienen después del título
        suffixes = [
            r'\s+es\s+increíble.*', r'\s+cambió\s+el\s+cine.*', r'\s+en\s+minutos.*',
            r'\s+explicado.*', r'\s+crítica.*', r'\s+review.*'
        ]
        for suffix in suffixes:
            clean = re.sub(suffix, '', clean, flags=re.IGNORECASE)
        
        # 4. Limpieza final: si sigue siendo muy largo, tomamos las primeras 3-4 palabras
        words = clean.split()
        if len(words) > 4:
            clean = " ".join(words[:4])
            
        logger.info(f"Título original: '{text}' -> Título limpio para búsqueda: '{clean}'")
        return clean

    def search_movie(self, movie_title: str) -> List[Dict]:
        """Busca una película en la API de Peliprex usando el término exacto proporcionado."""
        if not movie_title:
            return []
            
        try:
            params = {"q": movie_title}
            headers = {"User-Agent": random.choice(self.user_agents)}
            logger.info(f"Consultando API Peliprex: {self.base_url}?q={movie_title}")
            resp = self.session.get(self.base_url, params=params, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            
            if isinstance(data, list):
                # Filtrar estrictamente para ignorar resultados que sean solo de YouTube
                valid_results = []
                for item in data:
                    url = item.get("pelicula_url") or item.get("direct_link") or item.get("stream_url")
                    if url and not any(yt in url for yt in ["youtube.com", "youtu.be", "googlevideo.com"]):
                        valid_results.append(item)
                
                logger.info(f"Encontrados {len(data)} resultados, {len(valid_results)} son archivos directos (Telegram).")
                return valid_results
            return []
        except Exception as e:
            logger.error(f"Error buscando en Peliprex API: {e}")
            return []

    def download_fragment(self, video_url: str, save_path: Path, start_time: int, duration: int) -> bool:
        """Descarga un fragmento corto del video usando ffmpeg directamente desde la URL."""
        if any(yt in video_url for yt in ["youtube.com", "youtu.be", "googlevideo.com"]):
            logger.warning(f"Omitiendo enlace de YouTube detectado en descarga: {video_url}")
            return False

        # Formatear tiempo para ffmpeg (HH:MM:SS)
        start_str = time.strftime('%H:%M:%S', time.gmtime(start_time))
        end_time = start_time + duration
        end_str = time.strftime('%H:%M:%S', time.gmtime(end_time))
        
        logger.info(f"Descargando fragmento de {duration}s desde {start_str} hasta {end_str}...")
        
        cmd_stable = [
            'ffmpeg', '-y',
            '-ss', start_str,
            '-to', end_str,
            '-i', video_url,
            '-c:v', 'libx264', 
            '-preset', 'superfast', 
            '-crf', '28',
            '-c:a', 'aac', 
            '-strict', 'experimental',
            '-pix_fmt', 'yuv420p',
            '-movflags', '+faststart',
            '-maxrate', '2M', 
            '-bufsize', '4M',
            str(save_path)
        ]
        
        try:
            result = subprocess.run(cmd_stable, capture_output=True, text=True, timeout=600)
            
            if result.returncode == 0 and save_path.exists() and save_path.stat().st_size > 10240:
                logger.info(f"Fragmento descargado exitosamente: {save_path.name}")
                return True
            
            error_msg = result.stderr if result.stderr else "No stderr output"
            logger.error(f"FALLO FFmpeg en {save_path.name}: {error_msg}")
            return False
            
        except subprocess.TimeoutExpired:
            logger.error(f"TIMEOUT: FFmpeg tardó demasiado en descargar {save_path.name}")
            return False
        except Exception as e:
            logger.error(f"Excepción inesperada en Peliprex download: {str(e)}")
            return False

    def _normalize_text(self, text: str) -> str:
        """Normaliza el texto para comparaciones."""
        text = text.lower()
        text = text.replace("-", " ")
        text = re.sub(r'[^a-z0-9\s]', '', text)
        return text.strip()

    def generate_peliprex_link(self, movie_name: str) -> str:
        """Genera el enlace de Peliprex para una película dada."""
        if not movie_name:
            return ""
        # Codificar el nombre de la película para la URL
        encoded_movie_name = requests.utils.quote(movie_name)
        return f"https://masitaprex.com/PeliPREX?movie={encoded_movie_name}"

    def fetch_movie_clips(self, movie_title: str, save_dir: Path, clips_needed: int = 3) -> List[Dict]:
        """Busca y descarga varios clips cortos de una película en Peliprex con filtrado inteligente."""
        normalized_query = self._normalize_text(movie_title)
        
        results = self.search_movie(movie_title)
        
        if not results:
            logger.warning(f"No se encontraron archivos directos en Peliprex para '{movie_title}'")
            return []

        # Filtrado de títulos que coinciden con lo buscado
        filtered_results = []
        for res in results:
            res_title = res.get('titulo', '')
            normalized_res_title = self._normalize_text(res_title)
            
            if normalized_query in normalized_res_title or normalized_res_title in normalized_query:
                filtered_results.append(res)
                logger.info(f"Coincidencia encontrada: '{res_title}'")
            else:
                query_words = set(normalized_query.split())
                title_words = set(normalized_res_title.split())
                common_words = query_words.intersection(title_words)
                if len(common_words) >= len(query_words) * 0.5:
                    filtered_results.append(res)
                    logger.info(f"Coincidencia parcial aceptada: '{res_title}'")

        if not filtered_results:
            logger.warning(f"No se encontraron coincidencias satisfactorias para '{movie_title}'.")
            return []

        logger.info(f"Total de películas coincidentes con archivos directos: {len(filtered_results)}")
        
        downloaded_clips = []
        suggested_starts = [600, 1200, 1800, 2400, 3000, 3600, 4200, 4800]
        random.shuffle(suggested_starts)

        for i in range(clips_needed):
            result = filtered_results[i % len(filtered_results)]
            video_url = result.get("pelicula_url") or result.get("direct_link") or result.get("stream_url")
            
            if not video_url:
                continue
            
            start_time = suggested_starts[i % len(suggested_starts)] + random.randint(0, 300)
            duration = 7 # Ritmo 7-10-7
            
            output_path = save_dir / f"peliprex_{len(downloaded_clips):03d}.mp4"
            
            if self.download_fragment(video_url, output_path, start_time, duration):
                downloaded_clips.append({
                    "path": str(output_path),
                    "type": "video",
                    "duration": float(duration),
                    "keyword": movie_title,
                    "source": "peliprex",
                    "title": result.get("titulo", "Unknown"),
                    "width": 1280,
                    "height": 720
                })
            
            if len(downloaded_clips) >= clips_needed:
                break
        
        logger.info(f"Total de clips de Peliprex obtenidos: {len(downloaded_clips)}")
        return downloaded_clips
