FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    TZ=America/Mexico_City

# Instalar dependencias del sistema incluyendo ImageMagick y Node.js para yt-dlp
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-liberation \
    fontconfig \
    ca-certificates \
    wget \
    curl \
    tzdata \
    imagemagick \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && fc-cache -fv \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Configurar ImageMagick para permitir la creación de TextClips en MoviePy
# 1. Habilitar permisos de lectura/escritura para rutas
# 2. Eliminar restricciones de PDF/Coder
# 3. Eliminar o aumentar límites de recursos que causan "width or height exceeds limit"
RUN sed -i 's/policy domain="path" rights="none" pattern="@\*"/policy domain="path" rights="read|write" pattern="@\*"/g' /etc/ImageMagick-6/policy.xml && \
    sed -i '/<policy domain="coder" rights="none" pattern="PDF" \/>/d' /etc/ImageMagick-6/policy.xml && \
    sed -i 's/<policy domain="resource" name="width" value="[^"]*"\/>/<policy domain="resource" name="width" value="16KP"\/>/g' /etc/ImageMagick-6/policy.xml && \
    sed -i 's/<policy domain="resource" name="height" value="[^"]*"\/>/<policy domain="resource" name="height" value="16KP"\/>/g' /etc/ImageMagick-6/policy.xml && \
    sed -i 's/<policy domain="resource" name="area" value="[^"]*"\/>/<policy domain="resource" name="area" value="1GB"\/>/g' /etc/ImageMagick-6/policy.xml && \
    sed -i 's/<policy domain="resource" name="disk" value="[^"]*"\/>/<policy domain="resource" name="disk" value="1GB"\/>/g' /etc/ImageMagick-6/policy.xml && \
    sed -i 's/<policy domain="resource" name="map" value="[^"]*"\/>/<policy domain="resource" name="map" value="512MB"\/>/g' /etc/ImageMagick-6/policy.xml && \
    sed -i 's/<policy domain="resource" name="memory" value="[^"]*"\/>/<policy domain="resource" name="memory" value="512MB"\/>/g' /etc/ImageMagick-6/policy.xml

# Establecer variable de entorno para que MoviePy encuentre ImageMagick
ENV IMAGEMAGICK_BINARY=/usr/bin/convert
# Configurar Node.js como motor JS para yt-dlp
ENV YTDLP_JS_RUNTIME=node
ENV PATH="/usr/bin/node:${PATH}"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

    # Crear directorios necesarios
RUN mkdir -p assets/music assets/fonts output logs temp/audio temp/video temp/images credentials src && chmod -R 777 credentials

COPY . .

EXPOSE 8080

# El comando de arranque directo, sin intentar swapon
CMD ["python", "main.py"]
