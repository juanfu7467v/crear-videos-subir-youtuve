import json
import logging
import os
import time
from pathlib import Path
from typing import Optional, Dict
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
        
        # Mapeo inicial (mantenido por compatibilidad)
        self.channel_map = {
            "CHANNEL_NAME": "YOUTUBE_CREDENTIALS_FILE",
            "YOUTUBE_CREDENTIALS_FILE": "YOUTUBE_CREDENTIALS_FILE",
            "YOUTUBE_CREDENTIALS_FILE_CHANNEL_NAME_2": "YOUTUBE_CREDENTIALS_FILE_CHANNEL_NAME_2"
        }

    def _get_credentials_var_name(self, channel_input: str) -> str:
        """Determina el nombre de la variable de entorno para las credenciales de un canal."""
        clean_input = str(channel_input).strip()
        
        # 1. Verificar si ya es una variable de entorno conocida (escalabilidad dinámica)
        # El patrón es YOUTUBE_CREDENTIALS_FILE_<CHANNEL_NAME>
        # Pero para los canales originales mantenemos sus nombres específicos
        
        if clean_input == "CHANNEL_NAME" or clean_input == "YOUTUBE_CREDENTIALS_FILE":
            return "YOUTUBE_CREDENTIALS_FILE"
        
        if "Criterio" in clean_input or clean_input == "CHANNEL_NAME_2" or clean_input == "YOUTUBE_CREDENTIALS_FILE_CHANNEL_NAME_2":
            return "YOUTUBE_CREDENTIALS_FILE_CHANNEL_NAME_2"
        
        # 2. Escalabilidad dinámica: CHANNEL_NAME_3 -> YOUTUBE_CREDENTIALS_FILE_CHANNEL_NAME_3
        # Si el input es CHANNEL_NAME_X, buscamos YOUTUBE_CREDENTIALS_FILE_CHANNEL_NAME_X
        if clean_input.startswith("CHANNEL_NAME_"):
            return f"YOUTUBE_CREDENTIALS_FILE_{clean_input}"
        
        # 3. Fallback: Si no coincide con lo anterior, intentamos ver si existe como variable de entorno directa
        # o si es un nombre de canal que tiene una variable asociada siguiendo el patrón
        potential_var = f"YOUTUBE_CREDENTIALS_FILE_{clean_input.upper().replace(' ', '_')}"
        if os.getenv(potential_var):
            return potential_var
            
        return "YOUTUBE_CREDENTIALS_FILE" # Fallback final al canal 1

    def _load_credentials_from_secrets(self, channel_input: str):
        """Carga credenciales desde el secreto de Fly con soporte para múltiples canales."""
        
        # PRIORIDAD 1: Usar el nuevo secreto YOUTUBE_OAUTH2_DATA unificado (si existe)
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
        
        # PRIORIDAD 2: Mapeo dinámico de canales
        creds_env_var = self._get_credentials_var_name(channel_input)
        
        logger.info(f"Cargando credenciales para canal '{channel_input}' desde el secret: {creds_env_var}")
        creds_json = os.getenv(creds_env_var)
        
        if not creds_json:
            logger.error(f"ERROR: No se encontró el secret {creds_env_var} en el entorno.")
            # Si falló el dinámico, intentar con el canal 1 por defecto
            if creds_env_var != "YOUTUBE_CREDENTIALS_FILE":
                logger.warning("Intentando fallback al canal principal (YOUTUBE_CREDENTIALS_FILE)")
                creds_json = os.getenv("YOUTUBE_CREDENTIALS_FILE")
            
            if not creds_json:
                return None

        try:
            data = json.loads(creds_json)
            scopes = data.get('scopes', ["https://www.googleapis.com/auth/youtube.upload"])
            creds = Credentials.from_authorized_user_info(data, scopes)
            
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            return creds
        except Exception as e:
            logger.error(f"Error procesando el JSON del secret {creds_env_var}: {e}")
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
            logger.error(f"Fallo crítico: No se pudo inicializar YouTube para '{channel_name}'.")
            raise Exception(f"Fallo en la inicialización de YouTube para {channel_name}")

        try:
            is_kids = kwargs.get('is_kids', False)
            tags = kwargs.get('tags', [])
            category_id = kwargs.get('category_id', '22')
            
            body = {
                "snippet": {
                    "title": title[:100].strip(), 
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
            if video_id and thumbnail_path:
                if os.path.exists(thumbnail_path):
                    logger.info(f"Intentando subir miniatura desde: {thumbnail_path} para el video {video_id}")
                    try:
                        self.youtube.thumbnails().set(
                            videoId=video_id,
                            media_body=MediaFileUpload(thumbnail_path)
                        ).execute()
                        logger.info(f"✅ Miniatura subida correctamente para el video {video_id}.")
                    except Exception as e:
                        logger.warning(f"⚠️ No se pudo subir la miniatura: {e}")
                else:
                    logger.warning(f"⚠️ El archivo de miniatura no existe en la ruta: {thumbnail_path}")

            return f"https://youtu.be/{video_id}"
        except Exception as e:
            logger.error(f"Error real subiendo a YouTube: {e}")
            raise e
