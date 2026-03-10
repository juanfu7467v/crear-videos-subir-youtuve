'''# 🎬 El Tío Jota - Auto Video System
# Dockerfile optimizado para Fly.io con soporte para MoviePy y Edge-TTS

FROM python:3.11-slim-bookworm

# Evitar prompts interactivos y configurar variables de entorno
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    TZ=America/Mexico_City

# Instalar dependencias esenciales del sistema
# ffmpeg: para procesamiento de video
# imagemagick: necesario para TextClip de MoviePy
# fonts-liberation: fuentes estándar para subtítulos
# tzdata: para manejo de zonas horarias
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    imagemagick \
    fonts-liberation \
    ca-certificates \
    wget \
    tzdata \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Configurar la política de seguridad de ImageMagick para permitir la edición de texto
# Esto es CRÍTICO para que MoviePy pueda generar subtítulos
RUN sed -i 's/rights="none" pattern="@\*"/rights="read|write" pattern="@*"/' /etc/ImageMagick-6/policy.xml || true

WORKDIR /app

# Copiar requirements primero para aprovechar el cache de Docker
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Asegurar que existan todos los directorios necesarios ANTES de copiar el código
# Esto evita errores si el repositorio contiene archivos con los mismos nombres que los directorios
RUN mkdir -p assets/music assets/fonts output logs temp/audio temp/video temp/images credentials

# Copiar el resto del código
COPY . .

# Exponer el puerto que Fly.io espera (8080 por defecto)
EXPOSE 8080

# Comando de ejecución
# El sistema iniciará el servidor receptor definido en main.py
CMD ["python", "main.py"]
'''
