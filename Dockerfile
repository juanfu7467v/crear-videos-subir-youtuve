FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    TZ=America/Mexico_City

# Instalar dependencias del sistema incluyendo ImageMagick para los subtítulos
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-liberation \
    ca-certificates \
    wget \
    tzdata \
    imagemagick \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Configurar ImageMagick para permitir la creación de TextClips en MoviePy
RUN sed -i 's/policy domain="path" rights="none" pattern="@\*"/policy domain="path" rights="read|write" pattern="@\*"/g' /etc/ImageMagick-6/policy.xml

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Crear directorios necesarios
RUN mkdir -p assets/music assets/fonts output logs temp/audio temp/video temp/images credentials src

COPY . .

EXPOSE 8080

# El comando de arranque directo, sin intentar swapon
CMD ["python", "main.py"]
