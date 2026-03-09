# 🎬 El Tío Jota - Auto Video System
# Dockerfile optimizado para Fly.io

FROM python:3.11-slim-bookworm

# Metadatos
LABEL maintainer="El Tío Jota"
LABEL description="Sistema automático de generación de videos para YouTube"

# Variables de entorno
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    TZ=America/Mexico_City

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    imagemagick \
    fonts-liberation \
    ca-certificates \
    wget \
    tzdata \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Configurar ImageMagick para MoviePy (TextClip)
RUN sed -i 's/rights="none" pattern="@\*"/rights="read|write" pattern="@*"/' /etc/ImageMagick-6/policy.xml || true

WORKDIR /app

# Instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY . .

# Crear estructura de directorios
RUN mkdir -p assets/music assets/fonts output logs temp/audio temp/video temp/images credentials

# Exponer puerto para Fly.io
EXPOSE 8080

# Comando de inicio
CMD ["python", "main.py"]
