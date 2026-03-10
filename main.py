import os
import sys
import logging
import threading
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

    def run_full_pipeline_with_data(self, trend_data: dict):
        """Pipeline que corre en background."""
        try:
            topic = trend_data.get('topic', 'Sin nombre')
            logger.info(f"═══ INICIANDO PRODUCCIÓN DE: {topic} ═══")
            
            # AQUÍ ES DONDE DEBES PONER TUS LLAMADAS A LAS CLASES
            # script = self.script_gen.generate_full_script(trend_data)
            # ... resto de pasos ...
            
            logger.info(f"✅ Producción completada: {topic}")
        except Exception as e:
            logger.error(f"❌ Error crítico en pipeline: {e}")

if __name__ == "__main__":
    from src.web_server import run_server
    run_server()
