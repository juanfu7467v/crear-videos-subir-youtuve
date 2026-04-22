# Usar una imagen base de Python limpia y ligera
FROM python:3.11-slim-bookworm

# Configuración de entorno
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    TZ=America/Mexico_City \
    IMAGEMAGICK_BINARY=/usr/bin/convert

# Instalar dependencias del sistema
# Se eliminan librerías extras redundantes que pueden causar conflictos de versión con el binario de FFmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    imagemagick \
    fonts-liberation \
    fontconfig \
    ca-certificates \
    wget \
    curl \
    tzdata \
    && fc-cache -fv \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Configurar ImageMagick para permitir operaciones de MoviePy
RUN sed -i 's/policy domain="path" rights="none" pattern="@\*"/policy domain="path" rights="read|write" pattern="@\*"/g' /etc/ImageMagick-6/policy.xml && \
    sed -i '/<policy domain="coder" rights="none" pattern="PDF" \/>/d' /etc/ImageMagick-6/policy.xml && \
    sed -i 's/<policy domain="resource" name="width" value="[^"]*"\/>/<policy domain="resource" name="width" value="16KP"\/>/g' /etc/ImageMagick-6/policy.xml && \
    sed -i 's/<policy domain="resource" name="height" value="[^"]*"\/>/<policy domain="resource" name="height" value="16KP"\/>/g' /etc/ImageMagick-6/policy.xml && \
    sed -i 's/<policy domain="resource" name="area" value="[^"]*"\/>/<policy domain="resource" name="area" value="2GB"\/>/g' /etc/ImageMagick-6/policy.xml && \
    sed -i 's/<policy domain="resource" name="memory" value="[^"]*"\/>/<policy domain="resource" name="memory" value="1GB"\/>/g' /etc/ImageMagick-6/policy.xml

WORKDIR /app

# Instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Crear estructura de directorios necesaria
RUN mkdir -p assets/music assets/fonts assets/temp output logs credentials src && \
    chmod -R 777 credentials

# Copiar el código fuente
COPY . .

# Exponer puerto para el servidor web
EXPOSE 8080

# Comando de inicio
CMD ["python", "main.py"]
