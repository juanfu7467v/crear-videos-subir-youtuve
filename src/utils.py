import subprocess
import logging
import json
import os
from pathlib import Path

logger = logging.getLogger(__name__)

def validate_video(video_path: str) -> bool:
    """
    Valida si un archivo de video es válido usando ffprobe.
    Verifica que tenga un stream de video y una duración válida.
    """
    if not video_path or not os.path.exists(video_path):
        return False
    
    if os.path.getsize(video_path) == 0:
        return False

    try:
        cmd = [
            "ffprobe", 
            "-v", "error", 
            "-show_entries", "format=duration:stream=codec_type", 
            "-of", "json", 
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode != 0:
            logger.warning(f"ffprobe falló para {video_path}: {result.stderr}")
            return False
        
        data = json.loads(result.stdout)
        
        # Verificar duración
        duration = data.get("format", {}).get("duration")
        if duration is None or duration == "N/A":
            logger.warning(f"Video sin duración válida: {video_path}")
            return False
        
        # Verificar stream de video
        streams = data.get("streams", [])
        has_video = any(s.get("codec_type") == "video" for s in streams)
        if not has_video:
            logger.warning(f"Archivo no contiene stream de video: {video_path}")
            return False
            
        return True
    except Exception as e:
        logger.error(f"Error validando video {video_path}: {e}")
        return False

def cleanup_ffmpeg():
    """
    Intenta cerrar procesos de ffmpeg que hayan quedado huérfanos.
    """
    try:
        if os.name == 'posix':
            subprocess.run(["pkill", "-f", "ffmpeg"], capture_output=True)
    except Exception as e:
        logger.debug(f"Error limpiando ffmpeg: {e}")
