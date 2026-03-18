import requests
import json
import time
import sys

def test_trigger():
    url = "http://localhost:8080/trigger-video"
    payload = {
        "tema_recomendado": "Análisis de películas",
        "titulo": "El Señor de los Anillos",
        "idea_contenido": "Crea un análisis profundo, emocionante y entretenido de la película.",
        "formato_sugerido": "shorts",
        "hora_optima_publicacion": "19:30",
        "canal": "CHANNEL_NAME",
        "categoria": "películas",
        "prompt_ia": "Actúa como un experto creador de contenido para YouTube. Crea un guion atractivo, emocionante y que genere curiosidad desde el inicio. Usa lenguaje claro, incluye datos interesantes y mantén la atención del espectador hasta el final."
    }
    
    try:
        print(f"Enviando petición POST a {url}...")
        response = requests.post(url, json=payload)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_trigger()
