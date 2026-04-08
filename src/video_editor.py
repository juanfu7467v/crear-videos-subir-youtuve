import logging
import os
import random
from pathlib import Path
from PIL import Image
import numpy as np

# PARCHE: Esto obliga a que MoviePy encuentre la propiedad que busca
Image.ANTIALIAS = Image.Resampling.LANCZOS 

from moviepy.editor import (
    VideoFileClip, ImageClip, AudioFileClip, concatenate_videoclips, 
    CompositeVideoClip, TextClip, afx, vfx
)

logger = logging.getLogger(__name__)

class VideoEditor:
    def __init__(self):
        logger.info("Inicializando VideoEditor...")

    def create_video(self, audio_path, media_list, script_data, format_type, output_path, music_dir="assets/music"):
        # 1. Cargar Audio Principal (TTS) para determinar duración
        tts_audio = AudioFileClip(audio_path)
        duration = float(tts_audio.duration)

        is_short = "short" in str(format_type).lower() if format_type else (duration <= 60.0)
        
        # MEJORA 1: Si es Short, forzar duración a exactamente 60s
        if is_short:
            logger.info(f"Forzando duración de Short a 60.0s (Audio original: {duration:.2f}s)")
            duration = 60.0

        target_h = 1920 if is_short else 1080
        target_w = 1080 if is_short else 1920
        
        logger.info(f"Formato detectado: {'Short (9:16)' if is_short else 'Largo (16:9)'} - Duración final: {duration:.2f}s")
        
        # 2. Preparar Clips Visuales
        clips = []
        current_time = 0.0
        for i, item in enumerate(media_list):
            path_str = str(item.get("path", ""))
            if not path_str or not Path(path_str).exists():
                logger.warning(f"Clip {i} no encontrado o ruta vacía: {path_str}")
                continue
            
            if os.path.getsize(path_str) == 0:
                logger.warning(f"Clip {i} tiene 0 bytes, saltando: {path_str}")
                continue
            
            item_type = str(item.get("type", "video"))
            source = str(item.get("source", ""))
            
            try:
                try:
                    clip_duration = float(item.get("segment_duration", 5.0))
                except (TypeError, ValueError):
                    clip_duration = 5.0

                if item_type == "video":
                    try:
                        # OPTIMIZACIÓN: Cargar solo el fragmento necesario y sin audio
                        # target_resolution ayuda a reducir la carga de RAM al decodificar
                        raw_clip = VideoFileClip(path_str, audio=False, target_resolution=(target_h, target_w))
                    except Exception as ve:
                        logger.warning(f"Video corrupto detectado ({path_str}): {ve}")
                        continue
                    
                    raw_duration = float(raw_clip.duration)
                    if raw_duration < clip_duration:
                        clip = raw_clip.loop(duration=clip_duration)
                    else:
                        # Si el clip es más largo que lo que necesitamos (segment_duration), cortarlo
                        safe_end = min(raw_duration - 0.1, clip_duration)
                        clip = raw_clip.subclip(0, safe_end).set_duration(clip_duration)
                    
                    if "youtube" in source or "kinocheck" in source:
                        if random.random() > 0.5:
                            clip = clip.fx(vfx.mirror_x)
                        clip = clip.fx(vfx.resize, 1.1)
                else:
                    clip = ImageClip(path_str).set_duration(float(clip_duration))
                    clip = clip.fx(vfx.resize, lambda t: 1 + 0.02*t)
                
                # MEJORAS VISUALES: Nitidez, Brillo y Contraste
                clip = clip.fx(vfx.lum_contrast, lum=12, contrast=0.1) # Simula brillo 0.05 y contraste 1.1
                
                # Redimensionar según formato
                if is_short:
                    # TÉCNICA: Fondo desenfocado para Shorts
                    bg = clip.resize(height=target_h)
                    if bg.w < target_w:
                        bg = bg.resize(width=target_w)
                    
                    bg = bg.crop(x_center=bg.w/2, y_center=bg.h/2, width=target_w, height=target_h)
                    
                    from PIL import ImageFilter as pil_filters
                    def apply_blur(image):
                        pil_img = Image.fromarray(image.astype('uint8'))
                        pil_img = pil_img.filter(pil_filters.GaussianBlur(radius=15))
                        return np.array(pil_img)
                    
                    # OPTIMIZACIÓN EXTREMA (Mejora 3): Reducir resolución del fondo drásticamente para ahorrar RAM
                    # Un radio de 15 en una imagen pequeña da el mismo efecto visual que en una grande pero con 1/16 del costo de memoria
                    small_h = 360 # Resolución muy baja para el fondo desenfocado
                    small_w = int(target_w * (small_h / target_h))
                    
                    bg = bg.resize(height=small_h)
                    bg = bg.fl_image(apply_blur)
                    bg = bg.resize(height=target_h) # Reescalar a 1080x1920 (el blur oculta el pixelado)
                    bg = bg.fx(vfx.colorx, 0.7) # Oscurecer un poco el fondo
                    
                    fg = clip.resize(width=target_w)
                    if fg.h > target_h:
                        fg = fg.resize(height=target_h)
                    
                    # Usar use_bgclip=True en CompositeVideoClip para optimizar memoria si el primer clip es el fondo
                    clip = CompositeVideoClip([bg, fg.set_position("center")], size=(target_w, target_h), use_bgclip=True)
                else:
                    # OPTIMIZACIÓN (Mejora 3): Para videos largos, usar redimensionamiento simple sin margen si es posible
                    clip = clip.resize(height=target_h)
                    if clip.w > target_w:
                        clip = clip.crop(x_center=clip.w/2, y_center=clip.h/2, width=target_w, height=target_h)
                    elif clip.w < target_w:
                        # Si es más estrecho, reescalar al ancho para evitar el costoso .margin() en CPU
                        clip = clip.resize(width=target_w)
                        if clip.h > target_h:
                            clip = clip.crop(y_center=clip.h/2, height=target_h)
                
                clip = clip.set_start(current_time)
                clips.append(clip)
                current_time += clip_duration
                if current_time >= duration: break
            except Exception as e:
                logger.warning(f"Error procesando clip {path_str}: {e}")
                continue
            
        if not clips:
            logger.error("No se pudieron cargar clips visuales válidos.")
            raise Exception("No visual clips available")

        total_clips_duration = sum(c.duration for c in clips)
        if total_clips_duration < duration:
            logger.info(f"Clips insuficientes ({total_clips_duration:.2f}s < {duration:.2f}s). Repitiendo clips...")
            original_clips = clips.copy()
            while total_clips_duration < duration:
                shuffled_clips = original_clips.copy()
                random.shuffle(shuffled_clips)
                for c in shuffled_clips:
                    new_c = c.copy().set_start(total_clips_duration)
                    if random.random() > 0.5:
                        new_c = new_c.fx(vfx.mirror_x)
                    clips.append(new_c)
                    total_clips_duration += c.duration
                    if total_clips_duration >= duration:
                        break

        visual_base = concatenate_videoclips(clips, method="chain")
        visual_base = visual_base.set_duration(duration)
        
        # 3. Añadir Música de Fondo
        # Asegurar que el audio TTS dure lo mismo que el video si es Short
        if is_short and float(tts_audio.duration) < duration:
            # Rellenar con silencio si el audio es más corto para llegar a 60s
            from moviepy.audio.AudioClip import AudioArrayClip
            import numpy as np
            silence_duration = duration - float(tts_audio.duration)
            silence = AudioArrayClip(np.zeros((int(44100 * silence_duration), 2)), fps=44100)
            from moviepy.audio.AudioClip import concatenate_audioclips
            tts_audio_padded = concatenate_audioclips([tts_audio, silence])
        else:
            tts_audio_padded = tts_audio.set_duration(duration)

        final_audio = tts_audio_padded
        try:
            music_files = list(Path(music_dir).glob("*.mp3"))
            if music_files:
                bg_music_path = random.choice(music_files)
                logger.info(f"Añadiendo música de fondo: {bg_music_path.name}")
                bg_music = AudioFileClip(str(bg_music_path))
                bg_music = bg_music.volumex(0.15)
                if float(bg_music.duration) < duration:
                    bg_music = afx.audio_loop(bg_music, duration=duration)
                else:
                    bg_music = bg_music.set_duration(duration)
                
                from moviepy.audio.AudioClip import CompositeAudioClip
                final_audio = CompositeAudioClip([tts_audio_padded, bg_music])
        except Exception as e:
            logger.error(f"Error al añadir música de fondo: {e}")

        # 4. Añadir Subtítulos (Estilo mejorado basado en video de referencia)
        full_script = str(script_data.get('full_script', ''))
        subtitles = []
        import re
        # Dividir por frases más cortas para que el efecto "pop" sea más dinámico
        raw_sentences = re.split(r'[.,!?\n]', full_script)
        sentences = [s.strip() for s in raw_sentences if s.strip()]
        
        final_sentences = []
        for s in sentences:
            # Acortar frases para que quepan bien con el recuadro de fondo
            while len(s) > 40:
                split_idx = s[:40].rfind(' ')
                if split_idx == -1: split_idx = 40
                final_sentences.append(s[:split_idx].strip())
                s = s[split_idx:].strip()
            if s: final_sentences.append(s)

        if final_sentences:
            time_per_sentence = float(duration) / len(final_sentences)
            for i, sentence in enumerate(final_sentences):
                try:
                    # Estilo basado en el video de referencia:
                    # - Fuente Sans-Serif Bold (Liberation-Sans-Bold)
                    # - Color blanco
                    # - Recuadro de fondo negro sólido (bg_color='black')
                    # - Posición centrada en el tercio inferior
                    # - Efecto "pop" (zoom in)
                    
                    fs = 100 if is_short else 70
                    start_t = float(i * time_per_sentence)
                    end_t = start_t + float(time_per_sentence)
                    
                    txt_clip = TextClip(
                        sentence, 
                        fontsize=fs, 
                        color='white',
                        font='Liberation-Sans-Bold',
                        method='caption',
                        size=(target_w * 0.8, None),
                        align='center',
                        bg_color='black'
                    ).set_start(start_t).set_duration(float(time_per_sentence)).set_position(('center', target_h * 0.75))
                    
                    # Animación "Pop" (ligero zoom al aparecer)
                    # El clip empieza un poco más pequeño y crece rápidamente al tamaño normal
                    def zoom_effect(t):
                        # t es el tiempo relativo al inicio del clip
                        if t < 0.1:
                            return 0.8 + 2 * t # De 0.8 a 1.0 en 0.1 segundos
                        return 1.0
                    
                    txt_clip = txt_clip.fx(vfx.resize, zoom_effect)
                    
                    subtitles.append(txt_clip)
                except Exception as e:
                    logger.warning(f"No se pudo crear subtítulo: {e}")

        # 5. Componer Video Final
        final_video = CompositeVideoClip([visual_base] + subtitles, size=(target_w, target_h)).set_audio(final_audio)
        final_video = final_video.set_duration(duration)
        
        logger.info(f"Renderizando video final en {output_path}...")
        
        ffmpeg_params = [
            "-crf", "18", 
            "-tune", "film",
            "-b:v", "5M", 
            "-maxrate", "8M",
            "-bufsize", "10M"
        ]
        
        # OPTIMIZACIÓN EXTREMA (Mejora 3): Renderizado por fragmentos para evitar OOM
        # MoviePy a veces acumula memoria en videos largos. Usamos threads=1 para máxima estabilidad de RAM.
        final_video.write_videofile(
            str(output_path), 
            fps=24, 
            codec="libx264", 
            audio_codec="aac", 
            logger=None, 
            preset="ultrafast", 
            threads=1, # Un solo hilo consume mucha menos RAM en MoviePy
            ffmpeg_params=ffmpeg_params,
            bitrate="3000k" # Limitar bitrate para reducir presión de buffer
        )
        
        final_video.close()
        visual_base.close()
        for c in clips:
            try: c.close()
            except: pass
        tts_audio.close()
        if 'tts_audio_padded' in locals():
            try: tts_audio_padded.close()
            except: pass
        if 'bg_music' in locals(): 
            try: bg_music.close()
            except: pass

        # LIMPIEZA INMEDIATA (Mejora 2): Borrar clips descargados tras el render
        logger.info("🧹 Limpiando clips temporales procesados...")
        for item in media_list:
            p = item.get("path")
            if p and Path(p).exists():
                try:
                    Path(p).unlink()
                    logger.debug(f"Eliminado: {p}")
                except Exception as e:
                    logger.warning(f"No se pudo eliminar {p}: {e}")
        
        return output_path
