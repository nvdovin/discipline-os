"""Workout logging, weekly plan status, progression and personal records."""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import DailyLog, ExerciseSet, Habit, Workout
from app.services.habits import get_settings
from app.services.plan import (
    day_plan_for,
    effective_exercises,
    exercise_by_key,
    normalize_targets,
    workout_title,
)
from app.timeutils import (
    date_range,
    format_minutes,
    local_today,
    weekday_short_ru,
)

MAX_REPS = 200
MAX_DURATION_SECONDS = 7200


def _validate_day(day: date, timezone: str) -> None:
    if day > local_today(timezone):
        raise ValueError("Нельзя записывать будущую тренировку")


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zа-я0-9]+", "-", value.lower()).strip("-")
    return slug[:50] or "custom"


async def _get_or_create_workout(
    session: AsyncSession,
    day: date,
    workout_type: str,
    mode: str,
) -> Workout:
    workout = await session.scalar(
        select(Workout)
        .where(Workout.date == day)
        .options(selectinload(Workout.sets))
    )
    if workout is None:
        workout = Workout(
            date=day,
            workout_type=workout_type,
            mode=mode,
            status="in_progress",
        )
        session.add(workout)
        await session.flush()
    else:
        if workout.workout_type == "custom" and workout_type != "custom":
            workout.workout_type = workout_type
        if mode in {"full", "minimum"}:
            workout.mode = mode
    return workout


async def add_set(
    session: AsyncSession,
    day: date,
    *,
    exercise_key: str | None = None,
    exercise_name: str | None = None,
    repetitions: int | None = None,
    duration_seconds: int | None = None,
    rest_seconds: int | None = None,
    mode: str | None = None,
) -> Workout:
    settings = await get_settings(session)
    _validate_day(day, settings.timezone)
    if repetitions is None and duration_seconds is None:
        raise ValueError("Укажите повторения или длительность")
    if repetitions is not None and not (1 <= repetitions <= MAX_REPS):
        raise ValueError(f"Повторения должны быть от 1 до {MAX_REPS}")
    if duration_seconds is not None and not (
        1 <= duration_seconds <= MAX_DURATION_SECONDS
    ):
        raise ValueError("Длительность упражнения вне допустимого диапазона")
    if rest_seconds is not None and not (0 <= rest_seconds <= 600):
        raise ValueError("Отдых должен быть от 0 до 600 секунд")

    plan = day_plan_for(day.weekday())
    spec = exercise_by_key(day.weekday(), exercise_key) if exercise_key else None
    if spec is not None:
        key = spec.key
        name = spec.name
        workout_type = plan.key
    else:
        if not exercise_name or not exercise_name.strip():
            raise ValueError("Укажите название упражнения")
        name = exercise_name.strip()[:120]
        key = (exercise_key or _slugify(name))[:64]
        workout_type = "custom"

    workout = await _get_or_create_workout(
        session, day, workout_type, mode or "full"
    )
    await session.refresh(workout, attribute_names=["sets"])
    existing = [item for item in workout.sets if item.exercise_key == key]
    set_number = len(existing) + 1
    item = ExerciseSet(
        workout_id=workout.id,
        exercise_key=key,
        exercise_name=name,
        set_number=set_number,
        repetitions=repetitions,
        duration_seconds=duration_seconds,
        rest_seconds=rest_seconds,
    )
    session.add(item)
    await session.commit()
    await session.refresh(workout, attribute_names=["sets"])
    return workout


async def delete_set(session: AsyncSession, set_id: int) -> None:
    item = await session.get(ExerciseSet, set_id)
    if item is None:
        return
    workout = await session.get(Workout, item.workout_id)
    await session.delete(item)
    await session.flush()
    if workout is not None:
        remaining = await session.scalar(
            select(func.count(ExerciseSet.id)).where(
                ExerciseSet.workout_id == workout.id
            )
        )
        if not remaining and workout.status == "in_progress":
            await session.delete(workout)
    await session.commit()


async def complete_workout(
    session: AsyncSession,
    day: date,
    *,
    mode: str = "full",
    completed: bool = True,
    duration_minutes: int | None = None,
    notes: str | None = None,
) -> Workout:
    settings = await get_settings(session)
    _validate_day(day, settings.timezone)
    if mode not in {"full", "minimum"}:
        raise ValueError("Неизвестный режим тренировки")
    if duration_minutes is not None and not (1 <= duration_minutes <= 600):
        raise ValueError("Длительность тренировки должна быть от 1 до 600 минут")

    plan = day_plan_for(day.weekday())
    workout = await _get_or_create_workout(session, day, plan.key, mode)
    workout.mode = mode
    workout.status = "completed" if completed else "in_progress"
    if duration_minutes is not None:
        workout.total_duration_minutes = duration_minutes
    if notes is not None:
        workout.notes = notes
    elif completed and mode == "minimum":
        workout.notes = "Минимальная тренировка — привычка сохранена"
    await session.commit()
    await session.refresh(workout, attribute_names=["sets"])
    return workout


