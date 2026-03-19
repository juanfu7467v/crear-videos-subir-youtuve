import json
import os
import requests
import logging

logger = logging.getLogger(__name__)

def get_youtube_oauth2_data():
    """Obtiene los datos de OAuth2 desde la variable de entorno."""
    oauth2_data_raw = os.getenv("YOUTUBE_OAUTH2_DATA")
    if not oauth2_data_raw:
        logger.error("No se encontró la variable de entorno YOUTUBE_OAUTH2_DATA")
        return None
    
    try:
        # La variable puede venir como un string JSON
        return json.loads(oauth2_data_raw)
    except Exception as e:
        logger.error(f"Error al decodificar YOUTUBE_OAUTH2_DATA: {e}")
        return None

def refresh_access_token(oauth2_data):
    """Refresca el access_token usando el refresh_token."""
    payload = {
        'client_id': oauth2_data['client_id'],
        'client_secret': oauth2_data['client_secret'],
        'refresh_token': oauth2_data['refresh_token'],
        'grant_type': 'refresh_token'
    }
    
    try:
        response = requests.post(oauth2_data['token_uri'], data=payload, timeout=10)
        response.raise_for_status()
        new_tokens = response.json()
        
        # Actualizar el token en el objeto original
        oauth2_data['token'] = new_tokens['access_token']
        if 'refresh_token' in new_tokens:
            oauth2_data['refresh_token'] = new_tokens['refresh_token']
            
        return oauth2_data
    except Exception as e:
        logger.error(f"Error al refrescar el token de acceso: {e}")
        return None

def get_valid_oauth2_data():
    """Obtiene datos de OAuth2 y asegura que el token sea válido."""
    data = get_youtube_oauth2_data()
    if data:
        return refresh_access_token(data)
    return None
