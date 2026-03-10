import os
import sys
import logging
import requests
from pathlib import Path
import dotenv

dotenv.load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

from src.script_generator import ScriptGenerator
# ... (demás imports)

logger = logging.getLogger("AutoVideo")

class VideoAutoPipeline:
    def __init__(self):
        # ... (tu __init__ actual)
        pass

    def shutdown_machine(self):
        """Ordena a Fly.io apagar la máquina tras completar el trabajo."""
        logger.info("🛑 Producción finalizada. Apagando máquina para ahorrar recursos...")
        try:
            # Fly.io permite detenerse a sí mismo a través de su API interna
            requests.post("http://localhost:5500/v1/apps/crear-videos-subir-youtuve/stop", timeout=5)
        except Exception as e:
            logger.warning(f"No se pudo contactar a la API de Fly para apagado: {e}")
            os._exit(0) # Apagado forzoso si la API no responde

    def run_full_pipeline_with_data(self, trend_data: dict):
        try:
            logger.info("═══ INICIANDO CREACIÓN DE VIDEO ═══")
            # --- TU LÓGICA DE PIPELINE AQUÍ ---
            # ...
            logger.info("✅ Video creado y subido exitosamente.")
        except Exception as e:
            logger.error(f"❌ Error en pipeline: {e}")
        finally:
            self.shutdown_machine() # <--- ESTO ES LO NUEVO

if __name__ == "__main__":
    from src.web_server import run_server
    run_server()
