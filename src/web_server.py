"""
web_server.py - EL TÍO JOTA
Versión con soporte CORS para la interfaz web.
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
    pipeline_ref = None

    def log_message(self, format, *args):
        logger.debug(f"HTTP: {format % args}")

    def _send_cors_headers(self):
        """Encabezados necesarios para que la interfaz web funcione."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        """Maneja la pre-petición que hacen los navegadores."""
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        if self.path in ["/", "/health"]:
            self._respond(200, {"status": "healthy", "service": "El Tío Jota"})
        else:
            self._respond(404, {"error": "Not found"})

    def do_POST(self):
        if self.path == "/trigger-video":
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                received_data = json.loads(post_data.decode('utf-8'))

                trend_data = {
                    "topic": received_data.get("tema_recomendado"),
                    "title": received_data.get("titulo"),
                    "idea": received_data.get("idea_contenido"),
                    "format": received_data.get("formato_sugerido", "Short"),
                    "publish_time": received_data.get("hora_optima_publicacion", "19:30")
                }

                if self.pipeline_ref:
                    logger.info(f"🚀 Iniciando producción: {trend_data['topic']}")
                    thread = threading.Thread(
                        target=self.pipeline_ref.run_full_pipeline_with_data,
                        args=(trend_data,),
                        daemon=True
                    )
                    thread.start()
                    
                    self._respond(202, {
                        "status": "success",
                        "message": "Producción iniciada",
                        "topic": trend_data["topic"]
                    })
                else:
                    self._respond(503, {"error": "Pipeline no listo"})
            except Exception as e:
                logger.error(f"Error: {e}")
                self._respond(500, {"error": str(e)})
        else:
            self._respond(404, {"error": "No encontrado"})

    def _respond(self, status_code: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self._send_cors_headers() # IMPORTANTE
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

def run_server(port: int = None):
    from main import VideoAutoPipeline
    port = port or int(os.getenv("PORT", "8080"))
    
    # Aseguramos que el pipeline se inicie ANTES que el servidor
    try:
        pipeline = VideoAutoPipeline()
        PipelineHandler.pipeline_ref = pipeline
        server = HTTPServer(("0.0.0.0", port), PipelineHandler)
        logger.info(f"✅ El Tío Jota listo en puerto {port}")
        server.serve_forever()
    except Exception as e:
        logger.error(f"Error fatal: {e}")
