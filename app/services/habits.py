"""Daily habit state, derived completion and streak calculations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    BibleLog,
    BodyMeasurement,
    DailyLog,
    DailyReflection,
    ExerciseSet,
    Habit,
    Meal,
    SleepLog,
    UserSettings,
    WaterLog,
    Workout,
)
from app.services.plan import (
    day_plan_for,
    effective_exercises,
    normalize_targets,
    workout_title,
)
from app.timeutils import (
    circular_minute_delta,
    date_range,
    format_minutes,
    human_date_ru,
    local_now,
    local_today,
    planned_sleep_minutes,
    weekday_ru,
    weekday_short_ru,
)

SUCCESS_THRESHOLD = 60
HABIT_KEYS = ("sleep", "exercise", "nutrition", "bible", "priority")
SLEEP_SCHEDULE_TOLERANCE_MINUTES = 45


@dataclass
class RangeData:
    settings: UserSettings
    habits: list[Habit]
    logs: dict[tuple[str, date], DailyLog] = field(default_factory=dict)
    workouts: dict[date, Workout] = field(default_factory=dict)
    meals: dict[date, list[Meal]] = field(default_factory=dict)
    water: dict[date, int] = field(default_factory=dict)
    sleep: dict[date, SleepLog] = field(default_factory=dict)
    bible: dict[date, BibleLog] = field(default_factory=dict)
    reflections: dict[date, DailyReflection] = field(default_factory=dict)

    def habit(self, key: str) -> Habit | None:
        return next((habit for habit in self.habits if habit.key == key), None)


async def get_settings(session: AsyncSession) -> UserSettings:
    settings = await session.get(UserSettings, 1)
    if settings is None:
        settings = UserSettings(id=1)
        session.add(settings)
        await session.flush()
    return settings


async def load_range(session: AsyncSession, start: date, end: date) -> RangeData:
    settings = await get_settings(session)
    habits = list(
        (
            await session.scalars(
                select(Habit).where(Habit.enabled.is_(True)).order_by(Habit.sort_order)
            )
        ).all()
    )

    log_rows = (
        await session.execute(
            select(DailyLog, Habit.key)
            .join(Habit, DailyLog.habit_id == Habit.id)
            .where(DailyLog.date.between(start, end))
        )
    ).all()
    logs = {(key, log.date): log for log, key in log_rows}

    workouts = list(
        (
            await session.scalars(
                select(Workout)
                .where(Workout.date.between(start, end))
                .options(selectinload(Workout.sets))
            )
        ).all()
    )
    workout_map = {workout.date: workout for workout in workouts}

    meal_rows = list(
        (
            await session.scalars(
                select(Meal)
                .where(Meal.date.between(start, end))
                .order_by(Meal.date, Meal.time, Meal.id)
            )
        ).all()
    )
    meals: dict[date, list[Meal]] = {}
    for meal in meal_rows:
        meals.setdefault(meal.date, []).append(meal)

    water_rows = (
        await session.execute(
            select(WaterLog.date, func.sum(WaterLog.amount_ml))
            .where(WaterLog.date.between(start, end))
            .group_by(WaterLog.date)
        )
    ).all()
    water = {day: int(total or 0) for day, total in water_rows}

    sleep_logs = list(
        (
            await session.scalars(
                select(SleepLog).where(SleepLog.date.between(start, end))
            )
        ).all()
    )
    bible_logs = list(
        (
            await session.scalars(
                select(BibleLog).where(BibleLog.date.between(start, end))
            )
        ).all()
    )
    reflections = list(
        (
            await session.scalars(
                select(DailyReflection).where(DailyReflection.date.between(start, end))
            )
        ).all()
    )

    return RangeData(
        settings=settings,
        habits=habits,
        logs=logs,
        workouts=workout_map,
        meals=meals,
        water=water,
        sleep={log.date: log for log in sleep_logs},
        bible={log.date: log for log in bible_logs},
        reflections={reflection.date: reflection for reflection in reflections},
    )


def reflection_dict(reflection: DailyReflection | None) -> dict[str, Any]:
    if reflection is None:
        return {
            "main_priority": None,
            "priority_completed": False,
            "secondary_tasks": [],
            "positive_result": None,
            "difficulty": None,
            "tomorrow_priority": None,
        }
    tasks = []
    for index, task in enumerate(reflection.secondary_tasks or []):
        if isinstance(task, dict):
            tasks.append(
                {
                    "id": str(task.get("id") or f"task-{index + 1}"),
                    "text": str(task.get("text") or ""),
                    "done": bool(task.get("done")),
                }
            )
    return {
        "main_priority": reflection.main_priority,
        "priority_completed": reflection.priority_completed,
        "secondary_tasks": tasks,
        "positive_result": reflection.positive_result,
        "difficulty": reflection.difficulty,
        "tomorrow_priority": reflection.tomorrow_priority,
    }


def _sleep_on_schedule(log: SleepLog, settings: UserSettings) -> bool:
    return (
        circular_minute_delta(log.bedtime, settings.bedtime)
        <= SLEEP_SCHEDULE_TOLERANCE_MINUTES
        and circular_minute_delta(log.wake_up_time, settings.wake_up_time)
        <= SLEEP_SCHEDULE_TOLERANCE_MINUTES
    )


def _exercise_state(
    day: date, data: RangeData, workout: Workout | None
) -> dict[str, Any]:
    overrides = normalize_targets(data.settings.exercise_targets)
    plan = day_plan_for(day.weekday())
    mode = workout.mode if workout else "full"
    exercises = effective_exercises(day.weekday(), overrides, mode)
    target_sets = sum(exercise["sets"] for exercise in exercises)
    done_sets = len(workout.sets) if workout else 0
    completed = bool(workout and workout.status == "completed")
    if completed:
        progress = 1.0
    else:
        progress = min(1.0, done_sets / target_sets) if target_sets else 0.0
    if workout:
        detail = f"{workout_title(workout.workout_type)} · {done_sets} из {target_sets} подходов"
        if completed:
            # Short enough for one line on a 375 px screen; the workout type
            # is already visible on the fitness screen and in the quick stats.
            detail = "Тренировка засчитана"
    else:
        detail = f"{plan.title} · 0 из {target_sets} подходов"
    return {
        "type": plan.key,
        "title": plan.title,
        "subtitle": plan.subtitle,
        "kind": plan.kind,
        "mode": mode,
        "status": workout.status if workout else "planned",
        "completed": completed,
        "sets_done": done_sets,
        "sets_target": target_sets,
        "progress": round(progress, 3),
        "detail": detail,
        "workout_id": workout.id if workout else None,
    }


def _habit_progress(
    key: str,
    day: date,
    data: RangeData,
    settings: UserSettings,
    workout: Workout | None,
    meals: list[Meal],
    water_ml: int,
    sleep_log: SleepLog | None,
    bible_log: BibleLog | None,
    reflection: DailyReflection | None,
) -> tuple[bool, float, str, str]:
    """Return (auto_completed, progress, detail, value)."""
    if key == "sleep":
        target = planned_sleep_minutes(settings.bedtime, settings.wake_up_time)
        if sleep_log:
            return (
                True,
                min(1.0, sleep_log.duration_minutes / target) if target else 0.0,
                f"{sleep_log.bedtime} → {sleep_log.wake_up_time} · {format_minutes(sleep_log.duration_minutes)}",
                format_minutes(sleep_log.duration_minutes),
            )
        return (
            False,
            0.0,
            f"Цель {settings.bedtime} → {settings.wake_up_time}",
            "—",
        )

    if key == "exercise":
        state = _exercise_state(day, data, workout)
        return state["completed"], state["progress"], state["detail"], (
            "Готово" if state["completed"] else f"{state['sets_done']}/{state['sets_target']}"
        )

    if key == "nutrition":
        target = max(1, len(settings.meal_times or []))
        count = len(meals)
        protein = sum(meal.protein_g or 0 for meal in meals)
        detail = f"{count} из {target} приёмов"
        if protein:
            detail += f" · {protein:.0f} г белка"
        return (
            count >= target,
            min(1.0, count / target),
            detail,
            f"{count}/{target}",
        )

    if key == "bible":
        target = settings.bible_target_minutes
        minutes = bible_log.duration_minutes if bible_log else 0
        if bible_log:
            return (
                minutes >= target,
                min(1.0, minutes / target) if target else 0.0,
                f"{minutes} из {target} мин",
                f"{minutes} мин",
            )
        return (
            False,
            0.0,
            f"Цель {target} мин",
            "—",
        )

    if key == "priority":
        priority = reflection.main_priority if reflection else None
        completed = bool(reflection and reflection.priority_completed and priority)
        if completed:
            return True, 1.0, "Главное дело выполнено", "Готово"
        if priority:
            return False, 0.5, priority, "В работе"
        return False, 0.0, "Назначьте одно главное дело", "—"

    return False, 0.0, "", "—"


def build_day_state(day: date, data: RangeData) -> dict[str, Any]:
    settings = data.settings
    workout = data.workouts.get(day)
    meals = data.meals.get(day, [])
    water_ml = data.water.get(day, 0)
    sleep_log = data.sleep.get(day)
    bible_log = data.bible.get(day)
    reflection = data.reflections.get(day)

    habits: list[dict[str, Any]] = []
    completed_weight = 0
    total_weight = 0
    for habit in data.habits:
        if habit.key not in HABIT_KEYS:
            continue
        auto_completed, progress, detail, value = _habit_progress(
            habit.key,
            day,
            data,
            settings,
            workout,
            meals,
            water_ml,
            sleep_log,
            bible_log,
            reflection,
        )
        explicit = data.logs.get((habit.key, day))
        if habit.key != "priority" and explicit is not None:
            completed = explicit.completed
            source = "manual"
        else:
            completed = auto_completed
            source = "auto" if auto_completed else "none"
        weight = habit.weight or 20
        total_weight += weight
        if completed:
            completed_weight += weight
        habits.append(
            {
                "key": habit.key,
                "name": habit.name,
                "category": habit.category,
                "target": habit.target,
                "icon": habit.icon,
                "weight": weight,
                "completed": completed,
                "progress": round(max(0.0, min(1.0, progress)), 3),
                "detail": detail,
                "value": value,
                "source": source,
            }
        )

    completion = round(completed_weight / total_weight * 100) if total_weight else 0
    completed_count = sum(1 for habit in habits if habit["completed"])

    exercise_state = _exercise_state(day, data, workout)
    protein = sum(meal.protein_g or 0 for meal in meals)
    calories = sum(meal.calories or 0 for meal in meals)
    nutrition_missing = any(
        meal.calories is None or meal.protein_g is None for meal in meals
    )
    sleep_target = planned_sleep_minutes(settings.bedtime, settings.wake_up_time)

    return {
        "date": day.isoformat(),
        "weekday": weekday_ru(day),
        "weekday_short": weekday_short_ru(day),
        "human_date": human_date_ru(day),
        "completion": completion,
        "completed_count": completed_count,
        "habit_count": len(habits),
        "success": completion >= SUCCESS_THRESHOLD,
        "habits": habits,
        "quick": {
            "sleep_minutes": sleep_log.duration_minutes if sleep_log else None,
            "sleep_target_minutes": sleep_target,
            "protein_g": round(protein, 1),
            "protein_target_g": settings.protein_target_g,
            "bible_minutes": bible_log.duration_minutes if bible_log else 0,
            "bible_target_minutes": settings.bible_target_minutes,
            "water_ml": water_ml,
            "water_target_ml": settings.water_target_ml,
            "exercise_title": exercise_state["title"],
            "exercise_done_sets": exercise_state["sets_done"],
            "exercise_target_sets": exercise_state["sets_target"],
        },
        "sleep": {
            "bedtime": sleep_log.bedtime if sleep_log else None,
            "wake_up_time": sleep_log.wake_up_time if sleep_log else None,
            "duration_minutes": sleep_log.duration_minutes if sleep_log else None,
            "target_minutes": sleep_target,
            "on_schedule": _sleep_on_schedule(sleep_log, settings)
            if sleep_log
            else False,
        },
        "exercise": exercise_state,
        "nutrition": {
            "meals_count": len(meals),
            "meals_target": max(1, len(settings.meal_times or [])),
            "protein_g": round(protein, 1),
            "calories": calories,
            "water_ml": water_ml,
            "has_missing_values": nutrition_missing,
        },
        "bible": {
            "minutes": bible_log.duration_minutes if bible_log else 0,
            "target_minutes": settings.bible_target_minutes,
            "notes": bible_log.notes if bible_log else None,
        },
        "priority": reflection_dict(reflection),
    }


def build_states(data: RangeData, start: date, end: date) -> list[dict[str, Any]]:
    return [build_day_state(day, data) for day in date_range(end, (end - start).days + 1)]


def _streak_for(states: list[dict[str, Any]], key: str | None = None) -> tuple[int, int]:
    """Return (current, best) streaks for the whole day or a single habit."""
    if not states:
        return 0, 0
    by_date = {date.fromisoformat(state["date"]): state for state in states}
    ordered = sorted(by_date)
    last = ordered[-1]

    def ok(day: date) -> bool:
        state = by_date.get(day)
        if state is None:
            return False
        if key is None:
            return state["success"]
        habit = next((h for h in state["habits"] if h["key"] == key), None)
        return bool(habit and habit["completed"])

    # The current streak does not reset in the middle of today: if today is
    # not complete yet, count backwards from yesterday.
    anchor = last if ok(last) else last - timedelta(days=1)
    current = 0
    cursor = anchor
    while ok(cursor):
        current += 1
        cursor -= timedelta(days=1)

    best = 0
    running = 0
    for day in ordered:
        if ok(day):
            running += 1
            best = max(best, running)
        else:
            running = 0
    return current, max(best, current)


def compute_streaks(states: list[dict[str, Any]]) -> dict[str, Any]:
    current, best = _streak_for(states)
    habit_streaks = {}
    for key in HABIT_KEYS:
        habit_current, habit_best = _streak_for(states, key)
        habit_streaks[key] = {"current": habit_current, "best": habit_best}
    return {
        "current": current,
        "best": best,
        "threshold": SUCCESS_THRESHOLD,
        "habits": habit_streaks,
    }


async def latest_measurement(
    session: AsyncSession, day: date
) -> BodyMeasurement | None:
    return await session.scalar(
        select(BodyMeasurement)
        .where(BodyMeasurement.date <= day)
        .order_by(BodyMeasurement.date.desc())
        .limit(1)
    )


async def build_dashboard(session: AsyncSession, day: date) -> dict[str, Any]:
    start = day - timedelta(days=119)
    data = await load_range(session, start, day)
    states = build_states(data, start, day)
    today_state = states[-1]
    streaks = compute_streaks(states)
    measurement = await latest_measurement(session, day)
    settings = data.settings

    today = local_today(settings.timezone)
    if day == today:
        hour = local_now(settings.timezone).hour
        if 5 <= hour < 12:
            greeting = "Доброе утро"
        elif 12 <= hour < 18:
            greeting = "Добрый день"
        elif 18 <= hour < 23:
            greeting = "Добрый вечер"
        else:
            greeting = "Спокойной ночи"
    else:
        greeting = "Итоги дня"

    return {
        **today_state,
        "greeting": greeting,
        "streak": {
            "current": streaks["current"],
            "best": streaks["best"],
            "threshold": streaks["threshold"],
        },
        "habit_streaks": streaks["habits"],
        "weight_kg": measurement.weight_kg if measurement else None,
        "settings": {
            "timezone": settings.timezone,
            "wake_up_time": settings.wake_up_time,
            "bedtime": settings.bedtime,
            "meal_times": settings.meal_times,
            "protein_target_g": settings.protein_target_g,
            "water_target_ml": settings.water_target_ml,
            "bible_target_minutes": settings.bible_target_minutes,
            "exercise_targets": normalize_targets(settings.exercise_targets),
        },
    }


async def get_day_state(session: AsyncSession, day: date) -> dict[str, Any]:
    data = await load_range(session, day, day)
    return build_day_state(day, data)


async def toggle_habit(
    session: AsyncSession, key: str, day: date, completed: bool | None = None
) -> dict[str, Any]:
    settings = await get_settings(session)
    today = local_today(settings.timezone)
    if day > today:
        raise ValueError("Нельзя отмечать будущие дни")
    if key not in HABIT_KEYS:
        raise ValueError("Неизвестная привычка")

    if key == "priority":
        reflection = await session.scalar(
            select(DailyReflection).where(DailyReflection.date == day)
        )
        if reflection is None:
            reflection = DailyReflection(date=day, secondary_tasks=[])
            session.add(reflection)
            await session.flush()
        target = not reflection.priority_completed if completed is None else completed
        if target and not reflection.main_priority:
            raise ValueError("Сначала назначьте главное дело на день")
        reflection.priority_completed = target
        await session.commit()
    else:
        habit = await session.scalar(select(Habit).where(Habit.key == key))
        if habit is None:
            raise ValueError("Привычка не найдена")
        log = await session.scalar(
            select(DailyLog).where(
                DailyLog.habit_id == habit.id, DailyLog.date == day
            )
        )
        if log is None:
            log = DailyLog(
                habit_id=habit.id,
                date=day,
                completed=bool(completed) if completed is not None else True,
                source="user",
            )
            session.add(log)
        else:
            log.completed = not log.completed if completed is None else completed
            log.source = "user"
        await session.commit()

    return await get_day_state(session, day)


def nutrition_totals(meals: list[Meal]) -> dict[str, Any]:
    return {
        "calories": sum(meal.calories or 0 for meal in meals),
        "protein_g": round(sum(meal.protein_g or 0 for meal in meals), 1),
        "carbs_g": round(sum(meal.carbs_g or 0 for meal in meals), 1),
        "fats_g": round(sum(meal.fats_g or 0 for meal in meals), 1),
        "has_missing_values": any(
            meal.calories is None or meal.protein_g is None for meal in meals
        ),
    }


def workout_sets_count(workout: Workout | None) -> int:
    return len(workout.sets) if workout else 0


def set_summary(sets: list[ExerciseSet]) -> list[dict[str, Any]]:
    return [
        {
            "id": item.id,
            "exercise_key": item.exercise_key,
            "exercise_name": item.exercise_name,
            "set_number": item.set_number,
            "repetitions": item.repetitions,
            "duration_seconds": item.duration_seconds,
            "rest_seconds": item.rest_seconds,
        }
        for item in sets
    ]
