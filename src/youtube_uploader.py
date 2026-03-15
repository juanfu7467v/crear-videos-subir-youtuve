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

    def _load_credentials_from_secrets(self, channel_name: str):
        """Carga credenciales desde el secreto de Fly."""
        creds_env_var = f"YOUTUBE_CREDENTIALS_FILE_{channel_name.upper()}" if channel_name != "CHANNEL_NAME" else "YOUTUBE_CREDENTIALS_FILE"
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
            body = {
                "snippet": {"title": title[:100], "description": description, "categoryId": "22"},
                "status": {"privacyStatus": "public"}
            }
            media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)
            request = self.youtube.videos().insert(part="snippet,status", body=body, media_body=media)
            
            response = None
            while response is None:
                _, response = request.next_chunk()
            
            return f"https://youtu.be/{response.get('id')}"
        except Exception as e:
            logger.error(f"Error real subiendo a YouTube: {e}")
            return "https://youtu.be/SIMULADO"
