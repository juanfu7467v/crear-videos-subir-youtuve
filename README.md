# Automatización de Videos para YouTube con Fly.io y Railway

Este proyecto automatiza la creación y subida de videos (YouTube Shorts) utilizando inteligencia artificial y servicios cloud.

## Arquitectura

1.  **Railway**: Monitorea trends o feeds y, al detectar uno nuevo, envía un webhook (POST JSON) al service en Fly.io.
2.  **Fly.io (Módulo Receptor)**: Un microservicio en Flask recibe el JSON con el title y topic.
3.  **Generación de Contenido**:
    *   **Guion**: Se utiliza la API de Google Gemini para generar un guion optimizado.
    *   **Voz**: Se utiliza `edge-tts` para generar voiceovers naturales.
    *   **Visuales**: Se descargan clips stock de PexCrear la arquitectura completa del sitema de generación y subida automática de videos a YouTube.

## Requisitos

- Python 3.11+
- FFmpeg
- ImageMagick
- API Keys: Google Gemini, Pexels, YouTube Data API.

## Configuración

1. Clona el repositorio.
2. Configura las variables de entorno en un archivo `.env`.
3. Despliega en Fly.io usando `fly deploy`.
