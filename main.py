import os
import sys
import logging
import threading
import requests
import time
import shutil
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
        self.yt_uploader     = YouTubeUploader()
        self.scheduler       = VideoScheduler()
        self.keep_alive_thread = None
        self.keep_alive_running = False

    def run_full_pipeline_with_data(self, trend_data: dict):
        """Pipeline que procesa los datos recibidos y genera el video."""
        video_id = f"vid_{int(time.time())}"
        output_dir = Path("output") / video_id
        temp_assets_dir = Path("assets/temp") / video_id
        
        try:
            # Extraer datos del JSON recibido
            topic = trend_data.get('tema_recomendado') or trend_data.get('topic', 'Sin tema')
            title_suggested = trend_data.get('titulo')
            content_idea = trend_data.get('idea_contenido')
            format_suggested = trend_data.get('formato_sugerido', 'Short')
            optimal_time = trend_data.get('hora_optima_publicacion')

            logger.info(f"═══ INICIANDO PRODUCCIÓN DE: {topic} ═══")
            self._start_keep_alive()

            
            # 1. Generar Guion extendido usando la idea de contenido
            logger.info("1/6 Generando guion y metadatos...")
            # Enriquecemos el trend_data para el generador de guiones
            input_data = {
                "topic": topic,
                "suggested_title": title_suggested,
                "content_idea": content_idea,
                "canal": trend_data.get('canal', 'CHANNEL_NAME')
            }
            script_data = self.script_gen.generate_full_script(input_data)
            
            # Usar el título sugerido si el generador no dio uno mejor
            video_title = script_data.get('title') or title_suggested or topic
            
            # 2. Generar Audio (TTS)
            logger.info("2/6 Generando audio...")
            output_dir.mkdir(parents=True, exist_ok=True)
            
            audio_path = str(output_dir / "voice.mp3")
            self.tts_engine.generate_audio(
                text=script_data.get('full_script', ''),
                output_path=audio_path,
                voice=script_data.get('voice', 'es-MX-DaliaNeural')
            )
            
            # 3. Descargar Media (Videos/Imágenes)
            logger.info("3/6 Buscando material visual...")
            duration = self.tts_engine.get_audio_duration(audio_path)
            is_short = duration <= 60.0
            keywords = script_data.get('keywords', [topic])
            if isinstance(keywords, str): keywords = [k.strip() for k in keywords.split(',')]
            
            media_list = self.media_fetcher.fetch_media_for_video(
                keywords=keywords,
                target_duration=max(int(duration), 120),
                save_dir="assets/temp",
                video_id=video_id,
                prefer_video=True,
                is_short=is_short
            )
            
            # 4. Editar Video
            logger.info("4/6 Editando video final...")
            video_path = str(output_dir / "final_video.mp4")
            self.video_editor.create_video(
                audio_path=audio_path,
                media_list=media_list,
                script_data=script_data,
                format_type=format_suggested,
                output_path=video_path
            )
            
            # 5. Control de Calidad y Miniatura
            logger.info("5/6 Realizando control de calidad...")
            qc_results = self.quality_checker.check_video(video_path)
            thumbnail_path = qc_results.get('thumbnail_path')
            
            # 6. Subir a YouTube
            logger.info("6/6 Programando subida a YouTube...")
            publish_time = self.scheduler.calculate_publish_time(preferred_time=optimal_time)
            
            video_url = self.yt_uploader.upload(
                video_path=video_path,
                title=video_title,
                description=script_data.get('description', ''),
                tags=script_data.get('tags', []),
                channel_name=trend_data.get('canal', 'CHANNEL_NAME'),
                is_short=("short" in format_suggested.lower()),
                publish_at=publish_time,
                thumbnail_path=thumbnail_path
            )
            
            logger.info(f"✅ Proceso completado con éxito!")
            logger.info(f"🔗 URL: {video_url}")
            logger.info(f"📅 Programado para: {publish_time}")

            # --- POLÍTICA DE RESIDUO CERO ---
            logger.info("🧹 Aplicando Política de Residuo Cero...")
            self._cleanup_assets(output_dir, temp_assets_dir)
            self._stop_keep_alive()


        except Exception as e:
            logger.error(f"❌ Error crítico en pipeline: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # Intentar limpiar incluso si falla, para no dejar basura
            self._cleanup_assets(output_dir, temp_assets_dir)
            self._stop_keep_alive()


    def _cleanup_assets(self, output_dir: Path, temp_assets_dir: Path):
        """Elimina archivos temporales generados durante el proceso."""
        try:
            # 1. Eliminar directorio de salida (audio, video final, miniatura)
            if output_dir.exists():
                shutil.rmtree(output_dir)
                logger.info(f"🗑️ Eliminado directorio de salida: {output_dir}")
            
            # 2. Eliminar clips y media temporal
            if temp_assets_dir.exists():
                shutil.rmtree(temp_assets_dir)
                logger.info(f"🗑️ Eliminado directorio de media temporal: {temp_assets_dir}")
                
        except Exception as e:
            logger.warning(f"⚠️ Error durante la limpieza de residuos: {e}")

    def _keep_alive_task(self):
        while self.keep_alive_running:
            try:
                # Send a request to a dummy endpoint on the local server
                # This simulates activity and prevents Fly.io from auto-stopping
                requests.get("http://localhost:8080/keep-alive", timeout=5)
                logger.debug("❤️ Keep-alive signal sent.")
            except requests.exceptions.RequestException as e:
                logger.warning(f"⚠️ Error sending keep-alive signal: {e}")
            time.sleep(60) # Send signal every 60 seconds

    def _start_keep_alive(self):
        self.keep_alive_running = True
        self.keep_alive_thread = threading.Thread(target=self._keep_alive_task, daemon=True)
        self.keep_alive_thread.start()
        logger.info("✅ Keep-alive mechanism started.")

    def _stop_keep_alive(self):
        self.keep_alive_running = False
        if self.keep_alive_thread and self.keep_alive_thread.is_alive():
            self.keep_alive_thread.join(timeout=5) # Give it a moment to stop
        logger.info("✅ Keep-alive mechanism stopped.")


if __name__ == "__main__":
    from src.web_server import run_server
    run_server()
