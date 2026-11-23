"""Bible reading logs and consistency."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BibleLog
from app.services.habits import get_settings
from app.timeutils import (
    date_range,
    local_today,
    weekday_short_ru,
)

MAX_BIBLE_MINUTES = 600


def _serialize(log: BibleLog) -> dict[str, Any]:
    return {
        "date": log.date.isoformat(),
        "duration_minutes": log.duration_minutes,
        "notes": log.notes,
    }


def _streak(logs_by_date: dict[date, BibleLog], target: int, day: date) -> dict[str, int]:
    def done(current: date) -> bool:
        log = logs_by_date.get(current)
        return bool(log and log.duration_minutes >= target)

    anchor = day if done(day) else day - timedelta(days=1)
    current = 0
    cursor = anchor
    while done(cursor):
        current += 1
        cursor -= timedelta(days=1)

    best = 0
    running = 0
    for current_day in sorted(logs_by_date):
        if done(current_day):
            running += 1
            best = max(best, running)
        else:
            running = 0
    return {"current": current, "best": max(best, current)}


async def build_bible(
    session: AsyncSession, day: date, days: int = 30
) -> dict[str, Any]:
    settings = await get_settings(session)
    start = day - timedelta(days=max(days, 120) - 1)
    logs = list(
        (
            await session.scalars(
                select(BibleLog)
                .where(BibleLog.date.between(start, day))
                .order_by(BibleLog.date)
            )
        ).all()
    )
    by_date = {log.date: log for log in logs}
    target = settings.bible_target_minutes
    today_log = by_date.get(day)

    week_days = date_range(day, 7)
    week_logs = [by_date[current] for current in week_days if current in by_date]
    completed_week = sum(
        1 for log in week_logs if log.duration_minutes >= target
    )

    series = []
    for current in date_range(day, min(days, 30)):
        log = by_date.get(current)
        series.append(
            {
                "date": current.isoformat(),
                "label": weekday_short_ru(current),
                "day": current.day,
                "minutes": log.duration_minutes if log else None,
                "target_minutes": target,
                "complete": bool(log and log.duration_minutes >= target),
            }
        )

    return {
        "date": day.isoformat(),
        "target_minutes": target,
        "today": _serialize(today_log) if today_log else None,
        "series": series,
        "totals": {
            "minutes_7": sum(log.duration_minutes for log in week_logs),
            "minutes_30": sum(
                log.duration_minutes
                for current, log in by_date.items()
                if current >= day - timedelta(days=29)
            ),
            "days_7": len(week_logs),
            "completed_days_7": completed_week,
        },
        "consistency": {
            "days": 7,
            "logged": len(week_logs),
            "completed": completed_week,
            "pct": round(completed_week / 7 * 100),
        },
        "streak": _streak(by_date, target, day),
        "history": [
            _serialize(log)
            for log in sorted(logs, key=lambda item: item.date, reverse=True)[:14]
        ],
    }


async def upsert_bible(
    session: AsyncSession,
    day: date,
    duration_minutes: int,
    notes: str | None = None,
) -> BibleLog:
    settings = await get_settings(session)
    if day > local_today(settings.timezone):
        raise ValueError("Нельзя записывать будущее чтение")
    if not (1 <= duration_minutes <= MAX_BIBLE_MINUTES):
        raise ValueError(f"Минуты должны быть от 1 до {MAX_BIBLE_MINUTES}")
    if notes is not None and len(notes) > 2000:
        raise ValueError("Заметка слишком длинная")
    notes = notes.strip() if notes and notes.strip() else None

    log = await session.scalar(select(BibleLog).where(BibleLog.date == day))
    if log is None:
        log = BibleLog(date=day, duration_minutes=duration_minutes, notes=notes)
        session.add(log)
    else:
        log.duration_minutes = duration_minutes
        log.notes = notes
    await session.commit()
    await session.refresh(log)
    return log


async def delete_bible(session: AsyncSession, day: date) -> None:
    log = await session.scalar(select(BibleLog).where(BibleLog.date == day))
    if log is not None:
        await session.delete(log)
        await session.commit()
