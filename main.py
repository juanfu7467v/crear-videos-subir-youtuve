"""
main.py
──────────────
Sistema Automático de Creación de Videos.
Adaptado para recibir datos JSON de un sistema externo y procesarlos automáticamente.
"""

import os
import sys
import json
import logging
import time
import traceback
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Añadir src al path
sys.path.insert(0, str(Path(__file__).parent))

from src.script_generator import ScriptGenerator
from src.tts_engine import TTSEngine
from src.media_fetcher import MediaFetcher
from src.video_editor import VideoEditor
from src.quality_checker import QualityChecker
from src.youtube_uploader import YouTubeUploader
from src.scheduler import VideoScheduler

# ─── Configuración de Logging ─────────────────────────────────
def setup_logging():
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"pipeline_{datetime.now().strftime('%Y%m%d')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger("AutoVideo")


logger = setup_logging()


# ─── Pipeline Principal ────────────────────────────────────────
class VideoAutoPipeline:
    """
    Pipeline completo: Datos externos → Guion → Audio → Video → Calidad → YouTube
    """

    def __init__(self):
        self.gemini_api_key   = os.getenv("GEMINI_API_KEY", "")
        self.pexels_api_key   = os.getenv("PEXELS_API_KEY", "")
        self.pixabay_api_key  = os.getenv("PIXABAY_API_KEY", "")
        self.youtube_creds    = os.getenv("YOUTUBE_CREDENTIALS_FILE", "credentials/youtube_credentials.json")
        self.channel_name     = os.getenv("CHANNEL_NAME", "Mi Canal")
        self.output_dir       = Path("output")
        self.temp_dir         = Path("temp")

        # Crear directorios necesarios
        for d in [self.output_dir, self.temp_dir, Path("temp/audio"),
                  Path("temp/video"), Path("temp/images"), Path("logs")]:
            d.mkdir(parents=True, exist_ok=True)

        # Inicializar módulos
        self.script_gen      = ScriptGenerator(self.gemini_api_key)
        self.tts_engine      = TTSEngine()
        self.media_fetcher   = MediaFetcher(self.pexels_api_key, self.pixabay_api_key)
        self.video_editor    = VideoEditor()
        self.quality_checker = QualityChecker(self.gemini_api_key)
        self.yt_uploader     = YouTubeUploader(self.youtube_creds)
        self.scheduler       = VideoScheduler()

    # ─── Pipeline Completo ────────────────────────────────────
    def run_full_pipeline_with_data(self, trend_data: dict) -> dict:
        """
        Ejecuta el pipeline completo basado en datos JSON externos.
        """
        video_id = datetime.now().strftime("TJ_%Y%m%d_%H%M%S")
        logger.info(f"\n{'═'*60}")
        logger.info(f"  INICIANDO CREACIÓN DE VIDEO | ID: {video_id}")
        logger.info(f"  Tema: {trend_data.get('topic', 'N/A')}")
        logger.info(f"{'═'*60}\n")

        result = {
            "video_id": video_id,
            "status": "pending",
            "steps_completed": [],
            "errors": [],
        }

        try:
            # Paso 1: Guion
            logger.info("═══ PASO 1: Generando guion con IA ═══")
            script_data = self.script_gen.generate_full_script(trend_data)
            result["script_data"] = script_data
            result["steps_completed"].append("script_generation")

            # Paso 2: Audio
            logger.info("═══ PASO 2: Generando audio TTS ═══")
            audio_path = self.temp_dir / "audio" / f"{video_id}.mp3"
            self.tts_engine.generate_audio(
                text=script_data["full_script"],
                output_path=str(audio_path),
                voice=script_data.get("voice", "es-MX-DaliaNeural"),
                rate=script_data.get("speech_rate", "+10%"),
            )
            result["audio_path"] = str(audio_path)
            result["steps_completed"].append("tts_audio")

            # Paso 3: Media
            logger.info("═══ PASO 3: Descargando clips e imágenes ═══")
            keywords  = script_data.get("keywords", [trend_data.get("topic", "nature")])
            vid_format = trend_data.get("format", "short").lower()
            duration  = 60 if "short" in vid_format else 600

            media_list = self.media_fetcher.fetch_media_for_video(
                keywords=keywords,
                target_duration=duration,
                save_dir=str(self.temp_dir / "video"),
                video_id=video_id,
            )
            result["media_count"] = len(media_list)
            result["steps_completed"].append("media_fetch")

            # Paso 4: Edición
            logger.info("═══ PASO 4: Editando video ═══")
            output_path = self.output_dir / f"{video_id}.mp4"
            self.video_editor.create_video(
                audio_path=str(audio_path),
                media_list=media_list,
                script_data=script_data,
                format_type=trend_data.get("format", "short"),
                output_path=str(output_path),
                channel_name=self.channel_name,
                music_dir="assets/music",
            )
            result["video_path"] = str(output_path)
            result["steps_completed"].append("video_editing")

            # Paso 5: QC
            logger.info("═══ PASO 5: Verificación de calidad ═══")
            qc_result = self.quality_checker.check_video(
                video_path=str(output_path),
                expected_keywords=script_data.get("keywords", []),
            )
            result["qc_result"] = qc_result
            result["steps_completed"].append("quality_check")

            # Paso 6: Upload
            logger.info("═══ PASO 6: Publicando en YouTube ═══")
            publish_time = self.scheduler.calculate_publish_time(
                preferred_time=trend_data.get("publish_time", "18:00")
            )

            video_url = self.yt_uploader.upload(
                video_path=str(output_path),
                title=trend_data.get("title", script_data.get("title", "Video Automático")),
                description=script_data.get("description", ""),
                tags=script_data.get("tags", []),
                category_id="22",
                is_short="short" in trend_data.get("format", "").lower(),
                publish_at=publish_time,
                thumbnail_path=qc_result.get("thumbnail_path"),
            )
            result["youtube_url"] = video_url
            result["steps_completed"].append("youtube_upload")

            result["status"] = "success"
            logger.info(f"\n✅ PROCESO COMPLETADO EXITOSAMENTE")
            logger.info(f"   URL: {video_url}")

        except Exception as e:
            result["status"] = "error"
            result["errors"].append(str(e))
            logger.error(f"❌ Error en pipeline: {e}")
            logger.error(traceback.format_exc())

        # Guardar resultado en JSON
        result_path = Path("logs") / f"{video_id}_result.json"
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)

        return result


# ─── Entrypoint ───────────────────────────────────────────────
if __name__ == "__main__":
    # Modo servidor por defecto: espera peticiones JSON externas
    from src.web_server import run_server
    run_server()