def _serialize_set(item: ExerciseSet) -> dict[str, Any]:
    return {
        "id": item.id,
        "exercise_key": item.exercise_key,
        "exercise_name": item.exercise_name,
        "set_number": item.set_number,
        "repetitions": item.repetitions,
        "duration_seconds": item.duration_seconds,
        "rest_seconds": item.rest_seconds,
    }


def _done_for_key(workout: Workout | None, key: str) -> dict[str, Any]:
    items = [item for item in (workout.sets if workout else []) if item.exercise_key == key]
    return {
        "sets": len(items),
        "reps": sum(item.repetitions or 0 for item in items),
        "duration_seconds": sum(item.duration_seconds or 0 for item in items),
        "items": [_serialize_set(item) for item in items],
    }


def _exercise_rows(
    day: date,
    overrides: dict[str, Any],
    mode: str,
    workout: Workout | None,
) -> list[dict[str, Any]]:
    rows = []
    for exercise in effective_exercises(day.weekday(), overrides, mode):
        done = _done_for_key(workout, exercise["key"])
        target_volume = (
            exercise["sets"] * (exercise["reps"] or 0)
            if exercise["kind"] == "reps"
            else exercise["sets"] * (exercise["duration_seconds"] or 0)
        )
        done_volume = done["reps"] if exercise["kind"] == "reps" else done["duration_seconds"]
        rows.append(
            {
                **exercise,
                # ``sets`` stays the planned number of sets; the logged sets
                # are returned separately so the client never has to guess.
                "done_sets": done["sets"],
                "done_reps": done["reps"],
                "done_duration_seconds": done["duration_seconds"],
                "progress": round(min(1.0, done_volume / target_volume), 3)
                if target_volume
                else 0.0,
                "logged_sets": done["items"],
            }
        )
    return rows


async def _progression(session: AsyncSession, end: date, days: int = 30) -> dict[str, list[dict[str, Any]]]:
    start = end - timedelta(days=days - 1)
    rows = (
        await session.execute(
            select(ExerciseSet, Workout.date)
            .join(Workout, ExerciseSet.workout_id == Workout.id)
            .where(Workout.date.between(start, end))
        )
    ).all()

    by_day: dict[str, dict[str, list[int]]] = {}
    for item, workout_date in rows:
        bucket = by_day.setdefault(
            workout_date.isoformat(), {"pushups": [], "pullups": [], "plank": []}
        )
        if item.exercise_key == "pushups" and item.repetitions:
            bucket["pushups"].append(item.repetitions)
        elif item.exercise_key == "pullups" and item.repetitions:
            bucket["pullups"].append(item.repetitions)
        elif item.exercise_key == "plank" and item.duration_seconds:
            bucket["plank"].append(item.duration_seconds)

    series: dict[str, list[dict[str, Any]]] = {
        "pushups": [],
        "pullups": [],
        "plank": [],
    }
    for current in date_range(end, days):
        key = current.isoformat()
        values = by_day.get(key, {})
        series["pushups"].append(
            {
                "date": key,
                "label": f"{current.day}",
                "value": max(values.get("pushups", [])) if values.get("pushups") else None,
            }
        )
        series["pullups"].append(
            {
                "date": key,
                "label": f"{current.day}",
                "value": sum(values.get("pullups", []))
                if values.get("pullups")
                else None,
            }
        )
        series["plank"].append(
            {
                "date": key,
                "label": f"{current.day}",
                "value": max(values.get("plank", [])) if values.get("plank") else None,
            }
        )
    return series


async def personal_records(session: AsyncSession) -> dict[str, Any]:
    rows = (
        await session.execute(
            select(ExerciseSet, Workout.date).join(
                Workout, ExerciseSet.workout_id == Workout.id
            )
        )
    ).all()

    pushups_max = 0
    plank_max = 0
    pullups_by_day: dict[date, int] = {}
    generic: dict[str, dict[str, Any]] = {}
    for item, workout_date in rows:
        if item.repetitions:
            if item.exercise_key == "pushups":
                pushups_max = max(pushups_max, item.repetitions)
            if item.exercise_key == "pullups":
                pullups_by_day[workout_date] = (
                    pullups_by_day.get(workout_date, 0) + item.repetitions
                )
        if item.duration_seconds and item.exercise_key == "plank":
            plank_max = max(plank_max, item.duration_seconds)

        record = generic.setdefault(
            item.exercise_key,
            {
                "key": item.exercise_key,
                "name": item.exercise_name,
                "reps": 0,
                "duration_seconds": 0,
                "date": workout_date.isoformat(),
            },
        )
        if (item.repetitions or 0) > record["reps"]:
            record["reps"] = item.repetitions or 0
            record["date"] = workout_date.isoformat()
        if (item.duration_seconds or 0) > record["duration_seconds"]:
            record["duration_seconds"] = item.duration_seconds or 0
            record["date"] = workout_date.isoformat()

    pullups_day = max(pullups_by_day.values(), default=0)
    return {
        "pushups": pushups_max,
        "pullups_day": pullups_day,
        "plank_seconds": plank_max,
        "list": sorted(
            generic.values(),
            key=lambda item: item["name"],
        ),
    }


