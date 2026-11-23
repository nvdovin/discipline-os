"""One main daily priority, optional secondary tasks and evening reflection."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DailyReflection
from app.services.habits import get_settings, reflection_dict
from app.timeutils import date_range, local_today, weekday_short_ru

MAX_SECONDARY_TASKS = 10


def _serialize_history(item: DailyReflection) -> dict[str, Any]:
    data = reflection_dict(item)
    return {
        "date": item.date.isoformat(),
        "weekday_short": weekday_short_ru(item.date),
        **data,
    }


def _streak(reflections: dict[date, DailyReflection], day: date) -> dict[str, int]:
    def done(current: date) -> bool:
        item = reflections.get(current)
        return bool(item and item.priority_completed and item.main_priority)

    anchor = day if done(day) else day - timedelta(days=1)
    current = 0
    cursor = anchor
    while done(cursor):
        current += 1
        cursor -= timedelta(days=1)

    best = 0
    running = 0
    for current_day in sorted(reflections):
        if done(current_day):
            running += 1
            best = max(best, running)
        else:
            running = 0
    return {"current": current, "best": max(best, current)}


async def build_priority(session: AsyncSession, day: date) -> dict[str, Any]:
    start = day - timedelta(days=119)
    reflections = list(
        (
            await session.scalars(
                select(DailyReflection)
                .where(DailyReflection.date.between(start, day))
                .order_by(DailyReflection.date)
            )
        ).all()
    )
    by_date = {item.date: item for item in reflections}
    today = by_date.get(day)
    week_start = day - timedelta(days=6)
    week_items = [item for item in reflections if item.date >= week_start]
    history = [
        _serialize_history(item)
        for item in sorted(reflections, key=lambda entry: entry.date, reverse=True)
        if item.main_priority or item.positive_result or item.tomorrow_priority
    ][:14]
    return {
        "date": day.isoformat(),
        "today": reflection_dict(today),
        "has_priority": bool(today and today.main_priority),
        "week": {
            "completed": sum(
                1 for item in week_items if item.priority_completed and item.main_priority
            ),
            "with_priority": sum(1 for item in week_items if item.main_priority),
            "days": 7,
        },
        "streak": _streak(by_date, day),
        "history": history,
    }


async def upsert_priority(
    session: AsyncSession,
    day: date,
    *,
    main_priority: str | None = None,
    priority_completed: bool | None = None,
    secondary_tasks: list[dict[str, Any]] | None = None,
    positive_result: str | None = None,
    difficulty: str | None = None,
    tomorrow_priority: str | None = None,
) -> DailyReflection:
    settings = await get_settings(session)
    if day > local_today(settings.timezone):
        raise ValueError("Нельзя записывать будущий день")

    reflection = await session.scalar(
        select(DailyReflection).where(DailyReflection.date == day)
    )
    if reflection is None:
        reflection = DailyReflection(date=day, secondary_tasks=[])
        session.add(reflection)
        await session.flush()

    if main_priority is not None:
        cleaned = main_priority.strip()[:300]
        reflection.main_priority = cleaned or None
        if not reflection.main_priority:
            reflection.priority_completed = False
    if priority_completed is not None:
        if priority_completed and not reflection.main_priority:
            raise ValueError("Сначала назначьте главное дело")
        reflection.priority_completed = priority_completed

    if secondary_tasks is not None:
        if len(secondary_tasks) > MAX_SECONDARY_TASKS:
            raise ValueError(
                f"Второстепенных задач может быть не больше {MAX_SECONDARY_TASKS}"
            )
        cleaned_tasks = []
        for index, task in enumerate(secondary_tasks):
            text = str(task.get("text") or "").strip()
            if not text:
                continue
            cleaned_tasks.append(
                {
                    "id": str(task.get("id") or f"task-{index + 1}")[:50],
                    "text": text[:200],
                    "done": bool(task.get("done")),
                }
            )
        reflection.secondary_tasks = cleaned_tasks

    if positive_result is not None:
        reflection.positive_result = positive_result.strip()[:2000] or None
    if difficulty is not None:
        reflection.difficulty = difficulty.strip()[:2000] or None
    if tomorrow_priority is not None:
        reflection.tomorrow_priority = tomorrow_priority.strip()[:300] or None

    await session.commit()
    await session.refresh(reflection)
    return reflection


async def get_reflection(session: AsyncSession, day: date) -> DailyReflection | None:
    return await session.scalar(
        select(DailyReflection).where(DailyReflection.date == day)
    )
