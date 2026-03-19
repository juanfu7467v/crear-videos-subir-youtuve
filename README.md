# 🎬 Auto Video System - Peliprex Edition

Sistema automatizado para la creación de videos (Shorts y largos) utilizando la API de **Peliprex** como fuente principal de contenido cinematográfico.

## 🚀 Mejoras Recientes

- **Eliminación de YouTube v3 & yt-dlp**: Se ha eliminado completamente la dependencia de la API de búsqueda de YouTube y la herramienta de descarga `yt-dlp` para evitar fallos de descarga y bloqueos.
- **Integración con Peliprex API**: Nueva lógica de búsqueda y descarga de clips utilizando la API interna de Peliprex.
- **Descarga Optimizada**: Implementación de descargas parciales mediante `ffmpeg` (HTTP Range Requests), permitiendo extraer fragmentos de menos de 7 segundos directamente desde el stream original.
- **Eficiencia de Recursos**: Optimizado para un uso máximo de 2 GB de RAM y ahorro significativo de ancho de banda.

## 🛠️ Configuración (Fly.io)

El sistema utiliza las siguientes variables de entorno:

| Variable | Descripción |
|----------|-------------|
| `GEMINI_API_KEY` | Para la generación de guiones y control de calidad. |
| `PEXELS_API_KEY` | Fallback para clips de stock. |
| `PIXABAY_API_KEY`| Fallback secundario para clips de stock. |
| `YOUTUBE_OAUTH2_DATA` | JSON con credenciales OAuth2 para la subida final a YouTube. |

## ⚙️ Funcionamiento

1. **Trigger**: El sistema recibe un POST en `/trigger-video`.
2. **Búsqueda**: Utiliza `https://peliprex-31wrsa.fly.dev/search?q={termino}` para encontrar la película.
3. **Descarga**: Extrae fragmentos aleatorios de la película (puntos de inicio variados, duración < 7s) usando `ffmpeg`.
4. **Edición**: Ensambla el video con audio TTS, música de fondo y subtítulos.
5. **Upload**: Sube el resultado final a YouTube.

## 📦 Despliegue

1. Clona el repositorio.
2. Configura tus secretos en Fly.io:
   ```bash
   fly secrets set GEMINI_API_KEY=tu_key PEXELS_API_KEY=tu_key PIXABAY_API_KEY=tu_key YOUTUBE_OAUTH2_DATA='{"token": "...", "refresh_token": "...", ...}'
   ```
3. Asegúrate de tener el volumen para persistencia de datos (logs y tokens):
   ```bash
   fly volumes create el_tio_jota_data --size 5
   ```
4. Despliega:
   ```bash
   fly deploy
   ```

---
*Desarrollado para la automatización eficiente de contenido cinematográfico.*
