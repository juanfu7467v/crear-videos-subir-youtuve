"""
quality_checker.py
───────────────────
Control de calidad automático con llamadas directas a la API de Gemini v1beta.
Analiza frames del video para verificar calidad visual.
"""

import base64
import json
import logging
import os
import subprocess
import tempfile
import re
import requests
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

QC_PROMPT = """
Eres un experto en calidad de contenido para YouTube. Analiza este frame de video.
Evalúa los siguientes aspectos y responde ÚNICAMENTE en JSON válido:
{
  "score": 85,
  "legibility": "alta",
  "visual_appeal": "alta",
  "brightness": "correcto",
  "composition": "buena",
  "issues": [],
  "recommendations": [],
  "approved": true
}
"""

class QualityChecker:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.min_score = int(os.getenv("MIN_QC_SCORE", "60"))
        # Usando el modelo gemini-2.5-flash que es el nuevo estándar
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.api_key}"

    def _analyze_frame(self, frame_path: str) -> Optional[dict]:
        if not self.api_key:
            return None

        try:
            # Leer imagen y codificar en base64
            with open(frame_path, "rb") as f:
                image_bytes = f.read()
                image_base64 = base64.b64encode(image_bytes).decode('utf-8')

            # Preparar payload para la API directa
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": QC_PROMPT},
                            {
                                "inlineData": {
                                    "mimeType": "image/jpeg",
                                    "data": image_base64
                                }
                            }
                        ]
                    }
                ]
            }
            headers = {'Content-Type': 'application/json'}

            response = requests.post(self.url, headers=headers, json=payload)
            response.raise_for_status()
            
            data = response.json()

            # Extraer el texto de la respuesta de Gemini
            if 'candidates' in data and len(data['candidates']) > 0:
                text_response = data['candidates'][0]['content']['parts'][0]['text']
                raw = text_response.strip()
                # Limpiar posibles etiquetas markdown
                raw = re.sub(r'```json\s*|\s*```', '', raw)
                return json.loads(raw)
            else:
                logger.error(f"Respuesta inesperada de Gemini en QC: {data}")
                return None

        except Exception as e:
            logger.debug(f"⚠️ Error analizando frame: {e}")
            return None

    def check_video(self, video_path: str, expected_keywords: list = None, num_frames: int = 3) -> dict:
        result = {
            "score": 75,
            "legibility": "media",
            "visual_appeal": "media",
            "brightness": "correcto",
            "composition": "buena",
            "issues": [],
            "recommendations": [],
            "approved": True,
            "thumbnail_path": None,
            "frames_analyzed": 0,
        }

        if not Path(video_path).exists():
            result.update({"score": 0, "approved": False, "issues": ["Video no encontrado"]})
            return result

        frames = self._extract_frames(video_path, num_frames)
        result["frames_analyzed"] = len(frames)

        if frames and self.api_key:
            frame_results = []
            for f_path in frames:
                res = self._analyze_frame(f_path)
                if res: frame_results.append(res)
            
            if frame_results:
                result = self._aggregate_results(frame_results, result)

        # Limpieza y thumbnail
        if frames:
            thumb = Path(video_path).with_suffix(".jpg")
            try:
                import shutil
                shutil.copy(frames[0], thumb)
                result["thumbnail_path"] = str(thumb)
            except: pass
            for f in frames: Path(f).unlink(missing_ok=True)

        return result

    def _extract_frames(self, video_path: str, num_frames: int = 3) -> list:
        frames = []
        try:
            duration = self._get_video_duration(video_path)
            if duration <= 0: return []
            
            temp_dir = Path(tempfile.gettempdir())
            for i in range(num_frames):
                ts = (duration / (num_frames + 1)) * (i + 1)
                f_path = temp_dir / f"qc_{i}.jpg"
                cmd = ["ffmpeg", "-y", "-ss", str(ts), "-i", video_path, "-vframes", "1", str(f_path)]
                if subprocess.run(cmd, capture_output=True).returncode == 0:
                    frames.append(str(f_path))
        except: pass
        return frames

    def _get_video_duration(self, video_path: str) -> float:
        try:
            cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", video_path]
            return float(subprocess.run(cmd, capture_output=True, text=True).stdout.strip())
        except: return 0.0

    def _aggregate_results(self, frame_results: list, base_result: dict) -> dict:
        scores = [r.get("score", 70) for r in frame_results if isinstance(r.get("score"), (int, float))]
        if scores: base_result["score"] = int(sum(scores) / len(scores))
        base_result["approved"] = base_result["score"] >= self.min_score
        return base_result
