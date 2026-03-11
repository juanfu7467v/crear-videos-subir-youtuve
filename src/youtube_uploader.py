"""
youtube_uploader.py
────────────────────
Sube videos automáticamente a YouTube usando la API v3.
Gestiona autenticación OAuth2 leyendo desde Secrets de Fly.io.
"""

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Intentar importar librerías de Google
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    YOUTUBE_AVAILABLE = True
except ImportError:
    YOUTUBE_AVAILABLE = False
    logger.warning("google-api-python-client no instalado. Subida desactivada.")

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]

class YouTubeUploader:
    """
    Sube videos a YouTube usando credenciales desde variables de entorno (Secrets).
    """

    def __init__(self, credentials_path: str = "credentials/youtube_credentials.json"):
        # Mantenemos la compatibilidad con archivos, pero priorizaremos Secrets
        self.credentials_path = credentials_path
        self.youtube = None
        self._initialized = False

    def _initialize(self) -> bool:
        """Inicializa el cliente de YouTube API."""
        if not YOUTUBE_AVAILABLE:
            logger.error("Librerías de Google no disponibles")
            return False

        try:
            creds = self._load_credentials_from_secrets()
            if creds:
                self.youtube = build("youtube", "v3", credentials=creds)
                self._initialized = True
                logger.info("✅ YouTube API inicializado correctamente desde Secrets")
                return True
        except Exception as e:
            logger.error(f"Error inicializando YouTube API: {e}")

        return False

    def _load_credentials_from_secrets(self):
        """Carga las credenciales directamente desde la variable de entorno de Fly.io."""
        creds_json = os.getenv("YOUTUBE_CREDENTIALS_FILE")
        
        if not creds_json:
            logger.error("❌ Secret 'YOUTUBE_CREDENTIALS_FILE' no encontrado en Fly.io")
            return None

        try:
            # Si el secreto viene como string (común en Fly), lo parseamos a dict
            if isinstance(creds_json, str):
                # Limpiar posibles comillas simples si se pegó mal el JSON
                creds_data = json.loads(creds_json.replace("'", '"'))
            else:
                creds_data = creds_json

            creds = Credentials.from_authorized_user_info(creds_data, SCOPES)
            
            # Si el token expiró, intentar refrescarlo
            if creds and creds.expired and creds.refresh_token:
                logger.info("Refrescando token de YouTube...")
                creds.refresh(Request())
                
            return creds
        except Exception as e:
            logger.error(f"Error parseando credenciales desde Secrets: {e}")
            return None

    def upload(
        self,
        video_path: str,
        title: str,
        description: str = "",
        tags: list = None,
        category_id: str = "22",
        is_short: bool = False,
        publish_at: Optional[datetime] = None,
        thumbnail_path: Optional[str] = None,
        privacy: str = "public",
    ) -> str:
        """Sube un video a YouTube."""
        if not self._initialized:
            if not self._initialize():
                logger.warning("YouTube no disponible o sin credenciales. Simulando subida.")
                return self._simulate_upload(title)

        if not Path(video_path).exists():
            raise FileNotFoundError(f"Video no encontrado: {video_path}")

        # Configuración básica de metadatos
        if is_short and "#shorts" not in title.lower():
            title = f"{title} #shorts"

        body = {
            "snippet": {
                "title": title[:100],
                "description": description or f"{title}\n\n#ElTioJota #Viral",
                "tags": tags or ["ElTioJota", "viral"],
                "categoryId": category_id,
            },
            "status": {
                "privacyStatus": "private" if publish_at else privacy,
                "selfDeclaredMadeForKids": False,
            },
        }

        if publish_at:
            body["status"]["publishAt"] = publish_at.strftime("%Y-%m-%dT%H:%M:%S.000Z")

        try:
            media = MediaFileUpload(
                video_path,
                mimetype="video/mp4",
                resumable=True,
                chunksize=10 * 1024 * 1024
            )

            request = self.youtube.videos().insert(
                part=",".join(body.keys()),
                body=body,
                media_body=media
            )

            video_id = self._execute_upload(request)
            
            if video_id:
                if thumbnail_path and Path(thumbnail_path).exists():
                    self._upload_thumbnail(video_id, thumbnail_path)
                return f"https://youtu.be/{video_id}"
                
        except Exception as e:
            logger.error(f"Error durante la subida: {e}")
            
        return self._simulate_upload(title)

    def _execute_upload(self, request):
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                logger.info(f"Subiendo a YouTube: {int(status.progress() * 100)}%")
        return response.get("id")

    def _upload_thumbnail(self, video_id, thumbnail_path):
        try:
            self.youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumbnail_path, mimetype="image/jpeg")
            ).execute()
            logger.info("Thumbnail subida correctamente")
        except:
            logger.warning("No se pudo subir la thumbnail")

    def _simulate_upload(self, title: str) -> str:
        fake_id = f"SIMULATED_{int(time.time())}"
        url = f"https://youtu.be/{fake_id}"
        logger.info(f"[SIMULADO] Video '{title}' subido: {url}")
        return url