async def _week_strip(
    session: AsyncSession, day: date
) -> list[dict[str, Any]]:
    week_start = day - timedelta(days=day.weekday())
    week_end = week_start + timedelta(days=6)
    workouts = list(
        (
            await session.scalars(
                select(Workout)
                .where(Workout.date.between(week_start, week_end))
                .options(selectinload(Workout.sets))
            )
        ).all()
    )
    workout_map = {workout.date: workout for workout in workouts}
    log_rows = (
        await session.execute(
            select(DailyLog.date)
            .join(Habit, DailyLog.habit_id == Habit.id)
            .where(
                Habit.key == "exercise",
                DailyLog.date.between(week_start, week_end),
                DailyLog.completed.is_(True),
            )
        )
    ).all()
    logged_days = {row[0] for row in log_rows}
    today = day
    strip = []
    for offset in range(7):
        current = week_start + timedelta(days=offset)
        workout = workout_map.get(current)
        plan = day_plan_for(current.weekday())
        if workout and workout.status == "completed":
            status = "done"
        elif workout and workout.sets:
            status = "partial"
        elif current in logged_days:
            status = "done"
        elif current == today:
            status = "today"
        elif current < today:
            status = "open"
        else:
            status = "planned"
        strip.append(
            {
                "date": current.isoformat(),
                "weekday_short": weekday_short_ru(current),
                "day": current.day,
                "title": plan.title,
                "kind": plan.kind,
                "status": status,
                "is_today": current == today,
            }
        )
    return strip


async def _activity_days(session: AsyncSession, end: date, days: int = 30) -> int:
    start = end - timedelta(days=days - 1)
    workout_days = set(
        (
            await session.scalars(
                select(Workout.date).where(Workout.date.between(start, end))
            )
        ).all()
    )
    logged_days = set(
        (
            await session.scalars(
                select(DailyLog.date)
                .join(Habit, DailyLog.habit_id == Habit.id)
                .where(
                    Habit.key == "exercise",
                    DailyLog.date.between(start, end),
                    DailyLog.completed.is_(True),
                )
            )
        ).all()
    )
    return len(workout_days | logged_days)


async def build_fitness(
    session: AsyncSession, day: date, days: int = 30
) -> dict[str, Any]:
    settings = await get_settings(session)
    overrides = normalize_targets(settings.exercise_targets)
    workout = await session.scalar(
        select(Workout)
        .where(Workout.date == day)
        .options(selectinload(Workout.sets))
    )
    plan = day_plan_for(day.weekday())
    mode = workout.mode if workout else "full"

    full_exercises = _exercise_rows(day, overrides, "full", workout)
    minimum_exercises = _exercise_rows(day, overrides, "minimum", workout)
    planned_keys = {exercise["key"] for exercise in full_exercises}
    custom_sets = [
        _serialize_set(item)
        for item in (workout.sets if workout else [])
        if item.exercise_key not in planned_keys
    ]

    progression = await _progression(session, day, days=30)
    records = await personal_records(session)
    history_rows = list(
        (
            await session.scalars(
                select(Workout)
                .where(Workout.date <= day)
                .options(selectinload(Workout.sets))
                .order_by(Workout.date.desc())
                .limit(14)
            )
        ).all()
    )
    total_completed = await session.scalar(
        select(func.count(Workout.id)).where(Workout.status == "completed")
    )

    return {
        "date": day.isoformat(),
        "weekday": day.weekday(),
        "plan": {
            "key": plan.key,
            "title": plan.title,
            "subtitle": plan.subtitle,
            "kind": plan.kind,
        },
        "mode": mode,
        "workout": {
            "id": workout.id,
            "status": workout.status,
            "mode": workout.mode,
            "duration_minutes": workout.total_duration_minutes,
            "duration_label": format_minutes(workout.total_duration_minutes)
            if workout and workout.total_duration_minutes
            else None,
            "notes": workout.notes,
            "sets_count": len(workout.sets) if workout else 0,
            "sets": [_serialize_set(item) for item in workout.sets] if workout else [],
        }
        if workout
        else None,
        "modes": {
            "full": full_exercises,
            "minimum": minimum_exercises,
        },
        "custom_sets": custom_sets,
        "week": await _week_strip(session, day),
        "progression": progression,
        "records": records,
        "activity_days_30": await _activity_days(session, day),
        "total_workouts": int(total_completed or 0),
        "history": [
            {
                "id": item.id,
                "date": item.date.isoformat(),
                "weekday_short": weekday_short_ru(item.date),
                "title": workout_title(item.workout_type),
                "mode": item.mode,
                "status": item.status,
                "sets_count": len(item.sets),
                "duration_minutes": item.total_duration_minutes,
                "notes": item.notes,
            }
            for item in history_rows
            if item.sets or item.status == "completed"
        ],
        "targets": overrides,
    }
