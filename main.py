"""
╔══════════════════════════════════════════════════════════════╗
║          EL TÍO JOTA - Sistema Automático de Videos          ║
║     Generación, Edición y Publicación Autónoma en YouTube    ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import sys
import json
import logging
import schedule
import time
import traceback
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.trend_analyzer import TrendAnalyzer
from src.script_generator import ScriptGenerator
from src.tts_engine import TTSEngine
from src.media_fetcher import MediaFetcher
from src.video_editor import VideoEditor
from src.quality_checker import QualityChecker
from src.youtube_uploader import YouTubeUploader
from src.scheduler import VideoScheduler

# ─── Logging Setup ───────────────────────────────────────────
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
    return logging.getLogger("ElTioJota")


logger = setup_logging()


# ─── Pipeline Principal ────────────────────────────────────────
class VideoAutoPipeline:
    """
    Pipeline completo: Tendencia → Guion → Audio → Video → Calidad → YouTube
    """

    def __init__(self):
        self.gemini_api_key   = os.getenv("GEMINI_API_KEY", "")
        self.pexels_api_key   = os.getenv("PEXELS_API_KEY", "")
        self.pixabay_api_key  = os.getenv("PIXABAY_API_KEY", "")
        self.youtube_creds    = os.getenv("YOUTUBE_CREDENTIALS_FILE", "credentials/youtube_credentials.json")
        self.channel_name     = os.getenv("CHANNEL_NAME", "El Tío Jota")
        self.output_dir       = Path("output")
        self.temp_dir         = Path("temp")

        # Crear directorios necesarios
        for d in [self.output_dir, self.temp_dir, Path("temp/audio"),
                  Path("temp/video"), Path("temp/images"), Path("logs")]:
            d.mkdir(parents=True, exist_ok=True)

        # Inicializar módulos
        self.trend_analyzer  = TrendAnalyzer(self.gemini_api_key)
        self.script_gen      = ScriptGenerator(self.gemini_api_key)
        self.tts_engine      = TTSEngine()
        self.media_fetcher   = MediaFetcher(self.pexels_api_key, self.pixabay_api_key)
        self.video_editor    = VideoEditor()
        self.quality_checker = QualityChecker(self.gemini_api_key)
        self.yt_uploader     = YouTubeUploader(self.youtube_creds)
        self.scheduler       = VideoScheduler()

    # ─── Paso 1: Obtener datos de tendencia ───────────────────
    def step_1_get_trend(self, external_trend_data: dict = None) -> dict:
        if external_trend_data:
            logger.info("═══ PASO 1: Usando datos de tendencia externos ═══")
            trend_data = external_trend_data
        else:
            logger.info("═══ PASO 1: Analizando tendencias actuales ═══")
            trend_data = self.trend_analyzer.get_trending_content()
        logger.info(f"Tema encontrado: {trend_data.get('tema_recomendado', 'N/A')}")
        logger.info(f"Formato:         {trend_data.get('formato_sugerido', 'N/A')}")
        logger.info(f"Publicar a las:  {trend_data.get('hora_optima_publicacion', 'N/A')}")
        return trend_data

    # ─── Paso 2: Generar guion ────────────────────────────────
    def step_2_generate_script(self, trend_data: dict) -> dict:
        logger.info("═══ PASO 2: Generando guion con IA ═══")
        script_data = self.script_gen.generate_full_script(trend_data)
        logger.info(f"Guion generado: {len(script_data.get('full_script', ''))} caracteres")
        logger.info(f"Hook (3s):      {script_data.get('hook', '')[:80]}...")
        logger.info(f"Keywords:       {', '.join(script_data.get('keywords', []))}")
        return script_data

    # ─── Paso 3: Generar audio TTS ────────────────────────────
    def step_3_generate_audio(self, script_data: dict, video_id: str) -> Path:
        logger.info("═══ PASO 3: Generando audio con Edge-TTS ═══")
        audio_path = self.temp_dir / "audio" / f"{video_id}.mp3"
        self.tts_engine.generate_audio(
            text=script_data["full_script"],
            output_path=str(audio_path),
            voice=script_data.get("voice", "es-MX-DaliaNeural"),
            rate=script_data.get("speech_rate", "+10%"),
        )
        logger.info(f"Audio guardado: {audio_path}")
        return audio_path

    # ─── Paso 4: Obtener media (clips/imágenes) ───────────────
    def step_4_fetch_media(self, script_data: dict, trend_data: dict, video_id: str) -> list:
        logger.info("═══ PASO 4: Descargando clips e imágenes ═══")
        keywords  = script_data.get("keywords", [trend_data.get("topic", "nature")])
        vid_format = trend_data.get("format", "short").lower()
        duration  = 60 if "short" in vid_format else 600

        media_list = self.media_fetcher.fetch_media_for_video(
            keywords=keywords,
            target_duration=duration,
            save_dir=str(self.temp_dir / "video"),
            video_id=video_id,
        )
        logger.info(f"Media descargada: {len(media_list)} elementos")
        return media_list

    # ─── Paso 5: Editar video ─────────────────────────────────
    def step_5_edit_video(self, audio_path: Path, media_list: list,
                          script_data: dict, trend_data: dict, video_id: str) -> Path:
        logger.info("═══ PASO 5: Editando video con MoviePy ═══")
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
        logger.info(f"Video creado: {output_path}")
        return output_path

    # ─── Paso 6: Control de calidad ───────────────────────────
    def step_6_quality_check(self, video_path: Path, script_data: dict) -> dict:
        logger.info("═══ PASO 6: Verificación de calidad con IA ═══")
        qc_result = self.quality_checker.check_video(
            video_path=str(video_path),
            expected_keywords=script_data.get("keywords", []),
        )
        logger.info(f"Puntuación QC:  {qc_result.get('score', 0)}/100")
        logger.info(f"Legibilidad:    {qc_result.get('legibility', 'N/A')}")
        logger.info(f"Visual:         {qc_result.get('visual_appeal', 'N/A')}")
        return qc_result

    # ─── Paso 7: Publicar en YouTube ──────────────────────────
    def step_7_upload(self, video_path: Path, trend_data: dict,
                      script_data: dict, qc_result: dict) -> str:
        logger.info("═══ PASO 7: Publicando en YouTube ═══")

        publish_time = self.scheduler.calculate_publish_time(
            preferred_time=trend_data.get("publish_time", "18:00")
        )

        video_url = self.yt_uploader.upload(
            video_path=str(video_path),
            title=trend_data.get("title", script_data.get("title", "Video Automático")),
            description=script_data.get("description", ""),
            tags=script_data.get("tags", []),
            category_id="22",  # People & Blogs
            is_short="short" in trend_data.get("format", "").lower(),
            publish_at=publish_time,
            thumbnail_path=qc_result.get("thumbnail_path"),
        )
        logger.info(f"Video publicado: {video_url}")
        return video_url

    # ─── Pipeline Completo ────────────────────────────────────
    def run_full_pipeline_with_data(self, trend_data: dict) -> dict:
        return self.run_full_pipeline(external_trend_data=trend_data)

    def run_full_pipeline(self, external_trend_data: dict = None) -> dict:
        """
        Ejecuta el pipeline completo de principio a fin.
        Retorna un resumen del resultado.
        """
        video_id = datetime.now().strftime("TJ_%Y%m%d_%H%M%S")
        logger.info(f"\n{'═'*60}")
        logger.info(f"  INICIANDO PIPELINE | ID: {video_id}")
        logger.info(f"  Canal: {self.channel_name}")
        logger.info(f"{'═'*60}\n")

        result = {
            "video_id": video_id,
            "status": "pending",
            "steps_completed": [],
            "errors": [],
        }

        try:
            # Paso 1: Tendencias
            trend_data = self.step_1_get_trend(external_trend_data)
            result["trend_data"] = trend_data
            result["steps_completed"].append("trend_analysis")

            # Paso 2: Guion
            script_data = self.step_2_generate_script(trend_data)
            result["script_data"] = script_data
            result["steps_completed"].append("script_generation")

            # Paso 3: Audio
            audio_path = self.step_3_generate_audio(script_data, video_id)
            result["audio_path"] = str(audio_path)
            result["steps_completed"].append("tts_audio")

            # Paso 4: Media
            media_list = self.step_4_fetch_media(script_data, trend_data, video_id)
            result["media_count"] = len(media_list)
            result["steps_completed"].append("media_fetch")

            # Paso 5: Edición
            video_path = self.step_5_edit_video(
                audio_path, media_list, script_data, trend_data, video_id
            )
            result["video_path"] = str(video_path)
            result["steps_completed"].append("video_editing")

            # Paso 6: QC
            qc_result = self.step_6_quality_check(video_path, script_data)
            result["qc_result"] = qc_result
            result["steps_completed"].append("quality_check")

            if qc_result.get("score", 0) < int(os.getenv("MIN_QC_SCORE", "60")):
                logger.warning(f"QC score bajo ({qc_result['score']}). Publicando igualmente...")

            # Paso 7: Upload
            video_url = self.step_7_upload(video_path, trend_data, script_data, qc_result)
            result["youtube_url"] = video_url
            result["steps_completed"].append("youtube_upload")

            result["status"] = "success"
            logger.info(f"\n✅ PIPELINE COMPLETADO EXITOSAMENTE")
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


# ─── Modo Servidor con Schedule ──────────────────────────────
def run_scheduled():
    """Ejecuta el pipeline según horario programado."""
    pipeline = VideoAutoPipeline()
    schedule_times = os.getenv("SCHEDULE_TIMES", "08:00,18:00").split(",")

    logger.info(f"🕐 Modo programado. Horarios: {', '.join(schedule_times)}")

    for t in schedule_times:
        t = t.strip()
        schedule.every().day.at(t).do(pipeline.run_full_pipeline)
        logger.info(f"   → Programado para las {t}")

    while True:
        schedule.run_pending()
        time.sleep(30)


# ─── Entrypoint ───────────────────────────────────────────────
if __name__ == "__main__":
    mode = os.getenv("RUN_MODE", "server").lower()

    if mode == "scheduled":
        run_scheduled()
    elif mode == "once":
        pipeline = VideoAutoPipeline()
        result = pipeline.run_full_pipeline()
        sys.exit(0 if result["status"] == "success" else 1)
    elif mode == "server":
        # Modo servidor: espera requests HTTP (para health checks en Fly.io)
        from src.web_server import run_server
        run_server()
    else:
        logger.error(f"Modo desconocido: {mode}. Use: once | scheduled | server")
        sys.exit(1)
