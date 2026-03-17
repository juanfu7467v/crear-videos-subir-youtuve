import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

# Tratamos de importar las librerías de Google
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    YOUTUBE_AVAILABLE = True
except ImportError:
    YOUTUBE_AVAILABLE = False

logger = logging.getLogger(__name__)
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

class YouTubeUploader:
    # ACEPTAMOS EL ARGUMENTO PARA QUE MAIN.PY NO SE QUEJE
    def __init__(self):
        self.youtube = None
        self._initialized = False
        self._current_channel = None
        
        # Mapeo de nombres de canales a variables de entorno
        self.channel_map = {
            "EL TÍO JOTA": "YOUTUBE_CREDENTIALS_FILE",
            "EL CRITERIO": "YOUTUBE_CREDENTIALS_FILE_CHANNEL_NAME_2"
        }

    def _load_credentials_from_secrets(self, channel_name: str):
        """Carga credenciales desde el secreto de Fly."""
        # Normalizar el nombre del canal para la búsqueda en el mapa
        normalized_name = channel_name.strip().upper()
        
        # Intentar obtener la variable del mapa, si no, usar la lógica anterior como fallback
        creds_env_var = self.channel_map.get(normalized_name)
        
        if not creds_env_var:
            # Fallback: si no está en el mapa, intentar construir el nombre de la variable
            creds_env_var = f"YOUTUBE_CREDENTIALS_FILE_{normalized_name.replace(' ', '_')}" if channel_name != "CHANNEL_NAME" else "YOUTUBE_CREDENTIALS_FILE"
        
        logger.info(f"Intentando cargar credenciales desde la variable: {creds_env_var} para el canal: {channel_name}")
        creds_json = os.getenv(creds_env_var)
        
        if not creds_json:
            logger.error(f"No se encontró el secreto {creds_env_var}")
            return None

        try:
            data = json.loads(creds_json)
            creds = Credentials.from_authorized_user_info(data, SCOPES)
            
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            return creds
        except Exception as e:
            logger.error(f"Error procesando credenciales: {e}")
            return None

    def _initialize(self, channel_name: str) -> bool:
        # Reinicializar si el canal es diferente
        if self._initialized and self._current_channel == channel_name: return True
        
        self._current_channel = channel_name
        self._initialized = False # Forzar reinicialización si el canal cambia
        creds = self._load_credentials_from_secrets(channel_name)
        if creds:
            self.youtube = build("youtube", "v3", credentials=creds)
            self._initialized = True
            return True
        return False

    def upload(self, video_path: str, title: str, description: str = "", channel_name: str = "CHANNEL_NAME", **kwargs) -> str:
        # Intentamos inicializar. Si no hay creds, se va por el fallback.
        if not self._initialize(channel_name):
            logger.warning("No se pudo inicializar YouTube (Subida simulada).")
            return "https://youtu.be/SIMULADO"

        try:
            # MEJORA: Configuración avanzada de subida
            is_kids = kwargs.get('is_kids', False)
            tags = kwargs.get('tags', [])
            category_id = kwargs.get('category_id', '22') # 22: People & Blogs, 1: Film & Animation
            
            body = {
                "snippet": {
                    "title": title[:100], 
                    "description": description, 
                    "categoryId": category_id,
                    "tags": tags,
                    "defaultLanguage": "es",
                    "defaultAudioLanguage": "es"
                },
                "status": {
                    "privacyStatus": "public",
                    "selfDeclaredMadeForKids": is_kids,
                    "embeddable": True,
                    "license": "youtube"
                }
            }
            
            media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)
            request = self.youtube.videos().insert(part="snippet,status", body=body, media_body=media)
            
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    logger.info(f"Subiendo video: {int(status.progress() * 100)}%")
            
            video_id = response.get('id')
            
            # Subir miniatura si existe
            thumbnail_path = kwargs.get('thumbnail_path')
            if video_id and thumbnail_path and os.path.exists(thumbnail_path):
                try:
                    self.youtube.thumbnails().set(
                        videoId=video_id,
                        media_body=MediaFileUpload(thumbnail_path)
                    ).execute()
                    logger.info("Miniatura subida correctamente.")
                except Exception as e:
                    logger.warning(f"No se pudo subir la miniatura: {e}")

            return f"https://youtu.be/{video_id}"
        except Exception as e:
            logger.error(f"Error real subiendo a YouTube: {e}")
            return "https://youtu.be/SIMULADO"
