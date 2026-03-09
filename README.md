# 🎬 El Tío Jota - Sistema Automático de Videos

Sistema de **generación, edición y publicación autónoma** de videos para YouTube.
Crea videos desde cero usando IA, sin intervención manual.

---

## ✨ Características

| Módulo | Tecnología | Costo |
|--------|-----------|-------|
| 🤖 IA / Guiones | Gemini 1.5 Flash | Gratis (nivel gratuito) |
| 🔊 Voz (TTS) | Edge-TTS (Microsoft) | **Gratis** |
| 🎬 Clips de video | Pexels API + Pixabay API | **Gratis** |
| 🖼️ Imágenes IA | Pollinations.ai | **Gratis** |
| 🎵 Música de fondo | Archivos locales (sin copyright) | **Gratis** |
| 🎞️ Edición de video | MoviePy + ffmpeg | **Gratis** |
| ✅ Control de calidad | Gemini Vision | Gratis (nivel gratuito) |
| 📤 Publicación | YouTube Data API v3 | **Gratis** |
| ☁️ Hosting | Fly.io | ~$0-5/mes |

**Costo total estimado: $0 - $5 USD/mes**

---

## 🏗️ Arquitectura del Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                    PIPELINE AUTOMÁTICO                       │
├──────────┬──────────┬──────────┬──────────┬────────────────┤
│ PASO 1   │ PASO 2   │ PASO 3   │ PASO 4   │ PASO 5         │
│ Tendencia│ Guion    │ Audio    │ Media    │ Edición        │
│ Gemini   │ Gemini   │ Edge-TTS │ Pexels   │ MoviePy        │
│          │          │          │ Pixabay  │ + ffmpeg       │
│          │          │          │ Pollins. │                │
└──────────┴──────────┴──────────┴──────────┴────────────────┘
     ▼           ▼         ▼          ▼            ▼
┌──────────┬──────────┐
│ PASO 6   │ PASO 7   │
│ QC       │ YouTube  │
│ Gemini   │ Upload   │
│ Vision   │ API v3   │
└──────────┴──────────┘
```

---

## 🚀 Instalación Local

### Requisitos previos
- Python 3.10+
- ffmpeg instalado en el sistema

```bash
# Ubuntu/Debian
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg

# Windows
winget install ffmpeg
```

### Paso 1: Clonar e instalar

```bash
git clone https://github.com/tu-usuario/el-tio-jota-auto.git
cd el-tio-jota-auto

# Ejecutar configuración automática
python setup.py
```

### Paso 2: Obtener API Keys gratuitas

#### 🤖 Gemini (IA)
1. Ve a https://aistudio.google.com/app/apikey
2. Haz clic en "Create API Key"
3. Copia la key

#### 🎬 Pexels (Videos)
1. Ve a https://www.pexels.com/api/
2. Crea una cuenta gratuita
3. Haz clic en "Your API Key"

#### 🖼️ Pixabay (Videos/Imágenes)
1. Ve a https://pixabay.com/api/docs/
2. Crea cuenta y accede a tu API key

#### 📤 YouTube API
1. Ve a https://console.cloud.google.com/
2. Crea un nuevo proyecto
3. Activa la **YouTube Data API v3**
4. Ve a "Credenciales" → "Crear credenciales" → "ID de cliente OAuth 2.0"
5. Tipo: "Aplicación de escritorio"
6. Descarga el JSON y guárdalo en: `credentials/youtube_credentials.json`

### Paso 3: Configurar variables

```bash
cp .env.example .env
nano .env  # Edita con tus keys
```

### Paso 4: Descargar música

```bash
python download_music.py
```

### Paso 5: Añadir música manualmente (recomendado)

Descarga ~30 pistas sin copyright de:
- https://pixabay.com/music/ (Creative Commons)
- https://freemusicarchive.org/
- https://soundcloud.com/royalty-free-audio-loops

Guárdalas en la carpeta `assets/music/`

---

## ▶️ Uso

### Ejecutar una vez (para pruebas)

```bash
RUN_MODE=once python main.py
```

### Modo programado (producción local)

```bash
# Genera videos a las 8:00 AM y 6:00 PM
SCHEDULE_TIMES=08:00,18:00 RUN_MODE=scheduled python main.py
```

### Verificar el sistema

```bash
# Probar solo el TTS
python -c "from src.tts_engine import TTSEngine; TTSEngine().generate_audio('Hola mundo', '/tmp/test.mp3')"

# Ver voces disponibles
python -c "from src.tts_engine import TTSEngine; print(TTSEngine().list_voices())"
```

---

## ☁️ Despliegue en Fly.io

### Paso 1: Instalar flyctl

```bash
# macOS/Linux
curl -L https://fly.io/install.sh | sh

# Windows
iwr https://fly.io/install.ps1 -useb | iex
```

### Paso 2: Login y configuración

```bash
flyctl auth login

# Inicializar app (sin desplegar aún)
flyctl launch --no-deploy
```

### Paso 3: Configurar secretos

```bash
flyctl secrets set \
  GEMINI_API_KEY=tu_key_aqui \
  PEXELS_API_KEY=tu_key_aqui \
  PIXABAY_API_KEY=tu_key_aqui \
  API_SECRET_KEY=secreto-largo-y-seguro-aqui
