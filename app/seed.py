"""Idempotent seed data for a fresh database."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Habit, Reminder, UserSettings
from app.services.plan import DEFAULT_EXERCISE_TARGETS, normalize_targets

DEFAULT_HABITS = [
    {
        "key": "sleep",
        "name": "Сон",
        "category": "sleep",
        "target": "7–8 часов",
        "icon": "moon",
        "weight": 20,
        "sort_order": 10,
    },
    {
        "key": "exercise",
        "name": "Тренировка",
        "category": "fitness",
        "target": "Каждый день",
        "icon": "dumbbell",
        "weight": 20,
        "sort_order": 20,
    },
    {
        "key": "nutrition",
        "name": "Питание",
        "category": "nutrition",
        "target": "2 приёма",
        "icon": "apple",
        "weight": 20,
        "sort_order": 30,
    },
    {
        "key": "bible",
        "name": "Библия",
        "category": "bible",
        "target": "30–45 минут",
        "icon": "book",
        "weight": 20,
        "sort_order": 40,
    },
    {
        "key": "priority",
        "name": "Главное дело",
        "category": "productivity",
        "target": "1 приоритет",
        "icon": "target",
        "weight": 20,
        "sort_order": 50,
    },
]

DEFAULT_REMINDERS = [
    {
        "key": "morning",
        "title": "Доброе утро",
        "time": "06:00",
        "sort_order": 10,
    },
    {
        "key": "bible",
        "title": "Чтение Библии",
        "time": "06:05",
        "sort_order": 20,
    },
    {
        "key": "exercise",
        "title": "Тренировка",
        "time": "06:45",
        "sort_order": 30,
    },
    {
        "key": "meal_1",
        "title": "Первый приём пищи",
        "time": "11:00",
        "sort_order": 40,
    },
    {
        "key": "meal_2",
        "title": "Второй приём пищи",
        "time": "17:00",
        "sort_order": 50,
    },
    {
        "key": "checkin",
        "title": "Вечерний чек-ин",
        "time": "21:00",
        "sort_order": 60,
    },
    {
        "key": "sleep",
        "title": "Подготовка ко сну",
        "time": "21:30",
        "sort_order": 70,
    },
]


async def seed_defaults(session: AsyncSession) -> None:
    settings = await session.get(UserSettings, 1)
    if settings is None:
        settings = UserSettings(
            id=1,
            timezone="Europe/Moscow",
            wake_up_time="06:00",
            bedtime="22:00",
            meal_times=["11:00", "17:00"],
            protein_target_g=140,
            water_target_ml=2000,
            bible_target_minutes=30,
            exercise_targets=normalize_targets(DEFAULT_EXERCISE_TARGETS),
        )
        session.add(settings)
    elif not settings.exercise_targets:
        settings.exercise_targets = normalize_targets(DEFAULT_EXERCISE_TARGETS)

    existing_habits = {
        habit.key for habit in (await session.scalars(select(Habit))).all()
    }
    for item in DEFAULT_HABITS:
        if item["key"] not in existing_habits:
            session.add(Habit(**item, enabled=True, frequency="daily"))

    existing_reminders = {
        reminder.key for reminder in (await session.scalars(select(Reminder))).all()
    }
    for item in DEFAULT_REMINDERS:
        if item["key"] not in existing_reminders:
            session.add(Reminder(**item, enabled=True))

    await session.commit()
