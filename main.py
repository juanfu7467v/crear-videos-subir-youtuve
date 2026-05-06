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
from src.thumbnail_generator import ThumbnailGenerator
from src.youtube_uploader import YouTubeUploader
from src.scheduler import VideoScheduler

def setup_logging():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    return logging.getLogger("AutoVideo")

logger = setup_logging()

class VideoAutoPipeline:
    def __init__(self):
        self.script_gen      = ScriptGenerator()
        self.tts_engine      = TTSEngine()
        self.media_fetcher   = MediaFetcher(
            os.getenv("PEXELS_API_KEY", ""), 
            os.getenv("PIXABAY_API_KEY", ""),
            os.getenv("YOUTUBE_API_KEY", "")
        )
        self.video_editor    = VideoEditor()
        self.thumbnail_gen   = ThumbnailGenerator(os.getenv("OPENAI_API_KEY"))
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

            # MEJORA: Reemplazo correcto del nombre del canal desde secrets
            if canal == "CHANNEL_NAME_2":
                canal = os.getenv("CHANNEL_NAME_2_REAL_NAME", "PeliPREX-Shorts")
            elif canal == "CHANNEL_NAME":
                canal = os.getenv("CHANNEL_NAME_REAL_NAME", "PeliPREX")

            # 1. Generar Guion
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
            
            if not script_data or not script_data.get('full_script') or not script_data.get('segmented_script'):
                logger.error("❌ ERROR: El guion no se generó correctamente.")
                self._stop_keep_alive()
                return

            video_title = script_data.get('title') or title_suggested or topic
            video_description = script_data.get('description', '')

            # Peliprex Link
            peliprex_movie_name = None
            if "películas" in categoria.lower() and script_data.get('peliprex_search_term'):
                peliprex_movie_name = script_data.get('peliprex_search_term')
                peliprex_link = self.media_fetcher.peliprex_downloader.generate_peliprex_link(peliprex_movie_name)
                video_description = video_description.replace('{{PELIPREX_LINK}}', peliprex_link)

            # 2. Generar Audio (TTS)
            logger.info("2/6 Generando audio...")
            output_dir.mkdir(parents=True, exist_ok=True)
            audio_path = str(output_dir / "voice.mp3")
            self.tts_engine.generate_audio(
                text=script_data.get('full_script', ''),
                output_path=audio_path,
                voice=script_data.get('voice', 'es-MX-DaliaNeural')
            )
            
            # 3. Descargar Media
            logger.info("3/6 Buscando material visual...")
            duration = self.tts_engine.get_audio_duration(audio_path)
            is_short = "short" in format_suggested.lower()
            target_fetch_duration = int(duration) + 5

            media_list = self.media_fetcher.fetch_media_for_video(
                segmented_script=script_data.get("segmented_script", []),
                target_duration=target_fetch_duration,
                save_dir="assets/temp",
                video_id=video_id,
                prefer_video=True,
                is_short=is_short,
                categoria=categoria,
                script_data=script_data
            )
            
            if not media_list:
                logger.error("❌ ERROR: No se pudo obtener material visual.")
                self._cleanup_assets(output_dir, temp_assets_dir)
                self._stop_keep_alive()
                return

            # 4. Preparación de Miniatura
            # MEJORA: Asegurar que la miniatura se guarde en una ruta persistente durante el proceso
            logger.info("4/6 Generando miniatura...")
            thumbnail_path = str(output_dir / "thumbnail.jpg")
            
            tmdb_thumb_success = False
            if "películas" in categoria.lower():
                thumbnail_search_term = peliprex_movie_name if peliprex_movie_name else topic
                if self.media_fetcher.generate_thumbnail(thumbnail_search_term, video_title, thumbnail_path, categoria=categoria, is_short=is_short):
                    logger.info(f"✅ Miniatura de TMDB generada: {thumbnail_path}")
                    tmdb_thumb_success = True

            if not tmdb_thumb_success:
                logger.info("Generando miniatura con OpenAI...")
                generated_thumb = self.thumbnail_gen.generate_thumbnail(
                    script_data=script_data,
                    output_path=thumbnail_path,
                    is_short=is_short
                )
                if generated_thumb:
                    thumbnail_path = generated_thumb
                    logger.info(f"✅ Miniatura con OpenAI generada: {thumbnail_path}")
                else:
                    thumbnail_path = None
                    logger.warning("⚠️ No se pudo generar la miniatura.")

            # 5. Editar Video
            logger.info("5/6 Editando video final...")
            video_path = str(output_dir / "final_video.mp4")
            self.video_editor.create_video(
                audio_path=audio_path,
                media_list=media_list,
                script_data=script_data,
                format_type=format_suggested,
                output_path=video_path,
                thumbnail_path=thumbnail_path
            )
            
            # 6. Subir a YouTube
            logger.info("6/6 Programando subida a YouTube...")
            publish_time = self.scheduler.calculate_publish_time(preferred_time=optimal_time)
            yt_category = "1" if "películas" in categoria.lower() else "22"
            is_kids = "niños" in categoria.lower() or "infantil" in categoria.lower()
            final_description = "" if is_short else video_description

            # Verificación final de miniatura antes de subir
            if thumbnail_path and not os.path.exists(thumbnail_path):
                logger.warning(f"⚠️ Miniatura perdida antes de subir: {thumbnail_path}. Intentando recuperar...")
                # Re-generación de emergencia si se perdió
                if not tmdb_thumb_success:
                    thumbnail_path = self.thumbnail_gen.generate_thumbnail(script_data, thumbnail_path, is_short)

            video_url = self.yt_uploader.upload(
                video_path=video_path,
                title=video_title,
                description=final_description,
                tags=script_data.get('tags', []),
                channel_name=canal,
                is_short=is_short,
                publish_at=publish_time,
                thumbnail_path=thumbnail_path,
                category_id=yt_category,
                is_kids=is_kids
            )
            
            if video_url and "youtu.be" in video_url:
                logger.info(f"✅ Subida confirmada con éxito! URL: {video_url}")
                # --- POLÍTICA DE RESIDUO CERO ---
                # Solo limpiamos si la subida fue exitosa y tenemos confirmación real
                logger.info("⏳ Iniciando limpieza de archivos temporales...")
                self._cleanup_assets(output_dir, temp_assets_dir)
            else:
                logger.error("❌ La subida no devolvió una URL válida. Se conservan los archivos para revisión.")
            
            self._stop_keep_alive()

        except Exception as e:
            logger.error(f"❌ Error crítico en pipeline: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # En caso de error, NO limpiamos inmediatamente para permitir debug manual si fuera necesario
            # pero el sistema de Fly.io eventualmente reiniciará la máquina
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
            
            import tempfile
            temp_dir = Path(tempfile.gettempdir())
            for moviepy_file in temp_dir.glob("tmpxxx*"):
                try: moviepy_file.unlink()
                except: pass
            logger.info("🧹 Caché de MoviePy limpiada.")
                
        except Exception as e:
            logger.warning(f"⚠️ Error durante la limpieza: {e}")

    def _keep_alive_task(self):
        app_name = os.getenv("FLY_APP_NAME")
        urls = []
        if app_name:
            urls.append(f"http://{app_name}.internal:8080/keep-alive")
            urls.append(f"https://{app_name}.fly.dev/keep-alive")
        urls.append("http://localhost:8080/keep-alive")
        
        while self.keep_alive_running:
            for url in urls:
                try:
                    requests.get(url, timeout=5)
                    break 
                except Exception:
                    continue
            time.sleep(15)

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
