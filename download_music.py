#!/usr/bin/env python3
"""
download_music.py
──────────────────
Script auxiliar para descargar ~30 pistas de música sin copyright
desde fuentes gratuitas y legales.

Uso:
    python download_music.py

Las pistas se guardan en: assets/music/
"""

import os
import time
import logging
import requests
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

MUSIC_DIR = Path("assets/music")

# ─── Pistas de música sin copyright de Pixabay ───────────────────
# Fuente: pixabay.com/music (Creative Commons - Libre de royalties)
# Estas URLs son de la API pública de Pixabay Music
TRACKS = [
    # Upbeat / Motivacional
    {"name": "01_upbeat_corporate.mp3",    "url": "https://cdn.pixabay.com/download/audio/2022/01/18/audio_d0c6ff1bab.mp3"},
    {"name": "02_positive_energy.mp3",     "url": "https://cdn.pixabay.com/download/audio/2022/03/15/audio_0af4ca3e88.mp3"},
    {"name": "03_inspiring_cinematic.mp3", "url": "https://cdn.pixabay.com/download/audio/2021/08/09/audio_dc39bde808.mp3"},
    {"name": "04_uplifting_background.mp3","url": "https://cdn.pixabay.com/download/audio/2022/04/27/audio_67f108d235.mp3"},
    {"name": "05_motivational_beat.mp3",   "url": "https://cdn.pixabay.com/download/audio/2022/11/22/audio_febc508520.mp3"},

    # Chill / Ambiente
    {"name": "06_lofi_chill.mp3",          "url": "https://cdn.pixabay.com/download/audio/2022/05/27/audio_1808fbf07a.mp3"},
    {"name": "07_ambient_relaxing.mp3",    "url": "https://cdn.pixabay.com/download/audio/2021/11/25/audio_91b32dc84b.mp3"},
    {"name": "08_soft_piano.mp3",          "url": "https://cdn.pixabay.com/download/audio/2021/08/04/audio_0625f60b39.mp3"},
    {"name": "09_calm_background.mp3",     "url": "https://cdn.pixabay.com/download/audio/2022/08/02/audio_884fe92c21.mp3"},
    {"name": "10_peaceful_guitar.mp3",     "url": "https://cdn.pixabay.com/download/audio/2022/01/20/audio_b66d0d3baf.mp3"},

    # Energético / Viral
    {"name": "11_hip_hop_beat.mp3",        "url": "https://cdn.pixabay.com/download/audio/2022/10/25/audio_946b649ae5.mp3"},
    {"name": "12_electronic_dance.mp3",    "url": "https://cdn.pixabay.com/download/audio/2022/01/11/audio_8cb9e3df93.mp3"},
    {"name": "13_funky_groove.mp3",        "url": "https://cdn.pixabay.com/download/audio/2022/03/24/audio_1f7e21fd9e.mp3"},
    {"name": "14_trap_background.mp3",     "url": "https://cdn.pixabay.com/download/audio/2021/10/11/audio_8a6d3f28bd.mp3"},
    {"name": "15_modern_beat.mp3",         "url": "https://cdn.pixabay.com/download/audio/2022/07/13/audio_0f4c6d45c4.mp3"},

    # Suspense / Drama
    {"name": "16_suspense_intro.mp3",      "url": "https://cdn.pixabay.com/download/audio/2022/01/13/audio_7e6d7b10a1.mp3"},
    {"name": "17_dramatic_cinematic.mp3",  "url": "https://cdn.pixabay.com/download/audio/2021/12/29/audio_1ec89b3e7a.mp3"},
    {"name": "18_tension_build.mp3",       "url": "https://cdn.pixabay.com/download/audio/2022/09/14/audio_c8e5d44fde.mp3"},
    {"name": "19_dark_ambient.mp3",        "url": "https://cdn.pixabay.com/download/audio/2021/11/01/audio_fd8e609937.mp3"},
    {"name": "20_mystery_theme.mp3",       "url": "https://cdn.pixabay.com/download/audio/2022/02/07/audio_d1718ab41b.mp3"},

    # Alegre / Divertido
    {"name": "21_happy_ukulele.mp3",       "url": "https://cdn.pixabay.com/download/audio/2021/09/06/audio_3f6b65dd45.mp3"},
    {"name": "22_cheerful_pop.mp3",        "url": "https://cdn.pixabay.com/download/audio/2022/05/16/audio_5f4c6e2f1d.mp3"},
    {"name": "23_sunny_morning.mp3",       "url": "https://cdn.pixabay.com/download/audio/2021/08/08/audio_ba6a4e5b72.mp3"},
    {"name": "24_playful_theme.mp3",       "url": "https://cdn.pixabay.com/download/audio/2022/03/10/audio_c8c8a3f35f.mp3"},
    {"name": "25_cartoon_fun.mp3",         "url": "https://cdn.pixabay.com/download/audio/2021/10/25/audio_58c67a5e14.mp3"},

    # Cinematográfico
    {"name": "26_epic_orchestral.mp3",     "url": "https://cdn.pixabay.com/download/audio/2022/01/25/audio_2b3cc55f43.mp3"},
    {"name": "27_adventure_theme.mp3",     "url": "https://cdn.pixabay.com/download/audio/2021/11/15/audio_6e2e65b8df.mp3"},
    {"name": "28_heroic_music.mp3",        "url": "https://cdn.pixabay.com/download/audio/2022/06/07/audio_d7a9c72f5b.mp3"},
    {"name": "29_nature_sounds.mp3",       "url": "https://cdn.pixabay.com/download/audio/2022/03/03/audio_c8f9e3a7f1.mp3"},
    {"name": "30_documentary_bg.mp3",      "url": "https://cdn.pixabay.com/download/audio/2021/09/22/audio_73e4c7d9ef.mp3"},
]


