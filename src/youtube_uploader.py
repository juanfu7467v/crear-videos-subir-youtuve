import json
import logging
import os
import time
from pathlib import Path
from typing import Optional
from src.oauth2_utils import get_valid_oauth2_data

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    YOUTUBE_AVAILABLE = True
except ImportError:
    YOUTUBE_AVAILABLE = False

logger = logging.getLogger(__name__)

class YouTubeUploader:
    def __init__(self):
        self.youtube = None
        self._initialized = False
        self._current_channel = None
        
        # Mapeo según requerimientos:
        # CHANNEL_NAME -> Canal El Tío Jota (YOUTUBE_CREDENTIALS_FILE)
        # YOUTUBE_CREDENTIALS_FILE_CHANNEL_NAME_2 -> Canal El Criterio
        self.channel_map = {
            "CHANNEL_NAME": "YOUTUBE_CREDENTIALS_FILE",
            "YOUTUBE_CREDENTIALS_FILE_CHANNEL_NAME_2": "YOUTUBE_CREDENTIALS_FILE_CHANNEL_NAME_2"
        }

    def _load_credentials_from_secrets(self, channel_name: str):
        """Carga credenciales desde el secreto de Fly."""
        # PRIORIDAD 1: Usar el nuevo secreto YOUTUBE_OAUTH2_DATA unificado
        oauth2_data = get_valid_oauth2_data()
        if oauth2_data:
            logger.info("Usando el nuevo secreto YOUTUBE_OAUTH2_DATA unificado para la subida.")
            try:
                creds_info = {
                    "token": oauth2_data['token'],
                    "refresh_token": oauth2_data['refresh_token'],
                    "token_uri": oauth2_data['token_uri'],
                    "client_id": oauth2_data['client_id'],
                    "client_secret": oauth2_data['client_secret'],
                    "scopes": oauth2_data.get('scopes', ["https://www.googleapis.com/auth/youtube.upload"])
                }
                creds = Credentials.from_authorized_user_info(creds_info)
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                return creds
            except Exception as e:
                logger.error(f"Error procesando el nuevo secreto unificado: {e}")
        
        # PRIORIDAD 2: Usar los secretos individuales por canal
        # Buscamos directamente en el mapa de canales proporcionado
        creds_env_var = self.channel_map.get(channel_name)
        
        if not creds_env_var:
            # Fallback dinámico si no está en el mapa explícito
            normalized_name = channel_name.strip().upper()
            creds_env_var = f"YOUTUBE_CREDENTIALS_FILE_{normalized_name.replace(' ', '_')}"
        
        logger.info(f"Cargando credenciales desde: {creds_env_var}")
        creds_json = os.getenv(creds_env_var)
        
        if not creds_json:
            logger.error(f"No se encontró el secreto {creds_env_var}")
            return None

        try:
            data = json.loads(creds_json)
            scopes = data.get('scopes', ["https://www.googleapis.com/auth/youtube.upload"])
            creds = Credentials.from_authorized_user_info(data, scopes)
            
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            return creds
        except Exception as e:
            logger.error(f"Error procesando credenciales: {e}")
            return None

    def _initialize(self, channel_name: str) -> bool:
        if self._initialized and self._current_channel == channel_name: return True
        
        self._current_channel = channel_name
        self._initialized = False 
        creds = self._load_credentials_from_secrets(channel_name)
        if creds:
            self.youtube = build("youtube", "v3", credentials=creds)
            self._initialized = True
            return True
        return False

    def upload(self, video_path: str, title: str, description: str = "", channel_name: str = "CHANNEL_NAME", **kwargs) -> str:
        if not self._initialize(channel_name):
            logger.error(f"No se pudo inicializar YouTube para el canal {channel_name}.")
            raise Exception(f"Fallo en la inicialización de YouTube para {channel_name}")

        try:
            is_kids = kwargs.get('is_kids', False)
            tags = kwargs.get('tags', [])
            category_id = kwargs.get('category_id', '22')
            
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
            raise e
