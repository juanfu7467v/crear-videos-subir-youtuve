import json
import os
import logging

logger = logging.getLogger(__name__)

class ASSGenerator:
    def __init__(self):
        self.header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,100,&H00FFFFFF,&H0000FFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,10,5,2,50,50,450,1
Style: Karaoke,Arial,110,&H0000FFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,12,6,2,50,50,450,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    def format_time(self, seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours}:{minutes:02d}:{secs:05.2f}"

    def generate_ass(self, word_timestamps, output_path, start_offset=0.0):
        """
        Genera un archivo .ass con efecto de karaoke (resaltado de palabra actual).
        """
        if not word_timestamps:
            logger.warning("No hay timestamps para generar el archivo ASS.")
            return None

        events = []
        # Agrupar palabras en "líneas" o frases cortas para que no se vea una sola palabra
        # Para estilo Hormozi, a veces es mejor 1-3 palabras por línea.
        
        words_per_line = 3
        for i in range(0, len(word_timestamps), words_per_line):
            line_words = word_timestamps[i:i + words_per_line]
            if not line_words: continue
            
            line_start = line_words[0]["start"] + start_offset
            line_end = line_words[-1]["start"] + line_words[-1]["duration"] + start_offset
            
            # Construir el texto con efectos de karaoke
            # Estilo: {\k<duración>}Texto
            # La duración en \k es en centisegundos (1/100s)
            
            ass_text = ""
            current_time = line_start
            
            for word_data in line_words:
                word = word_data["word"].upper()
                # Duración de la palabra en centisegundos
                dur_cs = int(word_data["duration"] * 100)
                
                # Efecto: La palabra actual resalta
                # Usamos \k para el tiempo de karaoke y \c para cambiar color (Hormozi style)
                # Amarillo para la palabra activa, blanco para el resto
                ass_text += f"{{\\k{dur_cs}}}{word} "
            
            start_str = self.format_time(line_start)
            end_str = self.format_time(line_end)
            
            # Añadir la línea al archivo
            events.append(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{ass_text.strip()}")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(self.header)
            f.write("\n".join(events))
        
        logger.info(f"Archivo ASS generado: {output_path}")
        return output_path
