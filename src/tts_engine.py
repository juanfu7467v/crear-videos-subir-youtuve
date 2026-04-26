import asyncio
import logging
import os
import subprocess
import random
import json
from pathlib import Path
import edge_tts
import re

logger = logging.getLogger(__name__)

AVAILABLE_VOICES = {
    "mx_female": "es-MX-DaliaNeural",
    "mx_male":   "es-MX-JorgeNeural",
    "mx_male_2": "es-MX-EmilioNeural",
}

class TTSEngine:
    def __init__(self):
        self.default_voice = os.getenv("DEFAULT_VOICE", "es-MX-JorgeNeural")
        self.default_rate  = os.getenv("DEFAULT_SPEECH_RATE", "+10%")
        self.default_pitch = os.getenv("DEFAULT_PITCH", "+0Hz")
        self.voices_list = ["es-MX-DaliaNeural", "es-MX-EmilioNeural", "es-MX-JorgeNeural"]

    def _get_valid_voice(self, voice_input: str) -> str:
        if voice_input == "random":
            return random.choice(self.voices_list)
        if voice_input in self.voices_list: return voice_input
        if voice_input in AVAILABLE_VOICES.values(): return voice_input
        mapped = AVAILABLE_VOICES.get(voice_input)
        if mapped: return mapped
        return self.default_voice

    async def _generate_with_timestamps(self, text: str, voice: str, output_path: str, rate: str, pitch: str):
        # Aseguramos que el texto esté limpio para evitar que se lean etiquetas SSML
        clean_text = self._clean_text(text)
        
        try:
            # NO USAR SSML MANUAL: Usar parámetros nativos de edge_tts
            # Esto evita que el motor lea etiquetas <speak> por errores de sintaxis
            communicate = edge_tts.Communicate(clean_text, voice, rate=rate, pitch=pitch)
            logger.info(f"Generando audio nativo (Voz: {voice}, Rate: {rate}, Pitch: {pitch})")
            
            word_timestamps = []
            sentence_boundaries = []
            
            with open(output_path, "wb") as f:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        f.write(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        word_timestamps.append({
                            "word": chunk["text"],
                            "start": chunk["offset"] / 10**7, 
                            "duration": chunk["duration"] / 10**7
                        })
                    elif chunk["type"] == "SentenceBoundary":
                        sentence_boundaries.append({
                            "text": chunk["text"],
                            "start": chunk["offset"] / 10**7,
                            "duration": chunk["duration"] / 10**7
                        })
        except Exception as e:
            logger.error(f"Error generando audio con timestamps: {e}")
            # Fallback simple
            communicate = edge_tts.Communicate(clean_text, voice, rate=rate, pitch=pitch)
            await communicate.save(output_path)
            word_timestamps = []
            sentence_boundaries = []
        
        if not word_timestamps and sentence_boundaries:
            logger.info("⚠️ WordBoundaries no disponibles, interpolando desde SentenceBoundaries...")
            for sb in sentence_boundaries:
                words = sb["text"].split()
                if not words: continue
                
                total_chars = sum(len(w) for w in words)
                current_start = sb["start"]
                
                for word in words:
                    word_dur = (len(word) / total_chars) * sb["duration"] if total_chars > 0 else sb["duration"] / len(words)
                    word_timestamps.append({
                        "word": word,
                        "start": current_start,
                        "duration": max(0.05, word_dur)
                    })
                    current_start += word_dur
        
        json_path = output_path.replace(".mp3", ".json")
        if word_timestamps:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(word_timestamps, f, ensure_ascii=False, indent=2)
            logger.info(f"✅ Timestamps generados correctamente ({len(word_timestamps)} palabras): {json_path}")
        else:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump([], f)
            logger.warning(f"⚠️ No se pudieron generar timestamps para el audio. Archivo vacío creado: {json_path}")

    def generate_audio(self, text: str, output_path: str, voice: str = None, rate: str = None, pitch: str = None) -> str:
        voice = self._get_valid_voice(voice or "random")
        rate  = rate  or self.default_rate
        pitch = pitch or self.default_pitch

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Limpieza preventiva antes de cualquier proceso
        text = self._clean_text(text)
        text = text[:8000]
        
        logger.info(f"Generando TTS con timestamps para voz: {voice}")
        
        try:
            asyncio.run(self._generate_with_timestamps(text, voice, output_path, rate, pitch))
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                return output_path
        except Exception as e:
            logger.error(f"Error en Edge-TTS con timestamps: {e}")
            try:
                clean_text = self._clean_text(text)
                communicate = edge_tts.Communicate(clean_text, voice, rate=rate, pitch=pitch)
                asyncio.run(communicate.save(output_path))
            except Exception as e2:
                logger.error(f"Error crítico en fallback de TTS: {e2}")
            
        return output_path

    def get_audio_duration(self, audio_path: str) -> float:
        try:
            if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
                return 5.0
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", audio_path],
                capture_output=True, text=True
            )
            return float(result.stdout.strip())
        except:
            return 5.0

    def _apply_pronunciation_dictionary(self, text: str) -> str:
        corrections = {
            r"\bStallone\b": "Estalón",
            r"\bDavid Morrell\b": "Deivid Morrel",
            r"\bFirst Blood\b": "Ferst Blad",
            r"\bGoldsmith\b": "Goldsmit",
            r"\bRambo\b": "Rambo",
            r"\bSylvester\b": "Silvéster",
            r"\[Introducción cinematográfica\]": "",
            r"\[Capítulo \d+\]": "",
            r"\[Conclusión\]": "",
            r"\[Música.*?\]": "",
            r"\(Voz en off\)": "",
            r"\(Escena.*?\)": "",
        }
        
        for pattern, replacement in corrections.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        return text

    def _clean_text(self, text: str) -> str:
        if not text: return ""
        
        # 1. Si el texto es un JSON completo (a veces la IA lo envía así)
        if text.strip().startswith('{'):
            try:
                data = json.loads(text)
                text = data.get('full_script', text)
            except: pass
        
        # 2. ELIMINACIÓN AGRESIVA DE BASURA TÉCNICA (Lo que escuchamos en el video)
        # Eliminamos bloques completos de metadatos SSML que la IA pueda haber incluido
        # Esto busca patrones como 'speak version...', 'xmlns...', etc., y los elimina junto con sus valores
        technical_metadata_patterns = [
            r'(?i)speak\s+version\s*=\s*[\'"].*?[\'"]',
            r'(?i)xmlns\s*=\s*[\'"].*?[\'"]',
            r'(?i)xml:lang\s*=\s*[\'"].*?[\'"]',
            r'(?i)voice\s+name\s*=\s*[\'"].*?[\'"]',
            r'(?i)prosody\s+rate\s*=\s*[\'"].*?[\'"]',
            r'(?i)pitch\s*=\s*[\'"].*?[\'"]',
            r'(?i)version\s*=\s*[\'"]1\.0[\'"]',
            r'(?i)http://www\.w3\.org/2001/10/synthesis',
            r'(?i)jorgeNeural', r'(?i)daliaNeural', r'(?i)emilioNeural'
        ]
        for pattern in technical_metadata_patterns:
            text = re.sub(pattern, '', text)

        # 3. Eliminar etiquetas XML/SSML (ej: <speak>, <prosody>, etc.)
        text = re.sub(r'<[^>]*>', '', text)

        # 4. Eliminar cabeceras de la IA (Título:, Introducción:, [Música])
        headers = [
            r'(?im)^(Título|Guion|Script|Narrador|Voz en off|Introducción|Capítulo \d+|Conclusión|Escena \d+):\s*',
            r'\[.*?\]',  # Elimina todo lo que esté entre corchetes [Música]
            r'\(.*?\)'   # Elimina todo lo que esté entre paréntesis (Suspiros)
        ]
        for pattern in headers:
            text = re.sub(pattern, '', text)

        # 5. Limpieza de formato y caracteres raros
        text = text.replace('\\n', ' ').replace('\\"', '"').replace('*', '')
        
        # Limpieza de símbolos técnicos residuales pero manteniendo puntuación básica
        text = re.sub(r'[#@$%^&*={}\[\]<>|\\/_]', ' ', text)
        
        # Aplicar correcciones de pronunciación (Rambo, Stallone, etc.)
        text = self._apply_pronunciation_dictionary(text)
        
        # Normalizar espacios y puntos
        text = text.replace('...', '.')
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
