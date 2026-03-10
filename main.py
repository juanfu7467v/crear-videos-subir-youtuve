"""
main.py
──────────────
Sistema Automático de Creación de Videos.
"""

import os
import sys
import json
import logging
import traceback
from datetime import datetime
from pathlib import Path

# --- CORRECCIÓN CRÍTICA DE DOTENV ---
import dotenv
dotenv.load_dotenv() 

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
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    return logging.getLogger("AutoVideo")

logger = setup_logging()

# ─── Pipeline Principal ────────────────────────────────────────
class VideoAutoPipeline:
    def __init__(self):
        self.gemini_api_key   = os.getenv("GEMINI_API_KEY", "")
        self.pexels_api_key   = os.getenv("PEXELS_API_KEY", "")
        self.pixabay_api_key  = os.getenv("PIXABAY_API_KEY", "")
        self.youtube_creds    = os.getenv("YOUTUBE_CREDENTIALS_FILE", "credentials/youtube_credentials.json")
        self.channel_name     = os.getenv("CHANNEL_NAME", "El Tío Jota")
        
        self.script_gen      = ScriptGenerator(self.gemini_api_key)
        self.tts_engine      = TTSEngine()
        self.media_fetcher   = MediaFetcher(self.pexels_api_key, self.pixabay_api_key)
        self.video_editor    = VideoEditor()
        self.quality_checker = QualityChecker(self.gemini_api_key)
        self.yt_uploader     = YouTubeUploader(self.youtube_creds)
        self.scheduler       = VideoScheduler()

    def run_full_pipeline_with_data(self, trend_data: dict) -> dict:
        # (Tu lógica de pipeline se mantiene igual aquí...)
        pass

if __name__ == "__main__":
    from src.web_server import run_server
    run_server()
