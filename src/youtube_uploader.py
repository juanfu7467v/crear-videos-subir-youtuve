"""
youtube_uploader.py
────────────────────
Sube videos automáticamente a YouTube usando la API v3.
Gestiona autenticación OAuth2, subida, metadatos y programación.
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Intentar importar librerías de Google
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
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

# Categorías de YouTube
CATEGORIES = {
    "film":         "1",
    "autos":        "2",
    "music":        "10",
    "pets":         "15",
    "sports":       "17",
    "travel":       "19",
    "gaming":       "20",
    "people":       "22",
    "comedy":       "23",
    "entertainment":"24",
    "news":         "25",
    "howto":        "26",
    "education":    "27",
    "scitech":      "28",
}


class YouTubeUploader:
    """
    Sube videos a YouTube con todos los metadatos.
    Soporta subida inmediata y programación de publicación.
    """

    def __init__(self, credentials_path: str):
        self.credentials_path = credentials_path
        self.token_path = str(Path(credentials_path).parent / "token.json")

        self.youtube = None
        self._initialized = False

    def _initialize(self) -> bool:
        """Inicializa el cliente de YouTube API."""
        if not YOUTUBE_AVAILABLE:
            logger.error("Librerías de Google no disponibles")
            return False

        try:
            creds = self._load_credentials()
            if creds:
                self.youtube = build("youtube", "v3", credentials=creds)
                self._initialized = True
                logger.info("YouTube API inicializado correctamente")
                return True
        except Exception as e:
            logger.error(f"Error inicializando YouTube API: {e}")

        return False

    def _load_credentials(self):
        """Carga o refresca credenciales OAuth2."""
        creds = None

        # Intentar cargar token existente
        if Path(self.token_path).exists():
            try:
                creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
            except Exception as e:
                logger.warning(f"Error cargando token existente: {e}")

        # Refrescar si está expirado
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                self._save_token(creds)
                logger.info("Token de YouTube refrescado")
                return creds
            except Exception as e:
                logger.warning(f"Error refrescando token: {e}")
                creds = None

        # Si no hay creds válidas, iniciar flujo OAuth
        if not creds:
            if not Path(self.credentials_path).exists():
                logger.error(
                    f"Archivo de credenciales no encontrado: {self.credentials_path}\n"
                    "Por favor:\n"
                    "1. Ve a Google Cloud Console\n"
                    "2. Crea un proyecto y activa YouTube Data API v3\n"
                    "3. Descarga el archivo OAuth2 credentials.json\n"
                    f"4. Guárdalo en: {self.credentials_path}"
                )
                return None

            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES
                )
                # En servidor, usar redirect automático
                if os.getenv("YOUTUBE_REDIRECT_URI"):
                    flow.redirect_uri = os.getenv("YOUTUBE_REDIRECT_URI")
                    auth_url, _ = flow.authorization_url(prompt="consent")
                    logger.info(f"Visita esta URL para autorizar: {auth_url}")
                    code = input("Introduce el código de autorización: ")
                    flow.fetch_token(code=code)
                    creds = flow.credentials
                else:
                    creds = flow.run_local_server(port=0)

                self._save_token(creds)
                logger.info("Credenciales de YouTube guardadas")

            except Exception as e:
                logger.error(f"Error en flujo OAuth: {e}")
                return None

        return creds

    def _save_token(self, creds):
        """Guarda el token para futuros usos."""
        try:
            Path(self.token_path).parent.mkdir(parents=True, exist_ok=True)
            with open(self.token_path, "w") as f:
                f.write(creds.to_json())
        except Exception as e:
            logger.warning(f"Error guardando token: {e}")

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
        """
        Sube un video a YouTube con todos los metadatos.

        Args:
            video_path: Ruta al archivo de video
            title: Título del video
            description: Descripción
            tags: Lista de etiquetas
            category_id: ID de categoría de YouTube
            is_short: True si es YouTube Short
            publish_at: Fecha/hora de publicación (None = inmediato)
            thumbnail_path: Ruta a la miniatura personalizada
            privacy: "public", "private", o "unlisted"

        Returns:
            URL del video subido
        """
        if not self._initialized:
            if not self._initialize():
                logger.warning("YouTube no disponible. Simulando subida.")
                return self._simulate_upload(title)

        if not Path(video_path).exists():
            raise FileNotFoundError(f"Video no encontrado: {video_path}")

        # Preparar título para Shorts
        if is_short and "#shorts" not in title.lower():
            title = f"{title} #shorts"

        # Preparar descripción
        if not description:
            description = f"{title}\n\n#ElTioJota #Shorts #Viral"

        if is_short:
            description = f"{description}\n\n#shorts #viral #ElTioJota"

        # Tags por defecto
        if not tags:
            tags = ["ElTioJota", "viral", "shorts", "curiosidades"]

        # Determinar privacidad y tiempo de publicación
        if publish_at:
            status = "private"  # Primero privado, luego se programa
            publish_at_str = publish_at.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        else:
            status = privacy
            publish_at_str = None

        # Metadatos del video
        body = {
            "snippet": {
                "title": title[:100],  # YouTube límite: 100 chars
                "description": description[:5000],
                "tags": tags[:500],  # YouTube límite: 500 tags
                "categoryId": category_id,
                "defaultLanguage": "es",
                "defaultAudioLanguage": "es",
            },
            "status": {
                "privacyStatus": status,
                "selfDeclaredMadeForKids": False,
            },
        }

        if publish_at_str:
            body["status"]["publishAt"] = publish_at_str

        # Crear request de subida con resumable upload
        file_size = Path(video_path).stat().st_size
        logger.info(f"Iniciando subida: {title}")
        logger.info(f"Archivo: {video_path} ({file_size/(1024*1024):.1f} MB)")

        media = MediaFileUpload(
            video_path,
            mimetype="video/mp4",
            resumable=True,
            chunksize=10 * 1024 * 1024,  # Chunks de 10MB
        )

        request = self.youtube.videos().insert(
            part=",".join(body.keys()),
            body=body,
            media_body=media,
        )

        # Subida con reintentos
        video_id = self._execute_upload(request)

        if not video_id:
            raise RuntimeError("La subida a YouTube falló")

        video_url = f"https://youtu.be/{video_id}"
        logger.info(f"✅ Video subido: {video_url}")

        # Subir thumbnail personalizada
        if thumbnail_path and Path(thumbnail_path).exists():
            self._upload_thumbnail(video_id, thumbnail_path)

        # Si era programado, actualizar estado
        if publish_at and status == "private":
            logger.info(f"Video programado para: {publish_at}")

        return video_url

    def _execute_upload(self, request, max_retries: int = 5) -> Optional[str]:
        """Ejecuta la subida con reintentos progresivos."""
        response = None
        retry = 0
        retry_exceptions = (Exception,)

        while response is None:
            try:
                logger.info(f"Subiendo... (intento {retry + 1})")
                status, response = request.next_chunk()

                if status:
                    progress = int(status.progress() * 100)
                    logger.info(f"Progreso: {progress}%")

            except Exception as e:
                retry += 1
                if retry > max_retries:
                    logger.error(f"Subida fallida después de {max_retries} reintentos: {e}")
                    return None

                sleep_time = min(2 ** retry, 60)
                logger.warning(f"Error en subida, reintentando en {sleep_time}s: {e}")
                time.sleep(sleep_time)

        if response:
            video_id = response.get("id")
            logger.info(f"Subida completada. ID: {video_id}")
            return video_id

        return None

    def _upload_thumbnail(self, video_id: str, thumbnail_path: str):
        """Sube una thumbnail personalizada al video."""
        try:
            media = MediaFileUpload(thumbnail_path, mimetype="image/jpeg")
            self.youtube.thumbnails().set(
                videoId=video_id,
                media_body=media,
            ).execute()
            logger.info(f"Thumbnail subida para video {video_id}")
        except Exception as e:
            logger.warning(f"Error subiendo thumbnail: {e}")

    def _simulate_upload(self, title: str) -> str:
        """Simula una subida cuando YouTube no está disponible."""
        fake_id = f"SIMULATED_{int(time.time())}"
        url = f"https://youtu.be/{fake_id}"
        logger.info(f"[SIMULADO] Video '{title}' subido: {url}")
        return url

    def get_channel_info(self) -> dict:
        """Obtiene información del canal autenticado."""
        if not self._initialized:
            self._initialize()

        if not self.youtube:
            return {}

        try:
            response = self.youtube.channels().list(
                part="snippet,statistics",
                mine=True
            ).execute()

            channels = response.get("items", [])
            if channels:
                ch = channels[0]
                return {
                    "id": ch["id"],
                    "name": ch["snippet"]["title"],
                    "subscribers": ch["statistics"].get("subscriberCount", 0),
                    "videos": ch["statistics"].get("videoCount", 0),
                    "views": ch["statistics"].get("viewCount", 0),
                }
        except Exception as e:
            logger.error(f"Error obteniendo info del canal: {e}")

        return {}

    def delete_video(self, video_id: str) -> bool:
        """Elimina un video (útil para limpiar pruebas)."""
        if not self._initialized:
            self._initialize()

        try:
            self.youtube.videos().delete(id=video_id).execute()
            logger.info(f"Video eliminado: {video_id}")
            return True
        except Exception as e:
            logger.error(f"Error eliminando video: {e}")
            return False
