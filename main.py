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
        self.media_fetcher   = MediaFetcher(
            os.getenv("PEXELS_API_KEY", ""), 
            os.getenv("PIXABAY_API_KEY", ""),
            os.getenv("YOUTUBE_API_KEY", "")
        )
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
            categoria = trend_data.get('categoria', 'general')
            canal = trend_data.get('canal', 'CHANNEL_NAME')

            logger.info(f"═══ INICIANDO PRODUCCIÓN DE: {topic} ({categoria}) ═══")
            logger.info(f"Formato: {format_suggested} | Canal: {canal}")
            self._start_keep_alive()

            # 1. Generar Guion extendido usando la idea de contenido
            logger.info("1/6 Generando guion y metadatos...")
            input_data = {
                "tema_recomendado": topic,
                "titulo": title_suggested,
                "idea_contenido": content_idea,
                "formato_sugerido": format_suggested,
                "canal": canal,
                "categoria": categoria,
                "prompt_ia": trend_data.get('prompt_ia')
            }
            script_data = self.script_gen.generate_full_script(input_data)
            
            # VALIDACIÓN CRÍTICA DEL GUION
            if not script_data or not script_data.get('full_script') or not script_data.get('segmented_script'):
                logger.error("❌ ERROR: El guion no se generó correctamente tras varios intentos.")
                logger.error("Deteniendo el proceso para evitar errores en cadena.")
                self._stop_keep_alive()
                return

            # Log de las mejoras implementadas
            logger.info(f"✨ Estilo de contenido: {script_data.get('estilo_contenido', 'N/A')}")
            logger.info(f"🪝 Hook generado: {script_data.get('hook', 'N/A')[:50]}...")
            
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
            
            # Decidir si es short para la descarga de media
            is_short = "short" in format_suggested.lower() or duration <= 60.0
            
            media_list = self.media_fetcher.fetch_media_for_video(
                segmented_script=script_data.get("segmented_script", []),
                target_duration=max(int(duration), 120),
                save_dir="assets/temp",
                video_id=video_id,
                prefer_video=True,
                is_short=is_short,
                categoria=categoria,
                script_data=script_data
            )
            
            # VALIDACIÓN CRÍTICA DE MEDIA
            if not media_list:
                logger.error("❌ ERROR: No se pudo obtener ningún material visual para el video.")
                logger.error("Deteniendo el proceso para evitar errores de edición.")
                self._cleanup_assets(output_dir, temp_assets_dir)
                self._stop_keep_alive()
                return

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
            logger.info("5/6 Realizando control de calidad y miniatura...")
            qc_results = self.quality_checker.check_video(video_path, script_data=script_data)
            thumbnail_path = qc_results.get('thumbnail_path')
            
            # MEJORA: Si es películas, intentar miniatura de TMDB primero
            if "películas" in categoria.lower():
                tmdb_thumb = str(output_dir / "tmdb_thumb.jpg")
                if self.media_fetcher.generate_thumbnail(topic, video_title, tmdb_thumb, categoria=categoria):
                    thumbnail_path = tmdb_thumb

            # 6. Subir a YouTube
            logger.info("6/6 Programando subida a YouTube...")
            publish_time = self.scheduler.calculate_publish_time(preferred_time=optimal_time)
            
            # Configuración SEO y Categoría YouTube
            yt_category = "1" if "películas" in categoria.lower() else "22"
            is_kids = "niños" in categoria.lower() or "infantil" in categoria.lower()

            video_url = self.yt_uploader.upload(
                video_path=video_path,
                title=video_title,
                description=script_data.get('description', ''),
                tags=script_data.get('tags', []),
                channel_name=canal,
                is_short=is_short,
                publish_at=publish_time,
                thumbnail_path=thumbnail_path,
                category_id=yt_category,
                is_kids=is_kids
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
            if output_dir.exists():
                shutil.rmtree(output_dir)
                logger.info(f"🗑️ Eliminado directorio de salida: {output_dir}")
            
            if temp_assets_dir.exists():
                shutil.rmtree(temp_assets_dir)
                logger.info(f"🗑️ Eliminado directorio de media temporal: {temp_assets_dir}")
                
        except Exception as e:
            logger.warning(f"⚠️ Error durante la limpieza de residuos: {e}")

    def _keep_alive_task(self):
        app_name = os.getenv("FLY_APP_NAME")
        base_url = f"https://{app_name}.fly.dev" if app_name else "http://localhost:8080"
        
        logger.info(f"📡 Keep-alive usará la URL: {base_url}/keep-alive")
        
        while self.keep_alive_running:
            try:
                requests.get(f"{base_url}/keep-alive", timeout=10)
                logger.debug("❤️ Keep-alive signal sent to public endpoint.")
            except requests.exceptions.RequestException as e:
                logger.warning(f"⚠️ Error sending keep-alive signal: {e}")
            
            time.sleep(30)

    def _start_keep_alive(self):
        self.keep_alive_running = True
        self.keep_alive_thread = threading.Thread(target=self._keep_alive_task, daemon=True)
        self.keep_alive_thread.start()
        logger.info("✅ Keep-alive mechanism started.")

    def _stop_keep_alive(self):
        self.keep_alive_running = False
        if self.keep_alive_thread and self.keep_alive_thread.is_alive():
            self.keep_alive_thread.join(timeout=5)
        logger.info("✅ Keep-alive mechanism stopped.")


if __name__ == "__main__":
    from src.web_server import run_server
    run_server()
