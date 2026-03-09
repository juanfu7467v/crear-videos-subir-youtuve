#!/usr/bin/env python3
"""
setup.py
─────────
Script de configuración inicial del sistema.
Verifica dependencias, crea estructura y descarga recursos.

Uso:
    python setup.py
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path


def print_header():
    print("""
╔══════════════════════════════════════════════════════════════╗
║          EL TÍO JOTA - Sistema Automático de Videos          ║
║                    Configuración Inicial                      ║
╚══════════════════════════════════════════════════════════════╝
""")


def check_python():
    """Verifica versión de Python."""
    print("🐍 Verificando Python...")
    v = sys.version_info
    if v.major < 3 or (v.major == 3 and v.minor < 10):
        print(f"   ❌ Python {v.major}.{v.minor} detectado. Se requiere Python 3.10+")
        sys.exit(1)
    print(f"   ✅ Python {v.major}.{v.minor}.{v.micro}")


def check_ffmpeg():
    """Verifica que ffmpeg esté instalado."""
    print("🎬 Verificando ffmpeg...")
    if shutil.which("ffmpeg"):
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        version = result.stdout.split("\n")[0]
        print(f"   ✅ {version[:50]}")
    else:
        print("   ❌ ffmpeg no encontrado")
        print("   Instalar con:")
        if sys.platform == "linux":
            print("     sudo apt-get install ffmpeg")
        elif sys.platform == "darwin":
            print("     brew install ffmpeg")
        elif sys.platform == "win32":
            print("     winget install ffmpeg")
        sys.exit(1)


def install_requirements():
    """Instala dependencias de Python."""
    print("📦 Instalando dependencias Python...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "-q"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print("   ✅ Dependencias instaladas")
    else:
        print(f"   ⚠️  Algunos paquetes fallaron: {result.stderr[:200]}")


def create_directories():
    """Crea la estructura de directorios."""
    print("📁 Creando estructura de directorios...")
    dirs = [
        "assets/music",
        "assets/fonts",
        "output",
        "logs",
        "temp/audio",
        "temp/video",
        "temp/images",
        "credentials",
    ]
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
    print("   ✅ Directorios creados")


def create_env_file():
    """Crea el archivo .env si no existe."""
    print("⚙️  Configurando variables de entorno...")
    env_path = Path(".env")

    if env_path.exists():
        print("   ℹ️  .env ya existe, omitiendo")
        return

    if Path(".env.example").exists():
        shutil.copy(".env.example", ".env")
        print("   ✅ .env creado desde .env.example")
        print("   ⚠️  IMPORTANTE: Edita .env y añade tus API keys")
    else:
        print("   ❌ .env.example no encontrado")


def download_music():
    """Descarga música sin copyright."""
    print("🎵 Descargando música sin copyright...")
    result = subprocess.run(
        [sys.executable, "download_music.py"],
        timeout=300
    )
    if result.returncode == 0:
        music_count = len(list(Path("assets/music").glob("*.mp3")))
        print(f"   ✅ {music_count} pistas de música disponibles")
    else:
        print("   ⚠️  Descarga de música incompleta (el sistema puede funcionar sin ella)")


def verify_env_vars():
    """Verifica que las variables críticas estén configuradas."""
    print("🔑 Verificando API keys...")

    from dotenv import load_dotenv
    load_dotenv()

    required = {
        "GEMINI_API_KEY": "https://aistudio.google.com/app/apikey",
        "PEXELS_API_KEY": "https://www.pexels.com/api/",
        "PIXABAY_API_KEY": "https://pixabay.com/api/docs/",
    }

    all_ok = True
    for var, url in required.items():
        val = os.getenv(var, "")
        if val and val != f"tu_{var.lower()}_aqui":
            print(f"   ✅ {var}: configurada")
        else:
            print(f"   ⚠️  {var}: NO configurada → {url}")
            all_ok = False

    yt_creds = os.getenv("YOUTUBE_CREDENTIALS_FILE", "credentials/youtube_credentials.json")
    if Path(yt_creds).exists():
        print(f"   ✅ YouTube credentials: {yt_creds}")
    else:
        print(f"   ⚠️  YouTube credentials NO encontradas → {yt_creds}")
        print("      Descarga desde: https://console.cloud.google.com/")
        all_ok = False

    return all_ok


def test_tts():
    """Prueba el sistema TTS."""
    print("🔊 Probando Edge-TTS...")
    try:
        sys.path.insert(0, ".")
        from src.tts_engine import TTSEngine
        tts = TTSEngine()
        tts.generate_audio(
            text="Hola, soy el sistema automático de El Tío Jota.",
            output_path="temp/test_audio.mp3",
            voice="es-MX-DaliaNeural",
        )
        if Path("temp/test_audio.mp3").exists():
            size = Path("temp/test_audio.mp3").stat().st_size
            print(f"   ✅ Edge-TTS funcionando ({size/1024:.1f} KB)")
        else:
            print("   ❌ TTS no generó audio")
    except Exception as e:
        print(f"   ❌ Error en TTS: {e}")


def print_summary(env_ok: bool):
    """Imprime resumen de la configuración."""
    print("""
╔══════════════════════════════════════════════════════════════╗
║                    RESUMEN DE CONFIGURACIÓN                   ║
╚══════════════════════════════════════════════════════════════╝""")

    if env_ok:
        print("""
✅ Sistema listo para usar!

COMANDOS DISPONIBLES:
──────────────────────────────────────────────────────────────
# Ejecutar una vez (prueba)
python main.py

# Modo programado (producción)
RUN_MODE=scheduled python main.py

# Modo servidor (para Fly.io)
RUN_MODE=server python main.py

DESPLEGAR EN FLY.IO:
──────────────────────────────────────────────────────────────
1. flyctl auth login
2. flyctl launch --no-deploy
3. flyctl secrets set GEMINI_API_KEY=xxx PEXELS_API_KEY=xxx \\
                      PIXABAY_API_KEY=xxx API_SECRET_KEY=xxx
4. flyctl volumes create el_tio_jota_data --size 5 --region mia
5. flyctl deploy
""")
    else:
        print("""
⚠️  Configuración incompleta.

PRÓXIMOS PASOS:
──────────────────────────────────────────────────────────────
1. Edita el archivo .env con tus API keys
2. Descarga las credenciales de YouTube y guárdalas en:
   credentials/youtube_credentials.json
3. Ejecuta nuevamente: python setup.py

DOCUMENTACIÓN:
──────────────────────────────────────────────────────────────
Lee el archivo README.md para instrucciones detalladas.
""")


def main():
    print_header()

    check_python()
    check_ffmpeg()
    create_directories()
    create_env_file()
    install_requirements()
    download_music()
    test_tts()
    env_ok = verify_env_vars()
    print_summary(env_ok)


if __name__ == "__main__":
    main()
