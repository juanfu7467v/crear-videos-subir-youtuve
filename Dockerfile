FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    TZ=America/Mexico_City

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-liberation \
    ca-certificates \
    wget \
    tzdata \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

RUN mkdir -p assets/music assets/fonts output logs temp/audio temp/video temp/images credentials src

COPY . .

EXPOSE 8080

# Script para activar swap si es necesario y arrancar la app
RUN echo '#!/bin/bash\n\
# Crear un archivo swap de 512MB si no existe\n\
if [ ! -f /swapfile ]; then\n\
    fallocate -l 512M /swapfile\n\
    chmod 600 /swapfile\n\
    mkswap /swapfile\n\
fi\n\
# Intentar activar swap (puede fallar en algunos entornos de contenedores, pero Fly.io lo permite en ciertas configs)\n\
swapon /swapfile || true\n\
exec python main.py' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

CMD ["/app/entrypoint.sh"]
