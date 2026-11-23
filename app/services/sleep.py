"""Sleep logs, duration, schedule consistency and trends."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SleepLog
from app.services.habits import (
    SLEEP_SCHEDULE_TOLERANCE_MINUTES,
    get_settings,
)
from app.timeutils import (
    circular_minute_delta,
    date_range,
    format_minutes,
    local_today,
    minutes_to_hhmm,
    parse_hhmm,
    planned_sleep_minutes,
    sleep_duration_minutes,
    time_to_minutes,
    weekday_short_ru,
)

MIN_SLEEP_MINUTES = 120
MAX_SLEEP_MINUTES = 900


def on_schedule(log: SleepLog, bedtime: str, wake_up_time: str) -> bool:
    return (
        circular_minute_delta(log.bedtime, bedtime)
        <= SLEEP_SCHEDULE_TOLERANCE_MINUTES
        and circular_minute_delta(log.wake_up_time, wake_up_time)
        <= SLEEP_SCHEDULE_TOLERANCE_MINUTES
    )


def serialize_sleep(
    log: SleepLog, bedtime: str, wake_up_time: str
) -> dict[str, Any]:
    return {
        "date": log.date.isoformat(),
        "weekday_short": weekday_short_ru(log.date),
        "bedtime": log.bedtime,
        "wake_up_time": log.wake_up_time,
        "duration_minutes": log.duration_minutes,
        "duration_label": format_minutes(log.duration_minutes),
        "on_schedule": on_schedule(log, bedtime, wake_up_time),
        "notes": log.notes,
    }


def _average_bedtime(logs: list[SleepLog]) -> str | None:
    if not logs:
        return None
    values = []
    for log in logs:
        minutes = time_to_minutes(log.bedtime)
        if minutes < 12 * 60:
            minutes += 24 * 60
        values.append(minutes)
    average = round(sum(values) / len(values)) % (24 * 60)
    return minutes_to_hhmm(average)


def _average_wake(logs: list[SleepLog]) -> str | None:
    if not logs:
        return None
    average = round(
        sum(time_to_minutes(log.wake_up_time) for log in logs) / len(logs)
    ) % (24 * 60)
    return minutes_to_hhmm(average)


def _consistency(logs: list[SleepLog], settings_bedtime: str, settings_wake: str) -> dict[str, Any]:
    if not logs:
        return {
            "logged": 0,
            "on_schedule": 0,
            "pct": 0,
            "avg_duration_minutes": None,
            "avg_duration_label": "—",
            "avg_bedtime": None,
            "avg_wake_up_time": None,
        }
    scheduled = [log for log in logs if on_schedule(log, settings_bedtime, settings_wake)]
    avg_duration = round(sum(log.duration_minutes for log in logs) / len(logs))
    return {
        "logged": len(logs),
        "on_schedule": len(scheduled),
        "pct": round(len(scheduled) / len(logs) * 100),
        "avg_duration_minutes": avg_duration,
        "avg_duration_label": format_minutes(avg_duration),
        "avg_bedtime": _average_bedtime(logs),
        "avg_wake_up_time": _average_wake(logs),
    }


async def build_sleep(
    session: AsyncSession, day: date, days: int = 30
) -> dict[str, Any]:
    settings = await get_settings(session)
    start = day - timedelta(days=max(1, days) - 1)
    logs = list(
        (
            await session.scalars(
                select(SleepLog)
                .where(SleepLog.date.between(start, day))
                .order_by(SleepLog.date)
            )
        ).all()
    )
    by_date = {log.date: log for log in logs}
    target_minutes = planned_sleep_minutes(settings.bedtime, settings.wake_up_time)
    today_log = by_date.get(day)

    week_start = day - timedelta(days=6)
    week_logs = [log for log in logs if log.date >= week_start]
    consistency_7 = _consistency(week_logs, settings.bedtime, settings.wake_up_time)
    consistency_30 = _consistency(logs, settings.bedtime, settings.wake_up_time)

    series = []
    for current in date_range(day, min(days, 30)):
        log = by_date.get(current)
        series.append(
            {
                "date": current.isoformat(),
                "label": weekday_short_ru(current),
                "day": current.day,
                "duration_minutes": log.duration_minutes if log else None,
                "on_schedule": on_schedule(log, settings.bedtime, settings.wake_up_time)
                if log
                else None,
                "bedtime": log.bedtime if log else None,
                "wake_up_time": log.wake_up_time if log else None,
            }
        )

    return {
        "date": day.isoformat(),
        "target": {
            "bedtime": settings.bedtime,
            "wake_up_time": settings.wake_up_time,
            "duration_minutes": target_minutes,
            "duration_label": format_minutes(target_minutes),
            "tolerance_minutes": SLEEP_SCHEDULE_TOLERANCE_MINUTES,
        },
        "today": serialize_sleep(
            today_log, settings.bedtime, settings.wake_up_time
        )
        if today_log
        else None,
        "consistency": consistency_7,
        "consistency_30": consistency_30,
        "series": series,
        "history": [
            serialize_sleep(log, settings.bedtime, settings.wake_up_time)
            for log in sorted(logs, key=lambda item: item.date, reverse=True)[:14]
        ],
    }


async def upsert_sleep(
    session: AsyncSession,
    day: date,
    bedtime: str,
    wake_up_time: str,
    notes: str | None = None,
) -> SleepLog:
    settings = await get_settings(session)
    if day > local_today(settings.timezone):
        raise ValueError("Нельзя записывать будущий сон")
    parse_hhmm(bedtime)
    parse_hhmm(wake_up_time)
    duration = sleep_duration_minutes(bedtime, wake_up_time)
    if duration < MIN_SLEEP_MINUTES or duration > MAX_SLEEP_MINUTES:
        raise ValueError(
            "Продолжительность сна выглядит неправдоподобно (2–15 часов)"
        )

    log = await session.scalar(select(SleepLog).where(SleepLog.date == day))
    if log is None:
        log = SleepLog(
            date=day,
            bedtime=bedtime,
            wake_up_time=wake_up_time,
            duration_minutes=duration,
            notes=notes,
        )
        session.add(log)
    else:
        log.bedtime = bedtime
        log.wake_up_time = wake_up_time
        log.duration_minutes = duration
        log.notes = notes
    await session.commit()
    await session.refresh(log)
    return log


async def delete_sleep(session: AsyncSession, day: date) -> None:
    log = await session.scalar(select(SleepLog).where(SleepLog.date == day))
    if log is not None:
        await session.delete(log)
        await session.commit()
