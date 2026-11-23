"""Time zone and date/time helpers.

The database stores local wall-clock times (``HH:MM``) together with local
dates. That is intentional: a personal habit log is about the day the user
experienced, not about UTC. Conversions happen only at the edges.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

WEEKDAYS_RU = [
    "Понедельник",
    "Вторник",
    "Среда",
    "Четверг",
    "Пятница",
    "Суббота",
    "Воскресенье",
]
WEEKDAYS_SHORT_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
MONTHS_RU = [
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
]

DEFAULT_TIMEZONE = "Europe/Moscow"


def valid_timezone(name: str) -> bool:
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        return False
    return True


def tzinfo(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(DEFAULT_TIMEZONE)


def local_now(timezone_name: str) -> datetime:
    return datetime.now(tzinfo(timezone_name))


def local_today(timezone_name: str) -> date:
    return local_now(timezone_name).date()


def parse_date(value: str | date | None, timezone_name: str) -> date:
    if value is None:
        return local_today(timezone_name)
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def parse_hhmm(value: str) -> time:
    """Parse strict ``HH:MM`` (24h). Raises ``ValueError`` on bad input."""
    if not isinstance(value, str):
        raise ValueError("Время должно быть строкой в формате ЧЧ:ММ")
    parts = value.strip().split(":")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        raise ValueError("Время должно быть в формате ЧЧ:ММ")
    hour, minute = int(parts[0]), int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("Недопустимое время")
    return time(hour, minute)


def time_to_minutes(value: str) -> int:
    parsed = parse_hhmm(value)
    return parsed.hour * 60 + parsed.minute


def minutes_to_hhmm(total: int) -> str:
    total %= 24 * 60
    return f"{total // 60:02d}:{total % 60:02d}"


def sleep_duration_minutes(bedtime: str, wake_up_time: str) -> int:
    """Duration of a night, crossing midnight when needed.

    ``23:30 -> 06:30`` gives 420 minutes. ``00:30 -> 07:00`` gives 390.
    Equal times are treated as a full 24 hours, which callers reject as
    implausible.
    """
    bed = time_to_minutes(bedtime)
    wake = time_to_minutes(wake_up_time)
    duration = wake - bed
    if duration <= 0:
        duration += 24 * 60
    return duration


def planned_sleep_minutes(bedtime: str, wake_up_time: str) -> int:
    return sleep_duration_minutes(bedtime, wake_up_time)


def format_minutes(total: int | None) -> str:
    if total is None:
        return "—"
    hours, minutes = divmod(max(0, int(total)), 60)
    if hours and minutes:
        return f"{hours} ч {minutes} мин"
    if hours:
        return f"{hours} ч"
    return f"{minutes} мин"


def circular_minute_delta(a: str, b: str) -> int:
    """Smallest absolute difference between two wall-clock times."""
    diff = abs(time_to_minutes(a) - time_to_minutes(b))
    return min(diff, 24 * 60 - diff)


def weekday_ru(day: date) -> str:
    return WEEKDAYS_RU[day.weekday()]


def weekday_short_ru(day: date) -> str:
    return WEEKDAYS_SHORT_RU[day.weekday()]


def human_date_ru(day: date) -> str:
    return f"{day.day} {MONTHS_RU[day.month - 1]}"


def date_range(end: date, days: int) -> list[date]:
    """Inclusive range ending at ``end`` (oldest first)."""
    days = max(1, days)
    return [end - timedelta(days=offset) for offset in range(days - 1, -1, -1)]


def iso(day: date | datetime | None) -> str | None:
    return day.isoformat() if day is not None else None
