import json
import logging
import os
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

logger = logging.getLogger(__name__)

class YouTubeUploader:
    # Aceptamos el argumento path_arg para que main.py no falle
    def __init__(self, path_arg: str = None):
        self.youtube = None
        self._initialized = False
        self.credentials_path = path_arg

    def _load_credentials_from_secrets(self):
        """Carga y refresca credenciales desde el secreto de Fly."""
        creds_json = os.getenv("YOUTUBE_CREDENTIALS_FILE")
        if not creds_json:
            logger.error("No se encontró el secreto YOUTUBE_CREDENTIALS_FILE")
            return None

        try:
            data = json.loads(creds_json)
            creds = Credentials.from_authorized_user_info(data, ["https://www.googleapis.com/auth/youtube.upload"])
            
            if creds and creds.expired and creds.refresh_token:
                logger.info("Refrescando token de YouTube...")
                creds.refresh(Request())
            
            return creds
        except Exception as e:
            logger.error(f"Error procesando credenciales: {e}")
            return None

    def _initialize(self) -> bool:
        if self._initialized: return True
        creds = self._load_credentials_from_secrets()
        if creds:
            try:
                self.youtube = build("youtube", "v3", credentials=creds)
                self._initialized = True
                return True
            except Exception as e:
                logger.error(f"Error construyendo servicio YouTube: {e}")
        return False

    def upload(self, video_path: str, title: str, description: str = "", **kwargs) -> str:
        if not self._initialize():
            logger.warning("Subida simulada (sin credenciales).")
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
            logger.error(f"Error subiendo a YouTube: {e}")
            return "https://youtu.be/SIMULADO"