def download_track(name: str, url: str, save_dir: Path) -> bool:
    """Descarga una pista de música."""
    save_path = save_dir / name

    if save_path.exists() and save_path.stat().st_size > 50000:
        logger.info(f"  ✓ Ya existe: {name}")
        return True

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; ElTioJotaBot/1.0)",
            "Accept": "audio/mpeg, audio/*, */*",
        }
        resp = requests.get(url, headers=headers, timeout=60, stream=True)
        resp.raise_for_status()

        with open(save_path, "wb") as f:
            downloaded = 0
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)
                downloaded += len(chunk)

        size_kb = save_path.stat().st_size / 1024
        if size_kb < 50:
            logger.warning(f"  ⚠ Archivo muy pequeño ({size_kb:.0f} KB): {name}")
            save_path.unlink(missing_ok=True)
            return False

        logger.info(f"  ✓ Descargado: {name} ({size_kb:.0f} KB)")
        return True

    except Exception as e:
        logger.warning(f"  ✗ Error descargando {name}: {e}")
        if save_path.exists():
            save_path.unlink(missing_ok=True)
        return False


def generate_placeholder_music(save_dir: Path, count: int = 5):
    """
    Genera archivos de música placeholder con ffmpeg como fallback.
    Crea tonos simples si no se puede descargar música real.
    """
    import subprocess

    frequencies = [220, 262, 294, 330, 349, 392, 440, 494]
    generated = 0

    for i in range(min(count, 10)):
        name = f"placeholder_{i+1:02d}.mp3"
        path = save_dir / name

        if path.exists():
            continue

        freq = frequencies[i % len(frequencies)]
        try:
            cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi",
                "-i", f"sine=frequency={freq}:duration=120",
                "-b:a", "128k",
                str(path)
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=30)
            if result.returncode == 0:
                logger.info(f"  ✓ Placeholder generado: {name}")
                generated += 1
        except Exception as e:
            logger.warning(f"  ✗ Error generando placeholder: {e}")

    return generated


def main():
    logger.info("═══════════════════════════════════════════════")
    logger.info("  Descargando música sin copyright")
    logger.info("  Fuente: Pixabay Music (Creative Commons)")
    logger.info("═══════════════════════════════════════════════")

    MUSIC_DIR.mkdir(parents=True, exist_ok=True)

    successful = 0
    failed = 0

    for i, track in enumerate(TRACKS):
        logger.info(f"\n[{i+1}/{len(TRACKS)}] {track['name']}")
        success = download_track(track["name"], track["url"], MUSIC_DIR)
        if success:
            successful += 1
        else:
            failed += 1
        time.sleep(0.5)  # Rate limiting

    logger.info(f"\n═══ Resultado ═══")
    logger.info(f"Descargadas: {successful}/{len(TRACKS)}")
    logger.info(f"Fallidas: {failed}")

    # Si pocas se descargaron, generar placeholders
    if successful < 5:
        logger.info("\nGenerando pistas placeholder con ffmpeg...")
        gen = generate_placeholder_music(MUSIC_DIR, 10)
        logger.info(f"Placeholders generados: {gen}")

    # Contar pistas finales
    final_count = len(list(MUSIC_DIR.glob("*.mp3")) + list(MUSIC_DIR.glob("*.wav")))
    logger.info(f"\n✅ Total de pistas disponibles: {final_count}")
    logger.info(f"   Ubicación: {MUSIC_DIR.absolute()}")

    if final_count == 0:
        logger.warning(
            "\n⚠️  No hay música disponible. El sistema funcionará sin música de fondo.\n"
            "   Añade archivos MP3 manualmente a la carpeta: assets/music/"
        )


if __name__ == "__main__":
    main()
