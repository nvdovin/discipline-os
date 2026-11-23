"""Weekly training plan and target calculation.

The plan is intentionally conservative: comfortable volumes, no training to
failure, and active recovery days that count as successful activity days.
Every target is configurable through ``UserSettings.exercise_targets``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import ceil
from typing import Any

DEFAULT_EXERCISE_TARGETS: dict[str, dict[str, int]] = {
    "pushups": {"sets": 3, "reps": 10},
    "pullups": {"sets": 5, "reps": 5},
    "squats": {"sets": 3, "reps": 15},
    "lunges": {"sets": 3, "reps": 10},
    "plank": {"sets": 3, "duration_seconds": 40},
    "walk": {"sets": 1, "duration_seconds": 1200},
    "mobility": {"sets": 1, "duration_seconds": 600},
    "stretch": {"sets": 1, "duration_seconds": 600},
}

EXERCISE_NAMES: dict[str, str] = {
    "pushups": "Отжимания",
    "pullups": "Подтягивания",
    "squats": "Приседания",
    "lunges": "Выпады",
    "plank": "Планка",
    "walk": "Прогулка",
    "mobility": "Мобилити",
    "stretch": "Растяжка",
}


@dataclass(frozen=True)
class ExerciseSpec:
    key: str
    name: str
    kind: str  # "reps" | "duration"
    sets: int
    reps: int | None = None
    duration_seconds: int | None = None
    rest_seconds: int = 60
    note: str = ""
    unit: str = "повт."
    scale: float = 1.0


@dataclass(frozen=True)
class DayPlan:
    key: str
    title: str
    subtitle: str
    kind: str  # "strength" | "recovery" | "light"
    exercises: list[ExerciseSpec] = field(default_factory=list)


def _pushups(scale: float = 1.0) -> ExerciseSpec:
    return ExerciseSpec(
        "pushups",
        "Отжимания",
        "reps",
        3,
        10,
        rest_seconds=90,
        note="Рабочий объём, не до отказа",
        scale=scale,
    )


def _pullups(scale: float = 1.0) -> ExerciseSpec:
    return ExerciseSpec(
        "pullups",
        "Подтягивания",
        "reps",
        5,
        5,
        rest_seconds=120,
        note="Комфортный объём, всего около 25–30 за день",
        scale=scale,
    )


def _squats(scale: float = 1.0) -> ExerciseSpec:
    return ExerciseSpec(
        "squats", "Приседания", "reps", 3, 15, rest_seconds=60, scale=scale
    )


def _lunges() -> ExerciseSpec:
    return ExerciseSpec(
        "lunges", "Выпады", "reps", 3, 10, rest_seconds=60, note="На каждую ногу"
    )


def _plank() -> ExerciseSpec:
    return ExerciseSpec(
        "plank",
        "Планка",
        "duration",
        3,
        duration_seconds=40,
        rest_seconds=60,
        unit="сек",
        note="Держите ровное дыхание",
    )


def _walk(minutes: int = 20, scale: float = 1.0) -> ExerciseSpec:
    return ExerciseSpec(
        "walk",
        "Прогулка",
        "duration",
        1,
        duration_seconds=minutes * 60,
        rest_seconds=0,
        unit="мин",
        scale=scale,
    )


def _mobility() -> ExerciseSpec:
    return ExerciseSpec(
        "mobility", "Мобилити", "duration", 1, duration_seconds=600, unit="мин"
    )


def _stretch(minutes: int = 10, scale: float = 1.0) -> ExerciseSpec:
    return ExerciseSpec(
        "stretch",
        "Растяжка",
        "duration",
        1,
        duration_seconds=minutes * 60,
        unit="мин",
        scale=scale,
    )


WEEKLY_PLAN: dict[int, DayPlan] = {
    0: DayPlan(
        "strength_a",
        "Сила A",
        "Верх тела и кор",
        "strength",
        [_pushups(), _pullups(), _squats(), _plank()],
    ),
    1: DayPlan(
        "recovery",
        "Активное восстановление",
        "Движение без нагрузки",
        "recovery",
        [_walk(), _mobility(), _stretch()],
    ),
    2: DayPlan(
        "strength_b",
        "Сила B",
        "Верх тела, ноги и кор",
        "strength",
        [_pushups(), _pullups(), _lunges(), _plank()],
    ),
    3: DayPlan(
        "recovery",
        "Активное восстановление",
        "Прогулка и мобилити",
        "recovery",
        [_walk(), _mobility()],
    ),
    4: DayPlan(
        "strength_a",
        "Сила A",
        "Повтор понедельника",
        "strength",
        [_pushups(), _pullups(), _squats(), _plank()],
    ),
    5: DayPlan(
        "light",
        "Лёгкая активность",
        "Всё тело без спешки",
        "light",
        [_pushups(0.7), _squats(0.8), _walk(15, 0.75), _stretch(10, 0.8)],
    ),
    6: DayPlan(
        "recovery",
        "Восстановление",
        "Прогулка и растяжка",
        "recovery",
        [_walk(20), _stretch(10)],
    ),
}


def day_plan_for(weekday: int) -> DayPlan:
    return WEEKLY_PLAN[weekday % 7]


def _merge_targets(
    spec: ExerciseSpec, overrides: dict[str, Any] | None
) -> tuple[int, int | None, int | None]:
    """Return (sets, reps, duration_seconds) after user overrides and scaling."""
    override = (overrides or {}).get(spec.key) or {}
    sets = int(override.get("sets", spec.sets))
    reps = int(override.get("reps", spec.reps or 0)) if spec.kind == "reps" else None
    duration = (
        int(override.get("duration_seconds", spec.duration_seconds or 0))
        if spec.kind == "duration"
        else None
    )

    if spec.scale != 1.0:
        sets = max(1, round(sets * spec.scale))
        if reps is not None:
            reps = max(1, round(reps * spec.scale))
        if duration is not None:
            duration = max(5, round(duration * spec.scale))

    return max(1, sets), reps, duration


def _minimum_target(
    sets: int, reps: int | None, duration: int | None
) -> tuple[int, int | None, int | None]:
    """A genuinely small workout that keeps the habit alive."""
    min_sets = 1
    min_reps = max(2, ceil((reps or 0) / 2)) if reps is not None else None
    min_duration = max(5, round((duration or 0) / 2)) if duration is not None else None
    return min_sets, min_reps, min_duration


def effective_exercises(
    weekday: int,
    overrides: dict[str, Any] | None = None,
    mode: str = "full",
) -> list[dict[str, Any]]:
    plan = day_plan_for(weekday)
    result: list[dict[str, Any]] = []
    for spec in plan.exercises:
        sets, reps, duration = _merge_targets(spec, overrides)
        if mode == "minimum":
            sets, reps, duration = _minimum_target(sets, reps, duration)
        result.append(
            {
                "key": spec.key,
                "name": spec.name,
                "kind": spec.kind,
                "sets": sets,
                "reps": reps,
                "duration_seconds": duration,
                "rest_seconds": spec.rest_seconds,
                "note": spec.note,
                "unit": spec.unit,
                "target": target_label(spec.kind, sets, reps, duration),
            }
        )
    return result


def target_label(
    kind: str, sets: int, reps: int | None, duration_seconds: int | None
) -> str:
    if kind == "reps":
        return f"{sets} × {reps}"
    seconds = duration_seconds or 0
    if seconds >= 60:
        minutes = seconds / 60
        minutes_label = (
            f"{int(minutes)}" if minutes == int(minutes) else f"{minutes:.1f}"
        )
        return f"{minutes_label} мин" if sets == 1 else f"{sets} × {minutes_label} мин"
    return f"{sets} × {seconds} сек" if sets > 1 else f"{seconds} сек"


def exercise_by_key(weekday: int, key: str) -> ExerciseSpec | None:
    for spec in day_plan_for(weekday).exercises:
        if spec.key == key:
            return spec
    return None


def workout_title(workout_type: str) -> str:
    for plan in WEEKLY_PLAN.values():
        if plan.key == workout_type:
            return plan.title
    if workout_type == "custom":
        return "Своя активность"
    return "Тренировка"


def normalize_targets(raw: dict[str, Any] | None) -> dict[str, dict[str, int]]:
    """Return a complete, validated target dict.

    Unknown keys are dropped, missing keys fall back to defaults. Numeric
    ranges are enforced by the API schema; this function is a last-resort
    sanitizer for values read from an older database.
    """
    result: dict[str, dict[str, int]] = {}
    for key, default in DEFAULT_EXERCISE_TARGETS.items():
        value = (raw or {}).get(key) or {}
        if "duration_seconds" in default:
            duration = value.get("duration_seconds", default["duration_seconds"])
            sets = value.get("sets", default["sets"])
            result[key] = {
                "sets": max(1, min(10, int(sets))),
                "duration_seconds": max(5, min(7200, int(duration))),
            }
        else:
            reps = value.get("reps", default["reps"])
            sets = value.get("sets", default["sets"])
            result[key] = {
                "sets": max(1, min(10, int(sets))),
                "reps": max(1, min(100, int(reps))),
            }
    return result
