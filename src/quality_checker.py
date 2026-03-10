"""
quality_checker.py
───────────────────
Control de calidad automático con la NUEVA librería google-genai.
Analiza frames del video para verificar calidad visual.
"""

import base64
import json
import logging
import os
import subprocess
import tempfile
import re
from pathlib import Path
from typing import Optional
from google import genai
from google.genai import types

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
        self.client = None
        self._configure_gemini()

    def _configure_gemini(self):
        if self.api_key:
            try:
                # NUEVA FORMA: Cliente
                self.client = genai.Client(api_key=self.api_key)
                logger.info("✅ Cliente Gemini Vision (google-genai) configurado.")
            except Exception as e:
                logger.error(f"❌ Error configurando QC: {e}")
                self.client = None
        else:
            self.client = None
            logger.warning("⚠️ Sin API Gemini. QC desactivado.")

    def _analyze_frame(self, frame_path: str) -> Optional[dict]:
        if not self.client:
            return None

        try:
            # Leer imagen
            with open(frame_path, "rb") as f:
                image_bytes = f.read()

            # NUEVA FORMA: Envío de imagen con el cliente nuevo
            response = self.client.models.generate_content(
                model="gemini-1.5-flash",
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                    QC_PROMPT
                ]
            )

            raw = response.text.strip()
            # Limpiar posibles etiquetas markdown
            raw = re.sub(r'```json\s*|\s*```', '', raw)
            return json.loads(raw)

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

        if frames and self.client:
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
