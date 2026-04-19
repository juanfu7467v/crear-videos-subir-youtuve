import logging
import os
import random
import re
from pathlib import Path
from PIL import Image, ImageFilter as pil_filters
import numpy as np
from src.utils import validate_video, cleanup_ffmpeg

# PARCHE: Esto obliga a que MoviePy encuentre la propiedad que busca
if not hasattr(Image, 'ANTIALIAS'):
    try:
        from PIL import Image
        Image.ANTIALIAS = Image.Resampling.LANCZOS
    except Exception:
        pass

from moviepy.editor import (
    VideoFileClip, ImageClip, AudioFileClip, concatenate_videoclips, 
    CompositeVideoClip, TextClip, afx, vfx
)
from moviepy.audio.AudioClip import AudioArrayClip, concatenate_audioclips, CompositeAudioClip

logger = logging.getLogger(__name__)

def apply_blur(image):
    """Función auxiliar global para evitar errores de variable libre 'np' en cierres."""
    pil_img = Image.fromarray(image.astype('uint8'))
    pil_img = pil_img.filter(pil_filters.GaussianBlur(radius=15))
    return np.array(pil_img)

class VideoEditor:
    def __init__(self):
        logger.info("Inicializando VideoEditor...")

    def create_video(self, audio_path, media_list, script_data, format_type, output_path, music_dir="assets/music", thumbnail_path=None):
        # 1. Cargar Audio Principal (TTS) para determinar duración
        tts_audio = AudioFileClip(audio_path)
        duration = float(tts_audio.duration)

        is_short = "short" in str(format_type).lower() if format_type else (duration <= 60.0)
        
        # MEJORA 1: Si es Short, forzar duración a exactamente 60s
        if is_short:
            logger.info(f"Forzando duración de Short a 60.0s (Audio original: {duration:.2f}s)")
            duration = 60.0
        else:
            logger.info(f"Manteniendo duración de video largo en {duration:.2f}s")

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
            
            if not validate_video(path_str) and item.get("type", "video") == "video":
                logger.warning(f"Clip {i} no es un video válido, saltando: {path_str}")
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
                        raw_clip = VideoFileClip(path_str, audio=False, target_resolution=(target_h, target_w))
                    except Exception as ve:
                        logger.warning(f"Video corrupto detectado por MoviePy ({path_str}): {ve}")
                        try:
                            clip = ImageClip(path_str).set_duration(float(clip_duration))
                            logger.info(f"Clip {i} cargado como imagen estática tras fallo de video.")
                        except:
                            continue
                    
                    raw_duration = float(raw_clip.duration)
                    if raw_duration < clip_duration:
                        clip = raw_clip.loop(duration=clip_duration)
                    else:
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
                clip = clip.fx(vfx.lum_contrast, lum=12, contrast=0.1)
                
                # Redimensionar según formato
                if is_short:
                    bg = clip.resize(height=target_h)
                    if bg.w < target_w:
                        bg = bg.resize(width=target_w)
                    
                    bg = bg.crop(x_center=bg.w/2, y_center=bg.h/2, width=target_w, height=target_h)
                    
                    small_h = 360
                    small_w = int(target_w * (small_h / target_h))
                    
                    bg = bg.resize(height=small_h)
                    bg = bg.fl_image(apply_blur)
                    bg = bg.resize(height=target_h)
                    bg = bg.fx(vfx.colorx, 0.7)
                    
                    fg = clip.resize(width=target_w)
                    if fg.h > target_h:
                        fg = fg.resize(height=target_h)
                    
                    clip = CompositeVideoClip([bg, fg.set_position("center")], size=(target_w, target_h), use_bgclip=True)
                else:
                    clip = clip.resize(height=target_h)
                    if clip.w > target_w:
                        clip = clip.crop(x_center=clip.w/2, y_center=clip.h/2, width=target_w, height=target_h)
                    elif clip.w < target_w:
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
        
        # MEJORA: Insertar miniatura en el primer segundo para Shorts
        if is_short and thumbnail_path and os.path.exists(thumbnail_path):
            logger.info(f"Insertando miniatura en el primer segundo del Short: {thumbnail_path}")
            thumb_clip = ImageClip(thumbnail_path).set_duration(1.0).set_start(0).resize(height=target_h)
            if thumb_clip.w < target_w:
                thumb_clip = thumb_clip.resize(width=target_w)
            thumb_clip = thumb_clip.crop(x_center=thumb_clip.w/2, y_center=thumb_clip.h/2, width=target_w, height=target_h)
            
            # Desplazar el resto del video 1 segundo
            visual_base = visual_base.set_start(1.0)
            visual_base = CompositeVideoClip([thumb_clip, visual_base], size=(target_w, target_h))
            duration += 1.0 # Aumentar duración total por el segundo de miniatura
        
        visual_base = visual_base.set_duration(duration)
        
        # 3. Añadir Música de Fondo
        if is_short and float(tts_audio.duration) < duration:
            silence_duration = duration - float(tts_audio.duration)
            silence = AudioArrayClip(np.zeros((int(44100 * silence_duration), 2)), fps=44100)
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
                
                final_audio = CompositeAudioClip([tts_audio_padded, bg_music])
        except Exception as e:
            logger.error(f"Error al añadir música de fondo: {e}")

        # 4. Añadir Subtítulos Dinámicos (Estilo Alex Hormozi / Viral)
        segmented_script = script_data.get('segmented_script', [])
        subtitles = []
        
        # Fuente personalizada
        font_path = "assets/fonts/bold.ttf"
        if not os.path.exists(font_path):
            font_path = 'Liberation-Sans-Bold'

        # Ajustes de posición y tamaño (Hormozi style: Centro o ligeramente arriba del centro)
        # Para Shorts: Centro del video (y=0.5)
        # Para Largo: Parte inferior (y=0.8)
        y_pos = target_h * 0.5 if is_short else target_h * 0.8
        font_size = 110 if is_short else 80

        # Palabras clave para resaltar (Hormozi style usa mucho amarillo/verde/rojo)
        keywords_high = ["increíble", "espectacular", "misterio", "secreto", "poder", "dinero", "éxito", "letal", "peligro", "prohibido"]
        
        # MEJORA: Los subtítulos deben empezar después de la miniatura en Shorts
        current_time_sub = 1.0 if (is_short and thumbnail_path and os.path.exists(thumbnail_path)) else 0.0
        
        # Si no hay segmented_script, usamos el full_script como fallback
        if not segmented_script:
            full_text = str(script_data.get('full_script', ''))
            words = full_text.split()
            avg_word_duration = duration / max(len(words), 1)
            # Agrupar en bloques de 1-2 palabras para estilo Hormozi
            temp_segments = []
            for i in range(0, len(words), 2):
                block = " ".join(words[i:i+2])
                temp_segments.append({'segment_text': block, 'estimated_duration': avg_word_duration * 2})
            segmented_script = temp_segments

        for i, segment in enumerate(segmented_script):
            try:
                text = segment.get('segment_text', '').upper().strip()
                if not text: continue
                
                try:
                    seg_duration = float(segment.get('estimated_duration', 2.0))
                except:
                    seg_duration = 2.0
                
                # Asegurar que no nos pasamos de la duración total
                if current_time_sub + seg_duration > duration:
                    seg_duration = max(0.1, duration - current_time_sub)
                
                # Dividir segmentos largos en palabras individuales para mayor dinamismo (Alex Hormozi style)
                seg_words = text.split()
                word_duration = seg_duration / max(len(seg_words), 1)
                
                for j, word in enumerate(seg_words):
                    word_start = current_time_sub + (j * word_duration)
                    
                    # Colores vibrantes estilo Hormozi
                    is_special = any(kw.upper() in word for kw in keywords_high)
                    color = 'yellow' if is_special else ('white' if j % 2 == 0 else '#00FF00') # Blanco y Verde neón
                    
                    txt_clip = TextClip(
                        word,
                        fontsize=font_size + (20 if is_special else 0), 
                        color=color,
                        font=font_path,
                        method='caption',
                        size=(target_w * 0.9, None),
                        align='center',
                        stroke_color='black',
                        stroke_width=3
                    ).set_start(word_start).set_duration(word_duration).set_position(('center', y_pos))
                    
                    # --- ANIMACIONES VIRALES (Alex Hormozi Style) ---
                    # 1. Pop In con rotación ligera aleatoria
                    angle = random.uniform(-3, 3)
                    txt_clip = txt_clip.rotate(angle)
                    
                    # 2. Efecto de Escala (Zoom enérgico al aparecer)
                    def scale_anim(t):
                        # Aparece de 0.5 a 1.2 en 0.1s, luego se estabiliza en 1.0
                        if t < 0.07:
                            return 0.5 + (0.7 * (t / 0.07))
                        elif t < 0.12:
                            return 1.2 - (0.2 * ((t - 0.07) / 0.05))
                        else:
                            # Sutil movimiento de pulso si el locutor habla lento
                            return 1.0 + 0.02 * np.sin(t * 10)
                            
                    txt_clip = txt_clip.fx(vfx.resize, scale_anim)
                    
                    subtitles.append(txt_clip)
                
                current_time_sub += seg_duration
                if current_time_sub >= duration: break
                
            except Exception as e:
                logger.warning(f"Error creando subtítulo dinámico {i}: {e}")

        # 5. Composición Final
        final_video = CompositeVideoClip([visual_base] + subtitles, size=(target_w, target_h))
        final_video = final_video.set_audio(final_audio)
        
        # 6. Renderizado Optimizado
        try:
            final_video.write_videofile(
                output_path, 
                fps=24, 
                codec="libx264", 
                audio_codec="aac", 
                threads=4, 
                preset="ultrafast",
                logger=None
            )
        finally:
            logger.info("Limpiando recursos de MoviePy y FFMPEG...")
            try:
                tts_audio.close()
                final_video.close()
                visual_base.close()
                for c in clips:
                    try:
                        c.close()
                    except:
                        pass
                cleanup_ffmpeg()
            except Exception as ce:
                logger.warning(f"Error durante la limpieza de recursos: {ce}")
        
        return output_path
