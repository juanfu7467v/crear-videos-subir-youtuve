"""
web_server.py
──────────────
Servidor HTTP ligero para Fly.io.
Proporciona health checks y endpoints para control manual.
"""

import json
import logging
import os
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

logger = logging.getLogger(__name__)


class PipelineHandler(BaseHTTPRequestHandler):
    """Handler HTTP para endpoints del pipeline."""

    pipeline_ref = None  # Referencia al pipeline principal

    def log_message(self, format, *args):
        """Silenciar logs de HTTP por defecto."""
        logger.debug(f"HTTP: {format % args}")

    def do_GET(self):
        """Maneja requests GET."""
        if self.path == "/":
            self._respond(200, {"status": "running", "service": "El Tío Jota AutoVideo"})

        elif self.path == "/health":
            self._respond(200, {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "version": "1.0.0",
            })

        elif self.path == "/status":
            logs_dir = Path("logs")
            recent_logs = []
            if logs_dir.exists():
                for f in sorted(logs_dir.glob("TJ_*_result.json"))[-5:]:
                    try:
                        with open(f) as fp:
                            recent_logs.append(json.load(fp))
                    except Exception:
                        pass

            self._respond(200, {
                "status": "running",
                "recent_videos": len(recent_logs),
                "last_video": recent_logs[-1] if recent_logs else None,
            })

        elif self.path == "/schedule":
            schedule_times = os.getenv("SCHEDULE_TIMES", "08:00,18:00").split(",")
            self._respond(200, {
                "schedule": schedule_times,
                "timezone": os.getenv("TIMEZONE", "America/Mexico_City"),
            })

        else:
            self._respond(404, {"error": "Not found"})

    def do_POST(self):
        """Maneja requests POST."""
        if self.path == "/trigger-video": # Nuevo endpoint para recibir JSON
            # Recibir JSON y disparar pipeline


            # Ejecutar pipeline en thread separado
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                trend_data = json.loads(post_data.decode('utf-8'))

                if self.pipeline_ref:
                    thread = threading.Thread(
                        target=self.pipeline_ref.run_full_pipeline_with_data,
                        args=(trend_data,),
                        daemon=True
                    )
                    thread.start()
                    self._respond(202, {
                        "message": "Pipeline de video iniciado con datos recibidos",
                        "timestamp": datetime.now().isoformat(),
                        "received_data": trend_data
                    })
                else:
                    self._respond(503, {"error": "Pipeline no disponible"})
            except json.JSONDecodeError:
                self._respond(400, {"error": "JSON inválido"})
            except Exception as e:
                logger.error(f"Error procesando POST /trigger-video: {e}")
                self._respond(500, {"error": f"Error interno del servidor: {e}"})

        else:
            self._respond(404, {"error": "Not found"})

    def _respond(self, status_code: int, data: dict):
        """Envía respuesta JSON."""
        body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)


def run_server(port: int = None, pipeline=None):
    """
    Inicia el servidor HTTP con modo programado en background.
    """
    import schedule
    import time
    from main import VideoAutoPipeline, logger

    port = port or int(os.getenv("PORT", "8080"))

    # Crear pipeline
    p = VideoAutoPipeline()
    PipelineHandler.pipeline_ref = p

    # Programar ejecuciones automáticas (si aplica)
    if os.getenv("RUN_MODE", "server") == "scheduled":
        schedule_times = os.getenv("SCHEDULE_TIMES", "08:00,18:00").split(",")
        for t in schedule_times:
            t = t.strip()
            schedule.every().day.at(t).do(p.run_full_pipeline)
            logger.info(f"Programado: {t}")

    # Scheduler en thread separado
    def run_scheduler():
        while True:
            schedule.run_pending()
            time.sleep(30)

    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    logger.info("Scheduler iniciado en background")

    # Servidor HTTP
    server = HTTPServer(("0.0.0.0", port), PipelineHandler)
    logger.info(f"Servidor HTTP en puerto {port}")
    logger.info(f"Health check: http://0.0.0.0:{port}/health")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Servidor detenido")
        server.shutdown()
