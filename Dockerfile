# ═══════════════════════════════════════════════════════════════
# El Tío Jota - Auto Video System
# Dockerfile para despliegue en Fly.io
# ═══════════════════════════════════════════════════════════════

FROM python:3.11-slim-bookworm

# Metadatos
LABEL maintainer="El Tío Jota"
LABEL description="Sistema automático de generación de videos para YouTube"
LABEL version="1.0.0"

# ─── Variables de entorno del sistema ───────────────────────────
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ─── Instalar dependencias del sistema ──────────────────────────
# ffmpeg: procesamiento de video/audio
# fonts: para subtítulos
# imagemagick: para TextClip en MoviePy
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsm6 \
    libxext6 \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libfontconfig1 \
    libfreetype6 \
    imagemagick \
    fonts-dejavu-core \
    fonts-liberation \
    ca-certificates \
    wget \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ─── Configurar ImageMagick para MoviePy ────────────────────────
# Necesario para que TextClip funcione correctamente
RUN sed -i 's/<policy domain="path" rights="none" pattern="@\*"/<!-- <policy domain="path" rights="none" pattern="@*" -->/' \
    /etc/ImageMagick-6/policy.xml 2>/dev/null || true && \
    sed -i 's/rights="none" pattern="PDF"/rights="read|write" pattern="PDF"/' \
    /etc/ImageMagick-6/policy.xml 2>/dev/null || true

# ─── Crear directorio de trabajo ────────────────────────────────
WORKDIR /app

# ─── Instalar dependencias Python ───────────────────────────────
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# ─── Copiar código del proyecto ─────────────────────────────────
COPY . .

# ─── Crear directorios necesarios ───────────────────────────────
RUN mkdir -p \
    assets/music \
    assets/fonts \
    output \
    logs \
    temp/audio \
    temp/video \
    temp/images \
    credentials

# ─── Dar permisos de ejecución ──────────────────────────────────
RUN chmod +x main.py

# ─── Puerto para health checks de Fly.io ────────────────────────
EXPOSE 8080

# ─── Health check ───────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD wget -qO- http://localhost:8080/health || exit 1

# ─── Comando por defecto ─────────────────────────────────────────
# RUN_MODE puede ser: once | scheduled | server
CMD ["python", "main.py"]
