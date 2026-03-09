"""
scheduler.py
─────────────
Gestiona los horarios de publicación y programación de videos.
Calcula la hora óptima basada en análisis de engagement.
"""

import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


# Horarios de mayor engagement por día (hora en UTC-5, México/Colombia)
OPTIMAL_TIMES = {
    "Monday":    ["18:00", "20:00", "08:00"],
    "Tuesday":   ["18:30", "20:00", "12:00"],
    "Wednesday": ["18:00", "20:30", "09:00"],
    "Thursday":  ["18:00", "19:30", "12:00"],
    "Friday":    ["17:00", "20:00", "14:00"],
    "Saturday":  ["10:00", "15:00", "20:00"],
    "Sunday":    ["11:00", "15:00", "19:00"],
}


class VideoScheduler:
    """
    Calcula y gestiona los horarios óptimos de publicación.
    """

    def __init__(self, timezone_str: str = "America/Mexico_City"):
        self.timezone = ZoneInfo(timezone_str)

    def calculate_publish_time(
        self,
        preferred_time: str = None,
        delay_minutes: int = 30,
    ) -> datetime:
        """
        Calcula la próxima hora óptima de publicación.

        Args:
            preferred_time: Hora preferida "HH:MM" (opcional)
            delay_minutes: Minutos de retraso desde ahora (mínimo)

        Returns:
            datetime con la hora de publicación en UTC
        """
        now_local = datetime.now(self.timezone)
        day_name = now_local.strftime("%A")

        if preferred_time:
            # Usar la hora preferida del análisis de tendencias
            target_dt = self._parse_time_today(preferred_time)
        else:
            # Usar el siguiente horario óptimo del día
            target_dt = self._get_next_optimal_time(day_name)

        # Asegurar que hay al menos `delay_minutes` de margen
        min_time = now_local + timedelta(minutes=delay_minutes)
        if target_dt <= min_time:
            # Programar para la siguiente hora óptima
            target_dt = min_time + timedelta(minutes=5)

        # Convertir a UTC para la API de YouTube
        target_utc = target_dt.astimezone(timezone.utc)
        logger.info(f"Publicación programada: {target_dt.strftime('%A %d/%m %H:%M %Z')} "
                    f"({target_utc.strftime('%H:%M UTC')})")

        return target_utc

    def _parse_time_today(self, time_str: str) -> datetime:
        """Convierte HH:MM al datetime de hoy en la zona horaria local."""
        try:
            hour, minute = map(int, time_str.split(":"))
            now = datetime.now(self.timezone)
            target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            # Si ya pasó, programar para mañana
            if target < now:
                target += timedelta(days=1)
            return target
        except Exception:
            return datetime.now(self.timezone) + timedelta(hours=1)

    def _get_next_optimal_time(self, day_name: str) -> datetime:
        """Obtiene el siguiente horario óptimo para el día actual."""
        now = datetime.now(self.timezone)
        times = OPTIMAL_TIMES.get(day_name, ["18:00", "20:00"])

        for time_str in times:
            dt = self._parse_time_today(time_str)
            if dt > now + timedelta(minutes=30):
                return dt

        # Si todos los horarios ya pasaron, usar el primero de mañana
        tomorrow = now + timedelta(days=1)
        tomorrow_day = tomorrow.strftime("%A")
        first_time = OPTIMAL_TIMES.get(tomorrow_day, ["18:00"])[0]
        hour, minute = map(int, first_time.split(":"))
        return tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0)

    def get_weekly_schedule(self) -> dict:
        """Retorna el horario óptimo semanal."""
        return OPTIMAL_TIMES

    def should_run_now(self, scheduled_times: list) -> bool:
        """
        Verifica si es hora de ejecutar el pipeline.

        Args:
            scheduled_times: Lista de horarios ["HH:MM", ...]

        Returns:
            True si es hora de ejecutar (±5 minutos)
        """
        now = datetime.now(self.timezone)
        current_hhmm = now.strftime("%H:%M")

        for scheduled in scheduled_times:
            scheduled = scheduled.strip()
            if scheduled == current_hhmm:
                return True
            # Ventana de ±5 minutos
            try:
                sh, sm = map(int, scheduled.split(":"))
                scheduled_total = sh * 60 + sm
                current_total = int(now.strftime("%H")) * 60 + int(now.strftime("%M"))
                if abs(scheduled_total - current_total) <= 5:
                    return True
            except Exception:
                pass

        return False

    def format_publish_time_for_description(self, publish_dt: datetime) -> str:
        """Formatea la fecha de publicación para la descripción del video."""
        local_dt = publish_dt.astimezone(self.timezone)
        return local_dt.strftime("%d de %B de %Y a las %H:%M")