```

### Paso 4: Crear volumen para música

```bash
# 5GB para música y videos temporales
flyctl volumes create el_tio_jota_data --size 5 --region mia
```

### Paso 5: Subir credenciales de YouTube

```bash
# Las credenciales de YouTube NO deben ir como secretos de Fly.io
# En su lugar, usa fly sftp o cópialas al volumen

flyctl ssh console
# Dentro del contenedor:
# mkdir -p /app/credentials
# (usar fly sftp para subir el archivo)
```

```bash
# Método alternativo: codificar en base64
cat credentials/youtube_credentials.json | base64
flyctl secrets set YOUTUBE_CREDS_B64=<base64_string>
```

### Paso 6: Desplegar

```bash
flyctl deploy

# Verificar que funciona
flyctl status
flyctl logs

# Probar health check
curl https://el-tio-jota-auto.fly.dev/health
```

### Paso 7: Trigger manual (opcional)

```bash
curl -X POST https://el-tio-jota-auto.fly.dev/run \
  -H "X-API-Key: tu-api-secret-key"
```

---

## 📊 Endpoints del Servidor

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/` | GET | Info del servicio |
| `/health` | GET | Health check de Fly.io |
| `/status` | GET | Estado y últimos videos |
| `/schedule` | GET | Horarios programados |
| `/run` | POST | Trigger manual (requiere X-API-Key) |

---

## 🎙️ Voces disponibles (Edge-TTS)

| Código | País | Género |
|--------|------|--------|
| `es-MX-DaliaNeural` | México | Femenina |
| `es-MX-JorgeNeural` | México | Masculino |
| `es-ES-ElviraNeural` | España | Femenina |
| `es-ES-AlvaroNeural` | España | Masculino |
| `es-AR-ElenaNeural` | Argentina | Femenina |
| `es-CO-SalomeNeural` | Colombia | Femenina |
| `es-PE-CamilaNeural` | Perú | Femenina |

Cambiar voz en `.env`:
```
DEFAULT_VOICE=es-MX-JorgeNeural
```

---

## ⚙️ Variables de configuración

| Variable | Descripción | Valor por defecto |
|----------|-------------|-------------------|
| `RUN_MODE` | Modo de ejecución | `server` |
| `SCHEDULE_TIMES` | Horarios de publicación | `08:00,18:00` |
| `TIMEZONE` | Zona horaria | `America/Mexico_City` |
| `DEFAULT_VOICE` | Voz TTS | `es-MX-DaliaNeural` |
| `DEFAULT_SPEECH_RATE` | Velocidad de voz | `+10%` |
| `BG_MUSIC_VOLUME` | Volumen música de fondo | `0.08` (8%) |
| `USE_SUBTITLES` | Activar subtítulos | `true` |
| `MIN_QC_SCORE` | Score mínimo para publicar | `60` |
| `CHANNEL_NAME` | Nombre del canal | `El Tío Jota` |

---

## 🐛 Solución de problemas

### Error: "No module named 'moviepy'"
```bash
pip install moviepy==1.0.3
```

### Error: "ffmpeg not found"
```bash
sudo apt-get install ffmpeg  # Linux
brew install ffmpeg           # macOS
```

### Error: "TextClip requires ImageMagick"
```bash
sudo apt-get install imagemagick
# Luego editar /etc/ImageMagick-6/policy.xml
```

### YouTube no autoriza
1. Verifica que la API esté activada en Google Cloud Console
2. Asegúrate de que el proyecto tenga la **YouTube Data API v3** habilitada
3. Para la primera ejecución, necesitas ejecutar localmente para completar el flujo OAuth

---

## 📁 Estructura del proyecto

```
el-tio-jota-auto/
├── main.py                 # Entrypoint principal
├── setup.py                # Configuración inicial
├── download_music.py       # Descarga música sin copyright
├── requirements.txt        # Dependencias Python
├── Dockerfile              # Para Fly.io
├── fly.toml                # Configuración Fly.io
├── .env.example            # Template de variables
├── .gitignore
├── README.md
├── src/
│   ├── __init__.py
│   ├── trend_analyzer.py   # Análisis de tendencias (Gemini)
│   ├── script_generator.py # Generación de guiones (Gemini)
│   ├── tts_engine.py       # Texto a voz (Edge-TTS)
│   ├── media_fetcher.py    # Descarga clips (Pexels/Pixabay/Pollinations)
│   ├── video_editor.py     # Edición de video (MoviePy)
│   ├── quality_checker.py  # Control de calidad (Gemini Vision)
│   ├── youtube_uploader.py # Publicación en YouTube (API v3)
│   ├── scheduler.py        # Gestión de horarios
│   └── web_server.py       # Servidor HTTP (Fly.io)
├── assets/
│   └── music/              # ← Añadir aquí 30 pistas MP3
├── credentials/            # Credenciales de YouTube (NO subir a git)
├── output/                 # Videos generados
├── temp/                   # Archivos temporales
└── logs/                   # Registros del pipeline
```

---

## 📜 Licencia

MIT License - Uso libre para proyectos personales y comerciales.

---

**Hecho con ❤️ para El Tío Jota**
