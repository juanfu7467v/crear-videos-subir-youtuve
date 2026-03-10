import os
import sys
import logging
import subprocess
from pathlib import Path
import dotenv

# --- CONFIGURACIÓN ---
dotenv.load_dotenv() 
sys.path.insert(0, str(Path(__file__).parent))

from src.script_generator import ScriptGenerator
from src.tts_engine import TTSEngine
from src.media_fetcher import MediaFetcher
from src.video_editor import VideoEditor
from src.quality_checker import QualityChecker
from src.youtube_uploader import YouTubeUploader
from src.scheduler import VideoScheduler

def setup_logging():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    return logging.getLogger("AutoVideo")

logger = setup_logging()

class VideoAutoPipeline:
    def __init__(self):
        self.script_gen      = ScriptGenerator(os.getenv("GEMINI_API_KEY", ""))
        self.tts_engine      = TTSEngine()
        self.media_fetcher   = MediaFetcher(os.getenv("PEXELS_API_KEY", ""), os.getenv("PIXABAY_API_KEY", ""))
        self.video_editor    = VideoEditor()
        self.quality_checker = QualityChecker(os.getenv("GEMINI_API_KEY", ""))
        self.yt_uploader     = YouTubeUploader(os.getenv("YOUTUBE_CREDENTIALS_FILE", "credentials/youtube_credentials.json"))

    def shutdown_machine(self):
        """Apaga la máquina de Fly.io al finalizar."""
        logger.info("🛑 Proceso finalizado. Apagando máquina para ahorrar...")
        try:
            # Comando estándar para auto-apagado en Fly.io
            subprocess.run(["fly", "machine", "stop", os.getenv("FLY_MACHINE_ID", "")], check=False)
        except Exception as e:
            logger.error(f"Error al apagar: {e}")

    def run_full_pipeline_with_data(self, trend_data: dict) -> dict:
        try:
            logger.info(f"═══ INICIANDO PRODUCCIÓN: {trend_data.get('topic')} ═══")
            # --- TU LÓGICA DE PRODUCCIÓN AQUÍ ---
            # ... (código que crea el video) ...
            logger.info("✅ Producción completada con éxito.")
        except Exception as e:
            logger.error(f"❌ Error en pipeline: {e}")
        finally:
            self.shutdown_machine()

if __name__ == "__main__":
    from src.web_server import run_server
    run_server()
