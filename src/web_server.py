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
            
            # Lanzamos en hilo separado para no bloquear el servidor
            thread = threading.Thread(
                target=self.pipeline_ref.run_full_pipeline_with_data,
                args=(post_data,)
            )
            thread.start()
            
            self.send_response(202)
            self.end_headers()
            self.wfile.write(b'{"status": "in_progress"}')

def run_server():
    from main import VideoAutoPipeline
    PipelineHandler.pipeline_ref = VideoAutoPipeline()
    server = HTTPServer(("0.0.0.0", int(os.getenv("PORT", "8080"))), PipelineHandler)
    server.serve_forever()
