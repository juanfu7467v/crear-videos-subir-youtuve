import os
import logging
import threading
import time

logger = logging.getLogger(__name__)

class GeminiAPIManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.api_keys = self._load_api_keys()
        self.current_key_index = 0
        self._initialized = True
        logger.info(f"GeminiAPIManager inicializado con {len(self.api_keys)} claves API.")

    def _load_api_keys(self):
        keys = []
        # Cargar la clave principal
        main_key = os.getenv("GEMINI_API_KEY")
        if main_key: 
            keys.append(main_key)
            logger.debug("GEMINI_API_KEY cargada.")
        
        # Cargar claves adicionales (GEMINI_API_KEY_B, GEMINI_API_KEY_C, etc.)
        for i in range(ord('B'), ord('Z') + 1):
            key_name = f"GEMINI_API_KEY_{chr(i)}"
            key_value = os.getenv(key_name)
            if key_value:
                keys.append(key_value)
                logger.debug(f"{key_name} cargada.")
            else:
                # Si no se encuentra una clave en secuencia, asumimos que no hay más
                break
        
        if not keys:
            logger.warning("No se encontraron claves API de Gemini. Las operaciones de Gemini fallarán.")
        return keys

    def get_current_key(self) -> str:
        if not self.api_keys:
            raise ValueError("No hay claves API de Gemini configuradas.")
        return self.api_keys[self.current_key_index]

    def rotate_key(self) -> str:
        with self._lock:
            if not self.api_keys:
                raise ValueError("No hay claves API de Gemini configuradas para rotar.")
            
            self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
            new_key = self.api_keys[self.current_key_index]
            logger.warning(f"Rotando a la siguiente clave API de Gemini. Nueva clave en índice: {self.current_key_index}")
            return new_key

    def get_api_url(self, model: str = "gemini-1.5-flash") -> str:
        current_key = self.get_current_key()
        return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={current_key}"

# Instancia global para ser usada en toda la aplicación
gemini_api_manager = GeminiAPIManager()
