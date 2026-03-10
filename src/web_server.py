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
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = json.loads(self.rfile.read(content_length).decode('utf-8'))
                
                # Validar que el JSON tenga los campos mínimos necesarios
                if not post_data.get('tema_recomendado') and not post_data.get('topic'):
                    logger.warning("⚠️ Recibido JSON sin tema_recomendado ni topic.")
                    self._respond(400, {"error": "JSON inválido. Se requiere 'tema_recomendado' o 'topic'."})
                    return

                if self.pipeline_ref:
                    logger.info(f"🚀 Recibida información de tendencia: {post_data.get('tema_recomendado', 'Sin tema')}")
                    logger.info("Iniciando pipeline de creación de video en segundo plano...")
                    
                    thread = threading.Thread(
                        target=self.pipeline_ref.run_full_pipeline_with_data,
                        args=(post_data,),
                        daemon=True
                    )
                    thread.start()
                    self._respond(202, {
                        "status": "iniciado",
                        "mensaje": "El sistema ha recibido la información y está procesando el video automáticamente."
                    })
                else:
                    logger.error("❌ Pipeline no inicializado en el servidor.")
                    self._respond(503, {"error": "Pipeline no listo"})
            except json.JSONDecodeError:
                logger.error("❌ Error al decodificar el JSON recibido.")
                self._respond(400, {"error": "Formato JSON inválido"})
            except Exception as e:
                logger.error(f"❌ Error procesando la solicitud: {e}")
                self._respond(500, {"error": str(e)})
        else:
            self._respond(404, {"error": "Ruta no encontrada. Use /trigger-video"})

    def _respond(self, status, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

def run_server(port=8080):
    # Importación tardía para evitar ciclos
    from main import VideoAutoPipeline
    
    logger.info("Inicializando Pipeline de Video...")
    PipelineHandler.pipeline_ref = VideoAutoPipeline()
    
    server_address = ("0.0.0.0", port)
    httpd = HTTPServer(server_address, PipelineHandler)
    
    logger.info(f"✅ Servidor receptor de tendencias listo en puerto {port}")
    logger.info(f"Esperando información JSON en http://0.0.0.0:{port}/trigger-video")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Servidor detenido por el usuario.")
        httpd.server_close()
