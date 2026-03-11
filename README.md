# Sistema Automático de Videos (Receptor)

Este sistema crea y sube videos a YouTube automáticamente al recibir una señal JSON de un sistema externo de análisis de tendencias.

## 🚀 Funcionamiento
El sistema actúa como un servidor pasivo que espera una petición POST con los datos del video a crear. Una vez recibida la información, inicia automáticamente el proceso de generación de guion, audio, descarga de clips, edición y subida a YouTube.

### Endpoint Receptor
* **URL:** `https://tu-app-en-fly.fly.dev/trigger-video`
* **Método:** `POST`
* **Formato JSON esperado:**
```json
{
  "tema_recomendado": "Misterios del océano profundo descubiertos recientemente",
  "titulo": "Los secretos del océano que los científicos acaban de descubrir",
  "idea_contenido": "Un video que muestra descubrimientos recientes en el océano profundo, criaturas extrañas, lugares nunca explorados y datos sorprendentes que están cambiando lo que sabemos sobre el planeta.",
  "formato_sugerido": "Short",
  "hora_optima_publicacion": "19:30"
}
```

## 🛠️ Configuración (Fly.io)

### Variables de Entorno (Secrets)
Configura solo las siguientes variables en Fly.io:

| Variable | Descripción |
|----------|-------------|
| `GEMINI_API_KEY` | API Key de Google Gemini (para guiones y QC) |
| `PEXELS_API_KEY` | API Key de Pexels (para clips de video) |
| `PIXABAY_API_KEY` | API Key de Pixabay (para clips de video) |
| `CHANNEL_NAME` | Nombre de tu canal de YouTube |


### Simplificación del Sistema
Se han eliminado las siguientes variables y archivos para simplificar el sistema:
* **Eliminado:** `API_SECRET_KEY`, `RUN_MODE`, `SCHEDULE_TIMES`, `YOUTUBE_CREDENTIALS_FILE`.
* **Eliminado:** Módulo de análisis de tendencias interno (ahora es pasivo).
* **Eliminado:** Módulo de programación interna (ahora depende del trigger externo).

## 📦 Despliegue

1. Clona el repositorio.
2. Configura tus secretos en Fly.io:
   ```bash
   fly secrets set GEMINI_API_KEY=tu_key PEXELS_API_KEY=tu_key PIXABAY_API_KEY=tu_key CHANNEL_NAME="Tu Canal"
   ```
3. Asegúrate de tener el volumen para persistencia de datos (logs y tokens):
   ```bash
   fly volumes create el_tio_jota_data --size 5
   ```
4. Despliega:
   ```bash
   fly deploy
   ```

## 📝 Notas
* El sistema utiliza **Edge-TTS** para la generación de voz gratuita y de alta calidad.
* La edición se realiza mediante **MoviePy**.
* Las imágenes de apoyo se generan automáticamente vía **Pollinations.ai** si no se encuentran clips de video adecuados.
