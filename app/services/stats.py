"""Weekly and monthly reports, consistency, records and milestones."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BibleLog, BodyMeasurement, Workout
from app.services.fitness import personal_records
from app.services.habits import build_states, compute_streaks, load_range
from app.services.plan import normalize_targets
from app.timeutils import (
    date_range,
    format_minutes,
    human_date_ru,
    weekday_short_ru,
)

PERIOD_DAYS = {"week": 7, "month": 30}


def _avg(values: list[int | float]) -> float:
    return round(sum(values) / len(values), 1) if values else 0.0


def _measurement_series(
    measurements: list[BodyMeasurement], attr: str
) -> list[dict[str, Any]]:
    return [
        {
            "date": item.date.isoformat(),
            "label": f"{item.date.day}.{item.date.month:02d}",
            "value": getattr(item, attr),
        }
        for item in measurements
        if getattr(item, attr) is not None
    ]


def _delta(points: list[dict[str, Any]]) -> float | None:
    if len(points) < 2:
        return None
    return round(points[-1]["value"] - points[0]["value"], 1)


def _milestones(
    *,
    all_states: list[dict[str, Any]],
    streak_best: int,
    total_workouts: int,
    total_bible_minutes: int,
    records: dict[str, Any],
) -> list[dict[str, Any]]:
    success_days = sum(1 for state in all_states if state["success"])
    pullups_day = records.get("pullups_day", 0)

    definitions = [
        {
            "key": "first_step",
            "title": "Первый шаг",
            "description": "День, где закрыто 3 из 5 привычек",
            "value": success_days,
            "target": 1,
            "unit": "дней",
            "icon": "spark",
        },
        {
            "key": "week_streak",
            "title": "Неделя ритма",
            "description": "7 дней подряд с результатом 60%+",
            "value": streak_best,
            "target": 7,
            "unit": "дней",
            "icon": "flame",
        },
        {
            "key": "month_streak",
            "title": "Месяц дисциплины",
            "description": "30 дней подряд без давления",
            "value": streak_best,
            "target": 30,
            "unit": "дней",
            "icon": "trophy",
        },
        {
            "key": "workouts_10",
            "title": "10 тренировок",
            "description": "Любая активность считается",
            "value": total_workouts,
            "target": 10,
            "unit": "тренировок",
            "icon": "dumbbell",
        },
        {
            "key": "workouts_30",
            "title": "30 тренировок",
            "description": "Постепенность важнее рывков",
            "value": total_workouts,
            "target": 30,
            "unit": "тренировок",
            "icon": "medal",
        },
        {
            "key": "bible_500",
            "title": "500 минут Библии",
            "description": "Время, проведённое в Слове",
            "value": total_bible_minutes,
            "target": 500,
            "unit": "минут",
            "icon": "book",
        },
        {
            "key": "pushups_20",
            "title": "20 отжиманий",
            "description": "Личный рекорд в одном подходе",
            "value": records.get("pushups", 0),
            "target": 20,
            "unit": "раз",
            "icon": "trend",
        },
        {
            "key": "plank_60",
            "title": "Планка 60 секунд",
            "description": "Спокойно и без рывков",
            "value": records.get("plank_seconds", 0),
            "target": 60,
            "unit": "сек",
            "icon": "timer",
        },
        {
            "key": "pullups_30",
            "title": "30 подтягиваний за день",
            "description": "Комфортный дневной объём",
            "value": pullups_day,
            "target": 30,
            "unit": "раз",
            "icon": "trend",
        },
    ]
    for item in definitions:
        item["earned"] = item["value"] >= item["target"]
        item["progress"] = round(min(1.0, item["value"] / item["target"]), 3)
    return definitions


async def build_stats(
    session: AsyncSession, day: date, period: str = "week"
) -> dict[str, Any]:
    if period not in PERIOD_DAYS:
        raise ValueError("Период должен быть week или month")
    days = PERIOD_DAYS[period]
    period_start = day - timedelta(days=days - 1)
    previous_start = period_start - timedelta(days=days)
    context_start = day - timedelta(days=364)

    data = await load_range(session, context_start, day)
    all_states = build_states(data, context_start, day)
    by_date = {date.fromisoformat(state["date"]): state for state in all_states}
    period_states = [
        by_date[current] for current in date_range(day, days) if current in by_date
    ]
    previous_states = [
        by_date[current]
        for current in date_range(period_start - timedelta(days=1), days)
        if current in by_date
    ]
    streaks = compute_streaks(all_states)

    completions = [state["completion"] for state in period_states]
    previous_completions = [state["completion"] for state in previous_states]
    exercise_days = sum(
        1
        for state in period_states
        if state["exercise"]["sets_done"] > 0
        or state["exercise"]["completed"]
        or next(
            (habit["completed"] for habit in state["habits"] if habit["key"] == "exercise"),
            False,
        )
    )
    bible_minutes = sum(state["bible"]["minutes"] for state in period_states)
    sleep_values = [
        state["sleep"]["duration_minutes"]
        for state in period_states
        if state["sleep"]["duration_minutes"] is not None
    ]
    nutrition_days = sum(
        1
        for state in period_states
        if state["nutrition"]["meals_count"] >= state["nutrition"]["meals_target"]
    )
    success_days = sum(1 for state in period_states if state["success"])

    measurements = list(
        (
            await session.scalars(
                select(BodyMeasurement)
                .where(BodyMeasurement.date.between(period_start, day))
                .order_by(BodyMeasurement.date)
            )
        ).all()
    )
    weight_series = _measurement_series(measurements, "weight_kg")
    waist_series = _measurement_series(measurements, "waist_cm")

    total_workouts = int(
        (
            await session.scalar(
                select(func.count(Workout.id)).where(Workout.status == "completed")
            )
        )
        or 0
    )
    total_bible_minutes = int(
        (await session.scalar(select(func.sum(BibleLog.duration_minutes)))) or 0
    )
    records = await personal_records(session)

    habit_names = {
        habit["key"]: habit["name"]
        for state in period_states
        for habit in state["habits"]
    }
    habit_stats = []
    for key, name in habit_names.items():
        completed = sum(
            1
            for state in period_states
            if next(
                (habit["completed"] for habit in state["habits"] if habit["key"] == key),
                False,
            )
        )
        habit_stats.append(
            {
                "key": key,
                "name": name,
                "completed_days": completed,
                "days": len(period_states),
                "pct": round(completed / len(period_states) * 100)
                if period_states
                else 0,
                "streak": streaks["habits"].get(key, {"current": 0, "best": 0}),
            }
        )

    daily = []
    for state in period_states:
        current = date.fromisoformat(state["date"])
        daily.append(
            {
                "date": state["date"],
                "label": weekday_short_ru(current)
                if period == "week"
                else str(current.day),
                "completion": state["completion"],
                "success": state["success"],
            }
        )

    sleep_series = [
        {
            "date": state["date"],
            "label": weekday_short_ru(date.fromisoformat(state["date"]))
            if period == "week"
            else str(date.fromisoformat(state["date"]).day),
            "value": state["sleep"]["duration_minutes"],
            "target": state["sleep"]["target_minutes"],
        }
        for state in period_states
    ]

    avg_completion = round(_avg(completions))
    previous_avg = round(_avg(previous_completions))
    milestones = _milestones(
        all_states=all_states,
        streak_best=streaks["best"],
        total_workouts=total_workouts,
        total_bible_minutes=total_bible_minutes,
        records=records,
    )

    return {
        "period": period,
        "days": days,
        "range": {
            "start": period_start.isoformat(),
            "end": day.isoformat(),
            "label": f"{human_date_ru(period_start)} — {human_date_ru(day)}",
        },
        "completion": avg_completion,
        "previous_completion": previous_avg,
        "completion_delta": avg_completion - previous_avg,
        "success_days": success_days,
        "perfect_days": sum(1 for value in completions if value == 100),
        "exercise_days": exercise_days,
        "bible_minutes": bible_minutes,
        "avg_sleep_minutes": round(_avg(sleep_values)),
        "avg_sleep_label": format_minutes(round(_avg(sleep_values)))
        if sleep_values
        else "—",
        "sleep_logged_days": len(sleep_values),
        "nutrition_days": nutrition_days,
        "nutrition_pct": round(nutrition_days / len(period_states) * 100)
        if period_states
        else 0,
        "weight": {
            "latest": weight_series[-1]["value"] if weight_series else None,
            "delta": _delta(weight_series),
            "series": weight_series,
        },
        "waist": {
            "latest": waist_series[-1]["value"] if waist_series else None,
            "delta": _delta(waist_series),
            "series": waist_series,
        },
        "daily": daily,
        "sleep_series": sleep_series,
        "habit_stats": habit_stats,
        "streak": {
            "current": streaks["current"],
            "best": streaks["best"],
            "threshold": streaks["threshold"],
            "habits": streaks["habits"],
        },
        "milestones": milestones,
        "records": records,
        "total_workouts": total_workouts,
        "total_bible_minutes": total_bible_minutes,
        "targets": {
            "protein_g": data.settings.protein_target_g,
            "water_ml": data.settings.water_target_ml,
            "bible_minutes": data.settings.bible_target_minutes,
            "exercise": normalize_targets(data.settings.exercise_targets),
        },
    }
