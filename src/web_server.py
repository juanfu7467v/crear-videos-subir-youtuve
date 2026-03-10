import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import os

logger = logging.getLogger(__name__)

class PipelineHandler(BaseHTTPRequestHandler):
    pipeline_ref = None

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_POST(self):
        if self.path == "/trigger-video":
            content_length = int(self.headers['Content-Length'])
            post_data = json.loads(self.rfile.read(content_length).decode('utf-8'))
            
            if self.pipeline_ref:
                logger.info("🚀 Recibida solicitud de video. Iniciando hilo...")
                thread = threading.Thread(
                    target=self.pipeline_ref.run_full_pipeline_with_data,
                    args=(post_data,),
                    daemon=True
                )
                thread.start()
                self._respond(202, {"status": "iniciado"})
            else:
                self._respond(503, {"error": "Pipeline no listo"})
        else:
            self._respond(404, {"error": "Not found"})

    def _respond(self, status, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

def run_server(port=8080):
    from main import VideoAutoPipeline
    PipelineHandler.pipeline_ref = VideoAutoPipeline()
    server = HTTPServer(("0.0.0.0", port), PipelineHandler)
    logger.info(f"✅ El Tío Jota listo en puerto {port}")
    server.serve_forever()
