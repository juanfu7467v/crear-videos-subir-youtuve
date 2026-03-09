"""
quality_checker.py
───────────────────
Control de calidad automático con Gemini Vision.
Analiza frames del video para verificar calidad visual.
"""

import base64
import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional
import google.generativeai as genai

logger = logging.getLogger(__name__)


QC_PROMPT = """
Eres un experto en calidad de contenido para YouTube. Analiza este frame de video.

Evalúa los siguientes aspectos (responde en JSON):

{
  "score": número del 0 al 100 (calidad general),
  "legibility": "alta/media/baja" (si el texto es legible),
  "visual_appeal": "alta/media/baja" (atractivo visual),
  "brightness": "correcto/oscuro/sobreexpuesto",
  "composition": "buena/regular/mala",
  "issues": ["lista de problemas encontrados"],
  "recommendations": ["lista de mejoras sugeridas"],
  "approved": true o false (si aprueba para publicar)
}

Sé objetivo y estricto. El video es para YouTube en español.
Responde SOLO con JSON válido, sin markdown.
"""


class QualityChecker:
    """
    Verifica la calidad del video antes de publicar.
    Usa Gemini Vision para análisis visual inteligente.
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.min_score = int(os.getenv("MIN_QC_SCORE", "60"))
        self._configure_gemini()

    def _configure_gemini(self):
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel("gemini-1.5-flash")
        else:
            self.model = None
            logger.warning("Sin API Gemini. QC desactivado.")

    def check_video(
        self,
        video_path: str,
        expected_keywords: list = None,
        num_frames: int = 3,
    ) -> dict:
        """
        Realiza QC completo del video.

        Args:
            video_path: Ruta al video a analizar
            expected_keywords: Keywords que deben aparecer visualmente
            num_frames: Número de frames a analizar

        Returns:
            Dict con resultado del QC
        """
        result = {
            "score": 75,  # Score por defecto si no hay API
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
            result["issues"].append("Archivo de video no encontrado")
            result["score"] = 0
            result["approved"] = False
            return result

        # Extraer frames para análisis
        frames = self._extract_frames(video_path, num_frames)
        result["frames_analyzed"] = len(frames)

        if not frames:
            logger.warning("No se pudieron extraer frames del video")
            return result

        # Guardar el primer frame como thumbnail
        if frames:
            thumbnail_path = str(Path(video_path).with_suffix("_thumb.jpg"))
            try:
                import shutil
                shutil.copy(frames[1] if len(frames) > 1 else frames[0], thumbnail_path)
                result["thumbnail_path"] = thumbnail_path
            except Exception:
                pass

        # Análisis con Gemini Vision
        if self.model:
            frame_results = []
            for frame_path in frames:
                frame_result = self._analyze_frame(frame_path)
                if frame_result:
                    frame_results.append(frame_result)

            if frame_results:
                result = self._aggregate_results(frame_results, result)

        # Limpieza de frames temporales
        for frame in frames:
            try:
                Path(frame).unlink(missing_ok=True)
            except Exception:
                pass

        # Verificación de duración
        duration = self._get_video_duration(video_path)
        if duration > 0:
            result["duration_seconds"] = duration
            if duration < 15:
                result["issues"].append(f"Video muy corto: {duration:.1f}s")
                result["score"] = max(0, result["score"] - 20)
            elif duration > 3600:
                result["issues"].append("Video muy largo (>1 hora)")
                result["score"] = max(0, result["score"] - 10)

        # Verificación de tamaño
        size_gb = Path(video_path).stat().st_size / (1024**3)
        if size_gb > 128:
            result["issues"].append(f"Archivo muy grande: {size_gb:.1f} GB (límite YouTube: 128GB)")
            result["score"] = max(0, result["score"] - 15)

        result["approved"] = result["score"] >= self.min_score
        logger.info(f"QC Score: {result['score']}/100 | {'✅ Aprobado' if result['approved'] else '⚠️ Con observaciones'}")

        return result

    def _extract_frames(self, video_path: str, num_frames: int = 3) -> list:
        """Extrae frames del video en momentos clave."""
        frames = []
        temp_dir = Path(tempfile.mkdtemp())

        try:
            # Obtener duración del video
            duration = self._get_video_duration(video_path)
            if duration <= 0:
                return frames

            # Momentos a capturar: inicio, medio, casi al final
            timestamps = []
            if num_frames == 1:
                timestamps = [duration * 0.3]
            elif num_frames == 2:
                timestamps = [duration * 0.2, duration * 0.7]
            else:
                timestamps = [
                    min(2.0, duration * 0.1),   # Cerca del inicio
                    duration * 0.4,              # Primer tercio
                    duration * 0.75,             # Tres cuartos
                ]

            for i, ts in enumerate(timestamps):
                frame_path = str(temp_dir / f"frame_{i:03d}.jpg")
                cmd = [
                    "ffmpeg", "-y",
                    "-ss", str(ts),
                    "-i", video_path,
                    "-vframes", "1",
                    "-q:v", "2",
                    frame_path
                ]
                result = subprocess.run(cmd, capture_output=True, timeout=30)
                if result.returncode == 0 and Path(frame_path).exists():
                    frames.append(frame_path)

        except Exception as e:
            logger.error(f"Error extrayendo frames: {e}")

        return frames

    def _analyze_frame(self, frame_path: str) -> Optional[dict]:
        """Analiza un frame con Gemini Vision."""
        if not self.model:
            return None

        try:
            # Leer y codificar imagen
            with open(frame_path, "rb") as f:
                image_data = f.read()

            image_b64 = base64.b64encode(image_data).decode("utf-8")

            response = self.model.generate_content([
                {"mime_type": "image/jpeg", "data": image_b64},
                QC_PROMPT,
            ])

            raw = response.text.strip().replace("```json", "").replace("```", "").strip()
            return json.loads(raw)

        except json.JSONDecodeError as e:
            logger.debug(f"Error parseando respuesta QC: {e}")
            return None
        except Exception as e:
            logger.debug(f"Error analizando frame: {e}")
            return None

    def _aggregate_results(self, frame_results: list, base_result: dict) -> dict:
        """Combina resultados de múltiples frames en un resultado final."""
        if not frame_results:
            return base_result

        # Promediar scores
        scores = [r.get("score", 70) for r in frame_results if isinstance(r.get("score"), (int, float))]
        if scores:
            base_result["score"] = int(sum(scores) / len(scores))

        # Tomar el peor caso para legibilidad y visual
        legibility_map = {"alta": 3, "media": 2, "baja": 1}
        legibilities = [r.get("legibility", "media") for r in frame_results]
        worst_leg = min(legibilities, key=lambda x: legibility_map.get(x, 2))
        base_result["legibility"] = worst_leg

        # Agregar todos los issues únicos
        all_issues = []
        all_recommendations = []
        for r in frame_results:
            all_issues.extend(r.get("issues", []))
            all_recommendations.extend(r.get("recommendations", []))

        base_result["issues"] = list(set(all_issues))[:5]
        base_result["recommendations"] = list(set(all_recommendations))[:5]

        # Visual appeal del mejor frame (para thumbnail)
        appeals = [r.get("visual_appeal", "media") for r in frame_results]
        appeal_map = {"alta": 3, "media": 2, "baja": 1}
        best_appeal = max(appeals, key=lambda x: appeal_map.get(x, 2))
        base_result["visual_appeal"] = best_appeal

        return base_result

    def _get_video_duration(self, video_path: str) -> float:
        """Obtiene la duración del video con ffprobe."""
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "csv=p=0", video_path],
                capture_output=True, text=True, timeout=15
            )
            return float(result.stdout.strip())
        except Exception:
            return 0.0

    def generate_qc_report(self, qc_result: dict, video_id: str) -> str:
        """Genera un reporte legible del QC."""
        lines = [
            f"═══ QC Report: {video_id} ═══",
            f"Score:        {qc_result.get('score', 'N/A')}/100",
            f"Aprobado:     {'✅ Sí' if qc_result.get('approved') else '⚠️ Con observaciones'}",
            f"Legibilidad:  {qc_result.get('legibility', 'N/A')}",
            f"Visual:       {qc_result.get('visual_appeal', 'N/A')}",
            f"Brillo:       {qc_result.get('brightness', 'N/A')}",
            f"Duración:     {qc_result.get('duration_seconds', 'N/A')}s",
            f"Frames:       {qc_result.get('frames_analyzed', 0)} analizados",
        ]

        if qc_result.get("issues"):
            lines.append("Problemas:")
            for issue in qc_result["issues"]:
                lines.append(f"  ⚠ {issue}")

        if qc_result.get("recommendations"):
            lines.append("Recomendaciones:")
            for rec in qc_result["recommendations"]:
                lines.append(f"  → {rec}")

        return "\n".join(lines)
