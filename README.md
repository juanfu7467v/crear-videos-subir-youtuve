# 🎬 Auto Video System - Peliprex Edition

Sistema automatizado para la creación de videos (Shorts y largos) utilizando la API de **Peliprex** como fuente principal de contenido cinematográfico.

## 🚀 Mejoras Recientes

- **🤖 Actualización de Gemini AI**: Se ha implementado el endpoint estable `gemini-2.5-flash` con autenticación oficial mediante headers (`x-goog-api-key`).
- **🔄 Sistema de Respaldo (Fallback)**: Se ha eliminado Grok AI para reducir costes. Ahora, si Gemini falla por cuota o errores de red, el sistema utiliza automáticamente **GPT-4o-mini** de OpenAI para garantizar la generación de guiones de forma económica y eficiente.
- **📺 Escalabilidad de Canales**: Estructura preparada para gestionar múltiples canales de YouTube de forma dinámica y sencilla.
- **Eliminación de YouTube v3 & yt-dlp**: Se ha eliminado la dependencia de búsqueda de YouTube y `yt-dlp` para evitar bloqueos.
- **Integración con Peliprex API**: Nueva lógica de búsqueda y descarga de clips cinematográficos.
- **Descarga Optimizada**: Uso de `ffmpeg` para extraer fragmentos específicos directamente desde el stream original.

## 🛠️ Configuración (Fly.io)

El sistema utiliza las siguientes variables de entorno:

| Variable | Descripción |
|----------|-------------|
| `GEMINI_API_KEY` | Clave principal para generación de guiones. |
| `GEMINI_API_KEY_B, C...` | Claves adicionales para rotación automática de Gemini. |
| `OPENAI_API_KEY` | Clave para el fallback con **GPT-4o-mini** y generación de miniaturas. |
| `PEXELS_API_KEY` | Fallback para clips de stock. |
| `PIXABAY_API_KEY`| Fallback secundario para clips de stock. |
| `YOUTUBE_OAUTH2_DATA` | (Opcional) JSON unificado para subida a YouTube. |

## 📺 Cómo agregar más canales de YouTube

El sistema permite escalar a un número ilimitado de canales siguiendo estos pasos:

1. **Obtener las Credenciales**: Debes tener el JSON de las credenciales OAuth2 (formato `authorized_user_info`) para el nuevo canal.
2. **Configurar el Secreto**: Sube el JSON a Fly.io (o tu entorno) usando el prefijo `YOUTUBE_CREDENTIALS_FILE_` seguido del identificador del canal.
3. **Uso en Peticiones**: Al enviar una solicitud al endpoint `/trigger-video`, simplemente especifica el identificador en el campo `canal`:
   ```json
   {
     "tema_recomendado": "Matrix",
     "canal": "CHANNEL_NAME_3"
   }
   ```
   *El sistema buscará automáticamente la variable `YOUTUBE_CREDENTIALS_FILE_CHANNEL_NAME_3`.*

## ⚙️ Funcionamiento

1. **Trigger**: El sistema recibe un POST en `/trigger-video`.
2. **IA (Guion)**: Genera el guion con Gemini. Si falla, cambia automáticamente a **GPT-4o-mini**.
3. **Búsqueda**: Utiliza la API de Peliprex para encontrar material visual de la película.
4. **Descarga**: Extrae fragmentos aleatorios usando `ffmpeg`.
5. **Edición**: Ensambla el video con audio TTS, música y subtítulos.
6. **Upload**: Sube el video al canal de YouTube especificado dinámicamente.

## 📦 Despliegue

1. Clona el repositorio.
2. Configura tus secretos:
   ```bash
   fly secrets set GEMINI_API_KEY=... OPENAI_API_KEY=... PEXELS_API_KEY=...
   ```
3. Despliega:
   ```bash
   fly deploy
   ```

---
*Desarrollado para la automatización eficiente de contenido cinematográfico.*
