import json
import os
import logging
import requests
from typing import Optional, Dict

logger = logging.getLogger(__name__)

def get_youtube_oauth2_data() -> Optional[Dict]:
    """Obtiene los datos de OAuth2 desde la variable de entorno."""
    data_json = os.getenv("YOUTUBE_OAUTH2_DATA")
    if not data_json:
        return None
    try:
        return json.loads(data_json)
    except Exception as e:
        logger.error(f"Error parseando YOUTUBE_OAUTH2_DATA: {e}")
        return None

def refresh_access_token(oauth2_data: Dict) -> Optional[str]:
    """Refresca el access token usando el refresh token."""
    try:
        payload = {
            'client_id': oauth2_data['client_id'],
            'client_secret': oauth2_data['client_secret'],
            'refresh_token': oauth2_data['refresh_token'],
            'grant_type': 'refresh_token',
        }
        resp = requests.post(oauth2_data['token_uri'], data=payload, timeout=10)
        resp.raise_for_status()
        new_data = resp.json()
        return new_data.get('access_token')
    except Exception as e:
        logger.error(f"Error refrescando access token: {e}")
        return None

def get_valid_oauth2_data() -> Optional[Dict]:
    """Obtiene datos de OAuth2 y asegura que el token sea válido (refrescándolo si es necesario)."""
    oauth2_data = get_youtube_oauth2_data()
    if not oauth2_data:
        return None
    
    # Refrescar siempre para asegurar validez en la subida
    new_token = refresh_access_token(oauth2_data)
    if new_token:
        oauth2_data['token'] = new_token
        
    return oauth2_data
