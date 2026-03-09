"""
video_editor.py
────────────────
Editor de video automático con MoviePy.
Combina clips, audio TTS, música de fondo, subtítulos y efectos.
"""

import logging
import os
import random
import subprocess
from pathlib import Path
from typing import Optional
import numpy as np

logger = logging.getLogger(__name__)


class VideoEditor:
    """
    Ensambla el video final usando MoviePy.
    Gestiona clips, audio, música, subtítulos y transiciones.
    """

    def __init__(self):
        self.default_resolution  = (1080, 1920)  # Vertical (Shorts)
        self.long_resolution     = (1920, 1080)  # Horizontal (Long)
        self.fps                 = 30
        self.bg_music_volume     = float(os.getenv("BG_MUSIC_VOLUME", "0.08"))
        self.use_subtitles       = os.getenv("USE_SUBTITLES", "true").lower() == "true"
        self.font_path           = os.getenv("FONT_PATH", "assets/fonts/bold.ttf")
        self.transition_duration = 0.5  # segundos de transición

    def create_video(
        self,
        audio_path: str,
        media_list: list,
        script_data: dict,
        format_type: str,
        output_path: str,
        channel_name: str = "El Tío Jota",
        music_dir: str = "assets/music",
    ) -> str:
        """
        Crea el video final combinando todos los elementos.

        Args:
            audio_path: Ruta al audio TTS
            media_list: Lista de dicts con clips/imágenes descargados
            script_data: Datos del guion (texto, segments, etc)
            format_type: "Short" o "Long"
            output_path: Ruta de salida del video
            channel_name: Nombre del canal para watermark
            music_dir: Carpeta con música de fondo

        Returns:
            Ruta al video final
        """
        from moviepy.editor import (
            VideoFileClip, ImageClip, AudioFileClip, CompositeAudioClip,
            concatenate_videoclips, CompositeVideoClip, TextClip,
        )
        from moviepy.audio.fx.all import volumex, audio_fadeout, audio_fadein

        is_short = "short" in format_type.lower()
        target_w, target_h = self.default_resolution if is_short else self.long_resolution

        logger.info(f"Editando video {'Short' if is_short else 'Long'} ({target_w}x{target_h})")

        # 1. Cargar audio principal (TTS)
        tts_audio = AudioFileClip(audio_path)
        total_duration = tts_audio.duration
        logger.info(f"Duración total del video: {total_duration:.1f}s")

        # 2. Preparar clips de video/imagen
        video_clips = self._prepare_video_clips(
            media_list, total_duration, target_w, target_h
        )

        if not video_clips:
            logger.warning("Sin clips de video, usando fondo de color")
            video_clips = [self._create_color_background(total_duration, target_w, target_h)]

        # 3. Concatenar clips y ajustar duración
        main_video = concatenate_videoclips(video_clips, method="compose")
        if main_video.duration < total_duration:
            main_video = main_video.loop(duration=total_duration)
        main_video = main_video.subclip(0, total_duration)

        # 4. Añadir música de fondo
        bg_music = self._get_background_music(music_dir, total_duration)

        # 5. Combinar audio TTS + música
        if bg_music:
            bg_music = bg_music.fx(volumex, self.bg_music_volume)
            bg_music = bg_music.fx(audio_fadein, 1.0).fx(audio_fadeout, 2.0)
            final_audio = CompositeAudioClip([tts_audio, bg_music])
        else:
            final_audio = tts_audio

        # 6. Añadir subtítulos
        subtitle_clips = []
        if self.use_subtitles and script_data.get("segments"):
            subtitle_clips = self._create_subtitles(
                script_data, total_duration, target_w, target_h
            )

        # 7. Añadir watermark/branding
        watermark = self._create_watermark(channel_name, target_w, target_h, total_duration)

        # 8. Componer video final
        all_clips = [main_video] + subtitle_clips
        if watermark:
            all_clips.append(watermark)

        final_video = CompositeVideoClip(all_clips, size=(target_w, target_h))
        final_video = final_video.set_audio(final_audio)
        final_video = final_video.set_duration(total_duration)

        # 9. Exportar
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"Exportando video: {output_path}")

        final_video.write_videofile(
            output_path,
            fps=self.fps,
            codec="libx264",
            audio_codec="aac",
            audio_bitrate="192k",
            bitrate="4000k",
            preset="fast",
            threads=os.cpu_count() or 2,
            logger=None,  # Suprimir logs de MoviePy
        )

        # Limpiar clips en memoria
        final_video.close()
        tts_audio.close()

        size_mb = Path(output_path).stat().st_size / (1024 * 1024)
        logger.info(f"✅ Video exportado: {output_path} ({size_mb:.1f} MB)")
        return output_path

    # ─── Preparación de clips ─────────────────────────────────
    def _prepare_video_clips(
        self, media_list: list, total_duration: float, target_w: int, target_h: int
    ) -> list:
        """Procesa y normaliza todos los clips al mismo formato."""
        from moviepy.editor import VideoFileClip, ImageClip

        clips = []
        clip_duration = max(3, total_duration / max(len(media_list), 1))

        for item in media_list:
            try:
                path = item.get("path", "")
                if not Path(path).exists():
                    continue

                media_type = item.get("type", "image")

                if media_type == "video":
                    clip = VideoFileClip(path, audio=False)
                    clip = self._normalize_clip(clip, target_w, target_h, clip_duration)
                else:
                    # Imagen → clip estático
                    img_duration = item.get("duration", clip_duration)
                    clip = ImageClip(path, duration=img_duration)
                    clip = self._normalize_clip(clip, target_w, target_h, img_duration)
                    # Ken Burns effect para imágenes
                    clip = self._apply_ken_burns(clip, target_w, target_h)

                clips.append(clip)

            except Exception as e:
                logger.warning(f"Error procesando clip {item.get('path', '?')}: {e}")
                continue

        return clips

    def _normalize_clip(self, clip, target_w: int, target_h: int, duration: float):
        """Redimensiona y recorta clip al tamaño objetivo."""
        from moviepy.editor import VideoFileClip, ImageClip

        # Redimensionar manteniendo aspect ratio con crop
        clip_w, clip_h = clip.size
        scale_w = target_w / clip_w
        scale_h = target_h / clip_h
        scale = max(scale_w, scale_h)

        new_w = int(clip_w * scale)
        new_h = int(clip_h * scale)

        clip = clip.resize((new_w, new_h))

        # Centrar y recortar
        x_center = new_w // 2
        y_center = new_h // 2
        clip = clip.crop(
            x_center=x_center,
            y_center=y_center,
            width=target_w,
            height=target_h,
        )

        # Ajustar duración
        if hasattr(clip, 'duration') and clip.duration:
            if clip.duration > duration:
                clip = clip.subclip(0, duration)
            elif clip.duration < duration:
                clip = clip.loop(duration=duration)
        else:
            clip = clip.set_duration(duration)

        return clip

    def _apply_ken_burns(self, clip, target_w: int, target_h: int):
        """
        Aplica efecto Ken Burns (zoom lento) a imágenes estáticas.
        Hace el video más dinámico y profesional.
        """
        from moviepy.editor import ImageClip

        duration = clip.duration
        start_scale = 1.0
        end_scale = 1.08  # Zoom in suave

        def zoom_effect(get_frame, t):
            progress = t / duration if duration > 0 else 0
            scale = start_scale + (end_scale - start_scale) * progress
            frame = get_frame(t)
            h, w = frame.shape[:2]
            new_h = int(h * scale)
            new_w = int(w * scale)

            try:
                from PIL import Image
                import numpy as np
                img = Image.fromarray(frame)
                img = img.resize((new_w, new_h), Image.LANCZOS)
                # Recortar al centro
                left = (new_w - w) // 2
                top = (new_h - h) // 2
                img = img.crop((left, top, left + w, top + h))
                return np.array(img)
            except ImportError:
                return frame

        return clip.fl(zoom_effect)

    # ─── Música de fondo ──────────────────────────────────────
    def _get_background_music(self, music_dir: str, duration: float):
        """
        Selecciona aleatoriamente una pista de música de la carpeta local.
        """
        from moviepy.editor import AudioFileClip

        music_path = Path(music_dir)
        if not music_path.exists():
            logger.warning(f"Carpeta de música no encontrada: {music_dir}")
            return None

        # Buscar archivos de audio
        audio_files = (
            list(music_path.glob("*.mp3")) +
            list(music_path.glob("*.wav")) +
            list(music_path.glob("*.ogg")) +
            list(music_path.glob("*.m4a"))
        )

        if not audio_files:
            logger.warning(f"No hay música en {music_dir}")
            return None

        # Selección aleatoria
        chosen = random.choice(audio_files)
        logger.info(f"🎵 Música seleccionada: {chosen.name}")

        try:
            music = AudioFileClip(str(chosen))
            # Loop si la música es más corta que el video
            if music.duration < duration:
                music = music.audio_loop(duration=duration)
            else:
                music = music.subclip(0, duration)
            return music
        except Exception as e:
            logger.error(f"Error cargando música {chosen}: {e}")
            return None

    # ─── Subtítulos ───────────────────────────────────────────
    def _create_subtitles(
        self, script_data: dict, total_duration: float, target_w: int, target_h: int
    ) -> list:
        """
        Crea clips de texto para subtítulos animados.
        """
        from moviepy.editor import TextClip, CompositeVideoClip

        subtitle_clips = []
        segments = script_data.get("segments", [])

        if not segments:
            # Crear subtítulo simple del guion completo
            return self._create_simple_subtitle(
                script_data.get("full_script", ""), total_duration, target_w, target_h
            )

        # Calcular tiempos por segmento
        seg_duration = total_duration / len(segments)

        for i, seg in enumerate(segments):
            text = seg.get("text", "")
            if not text or len(text) > 200:
                continue

            start_time = i * seg_duration
            end_time = min((i + 1) * seg_duration, total_duration)
            clip_duration = end_time - start_time

            # Dividir texto en líneas cortas para subtítulos
            lines = self._wrap_text(text, max_chars=40)
            subtitle_text = "\n".join(lines[:2])  # Máximo 2 líneas

            try:
                txt_clip = self._make_text_clip(
                    subtitle_text, clip_duration, target_w, target_h
                )
                if txt_clip:
                    txt_clip = txt_clip.set_start(start_time)
                    subtitle_clips.append(txt_clip)
            except Exception as e:
                logger.debug(f"Error creando subtítulo {i}: {e}")

        return subtitle_clips

    def _make_text_clip(self, text: str, duration: float, target_w: int, target_h: int):
        """Crea un clip de texto con estilo para YouTube Shorts."""
        from moviepy.editor import TextClip

        font_size = 52 if target_h > 1000 else 38

        try:
            # Intentar con PIL para mejor compatibilidad
            return self._make_pil_text_clip(text, duration, target_w, target_h, font_size)
        except Exception:
            pass

        try:
            # Fallback con ImageMagick
            txt = TextClip(
                text,
                fontsize=font_size,
                color="white",
                font="DejaVu-Sans-Bold",
                stroke_color="black",
                stroke_width=3,
                method="caption",
                size=(int(target_w * 0.9), None),
            )
            txt = txt.set_duration(duration)
            # Posición en el tercio inferior
            txt = txt.set_position(("center", target_h * 0.7))
            return txt
        except Exception as e:
            logger.debug(f"TextClip error: {e}")
            return None

    def _make_pil_text_clip(
        self, text: str, duration: float, target_w: int, target_h: int, font_size: int
    ):
        """Crea texto usando PIL como imagen."""
        from moviepy.editor import ImageClip
        from PIL import Image, ImageDraw, ImageFont
        import numpy as np

        # Crear imagen transparente
        img = Image.new("RGBA", (target_w, 200), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Intentar cargar fuente personalizada
        try:
            if Path(self.font_path).exists():
                font = ImageFont.truetype(self.font_path, font_size)
            else:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()

        # Sombra del texto
        for dx, dy in [(-2,-2), (2,-2), (-2,2), (2,2), (3,3)]:
            draw.text((target_w//2 + dx, 80 + dy), text, font=font, fill=(0,0,0,200), anchor="mm")

        # Texto principal
        draw.text((target_w//2, 80), text, font=font, fill=(255,255,255,255), anchor="mm")

        # Convertir a numpy
        frame = np.array(img)

        # Crear clip
        clip = ImageClip(frame, duration=duration, ismask=False)
        clip = clip.set_position(("center", target_h * 0.68))
        return clip

    def _create_simple_subtitle(
        self, script: str, duration: float, target_w: int, target_h: int
    ) -> list:
        """Crea subtítulos simples dividiendo el guion por tiempo."""
        words = script.split()
        if not words:
            return []

        words_per_second = len(words) / duration
        chunk_size = max(6, int(words_per_second * 4))  # Chunks de ~4 segundos
        chunks = [" ".join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size)]

        clips = []
        chunk_duration = duration / len(chunks)

        for i, chunk in enumerate(chunks):
            start = i * chunk_duration
            try:
                txt = self._make_text_clip(chunk, chunk_duration * 0.9, target_w, target_h)
                if txt:
                    clips.append(txt.set_start(start))
            except Exception:
                pass

        return clips

    # ─── Watermark / Branding ─────────────────────────────────
    def _create_watermark(
        self, channel_name: str, target_w: int, target_h: int, duration: float
    ):
        """Crea un watermark sutil con el nombre del canal."""
        try:
            from PIL import Image, ImageDraw, ImageFont
            from moviepy.editor import ImageClip
            import numpy as np

            # Imagen pequeña con el nombre del canal
            img = Image.new("RGBA", (300, 50), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            try:
                font = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22
                )
            except Exception:
                font = ImageFont.load_default()

            # Sombra + texto
            draw.text((11, 11), f"@{channel_name}", font=font, fill=(0,0,0,128))
            draw.text((10, 10), f"@{channel_name}", font=font, fill=(255,255,255,180))

            frame = np.array(img)
            clip = ImageClip(frame, duration=duration, ismask=False)
            clip = clip.set_position((20, 50))
            return clip

        except Exception as e:
            logger.debug(f"Watermark error: {e}")
            return None

    # ─── Fondo de color ───────────────────────────────────────
    def _create_color_background(
        self, duration: float, target_w: int, target_h: int, color=(10, 10, 30)
    ):
        """Crea un fondo de color sólido como fallback."""
        from moviepy.editor import ColorClip
        clip = ColorClip(size=(target_w, target_h), color=color, duration=duration)
        return clip

    # ─── Utilitarios ──────────────────────────────────────────
    def _wrap_text(self, text: str, max_chars: int = 40) -> list:
        """Divide texto en líneas de máximo max_chars caracteres."""
        words = text.split()
        lines = []
        current = ""

        for word in words:
            if len(current) + len(word) + 1 <= max_chars:
                current = f"{current} {word}".strip()
            else:
                if current:
                    lines.append(current)
                current = word

        if current:
            lines.append(current)

        return lines

    def get_video_info(self, video_path: str) -> dict:
        """Obtiene información del video usando ffprobe."""
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-print_format", "json",
                 "-show_format", "-show_streams", video_path],
                capture_output=True, text=True
            )
            import json
            data = json.loads(result.stdout)
            video_stream = next(
                (s for s in data.get("streams", []) if s.get("codec_type") == "video"),
                {}
            )
            return {
                "duration": float(data.get("format", {}).get("duration", 0)),
                "size_mb": int(data.get("format", {}).get("size", 0)) / (1024*1024),
                "width": video_stream.get("width", 0),
                "height": video_stream.get("height", 0),
                "fps": eval(video_stream.get("avg_frame_rate", "30/1")),
            }
        except Exception as e:
            logger.error(f"Error obteniendo info del video: {e}")
            return {}
