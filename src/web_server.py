"""
web_server.py
──────────────
Servidor HTTP ligero para recibir datos de tendencias externos.
Proporciona health checks y un endpoint para recibir el JSON que dispara la creación de videos.
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
    """Handler HTTP para recibir datos y disparar el pipeline."""

    pipeline_ref = None  # Referencia al pipeline principal

    def log_message(self, format, *args):
        """Silenciar logs de HTTP por defecto."""
        logger.debug(f"HTTP: {format % args}")

    def do_GET(self):
        """Maneja requests GET para health checks."""
        if self.path == "/":
            self._respond(200, {"status": "running", "service": "AutoVideo Receiver"})

        elif self.path == "/health":
            self._respond(200, {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
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

        else:
            self._respond(404, {"error": "Not found"})

    def do_POST(self):
        """Maneja requests POST para recibir el JSON de tendencias."""
        if self.path == "/trigger-video":
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                received_data = json.loads(post_data.decode('utf-8'))

                # Mapear campos si es necesario (para compatibilidad con el pipeline interno)
                # El sistema externo envía: tema_recomendado, titulo, idea_contenido, formato_sugerido, hora_optima_publicacion
                # El pipeline interno usa: topic, title, idea, format, publish_time
                trend_data = {
                    "topic": received_data.get("tema_recomendado"),
                    "title": received_data.get("titulo"),
                    "idea": received_data.get("idea_contenido"),
                    "format": received_data.get("formato_sugerido", "Short"),
                    "publish_time": received_data.get("hora_optima_publicacion", "18:00"),
                    "target_audience": received_data.get("audiencia", "público general")
                }

                if self.pipeline_ref:
                    logger.info(f"Recibida petición para crear video: {trend_data['topic']}")
                    # Ejecutar pipeline en thread separado para no bloquear la respuesta HTTP
                    thread = threading.Thread(
                        target=self.pipeline_ref.run_full_pipeline_with_data,
                        args=(trend_data,),
                        daemon=True
                    )
                    thread.start()
                    
                    self._respond(202, {
                        "message": "Proceso de creación de video iniciado",
                        "video_topic": trend_data["topic"],
                        "timestamp": datetime.now().isoformat()
                    })
                else:
                    self._respond(503, {"error": "Pipeline no inicializado"})
            except json.JSONDecodeError:
                self._respond(400, {"error": "JSON inválido"})
            except Exception as e:
                logger.error(f"Error procesando petición: {e}")
                self._respond(500, {"error": str(e)})
        else:
            self._respond(404, {"error": "Endpoint no encontrado"})

    def _respond(self, status_code: int, data: dict):
        """Envía respuesta JSON."""
        body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)


def run_server(port: int = None):
    """Inicia el servidor HTTP."""
    from main import VideoAutoPipeline
    
    port = port or int(os.getenv("PORT", "8080"))
    
    # Inicializar el pipeline una sola vez
    pipeline = VideoAutoPipeline()
    PipelineHandler.pipeline_ref = pipeline
    
    server = HTTPServer(("0.0.0.0", port), PipelineHandler)
    logger.info(f"Servidor receptor iniciado en puerto {port}")
    logger.info(f"Esperando JSON en POST /trigger-video")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Servidor detenido")
        server.shutdown()
