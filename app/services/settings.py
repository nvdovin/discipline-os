"""Settings read/update and full data export."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings as app_settings
from app.models import (
    BibleLog,
    BodyMeasurement,
    DailyLog,
    DailyReflection,
    ExerciseSet,
    Habit,
    Meal,
    Reminder,
    SleepLog,
    UserSettings,
    WaterLog,
    Workout,
)
from app.schemas import SettingsIn
from app.services.habits import get_settings
from app.services.plan import normalize_targets
from app.timeutils import (
    planned_sleep_minutes,
    valid_timezone,
)

TIMEZONE_OPTIONS = [
    {"value": "Europe/Kaliningrad", "label": "Калининград (UTC+2)"},
    {"value": "Europe/Moscow", "label": "Москва (UTC+3)"},
    {"value": "Europe/Minsk", "label": "Минск (UTC+3)"},
    {"value": "Europe/Kyiv", "label": "Киев (UTC+2/3)"},
    {"value": "Europe/Samara", "label": "Самара (UTC+4)"},
    {"value": "Asia/Yekaterinburg", "label": "Екатеринбург (UTC+5)"},
    {"value": "Asia/Omsk", "label": "Омск (UTC+6)"},
    {"value": "Asia/Krasnoyarsk", "label": "Красноярск (UTC+7)"},
    {"value": "Asia/Irkutsk", "label": "Иркутск (UTC+8)"},
    {"value": "Asia/Yakutsk", "label": "Якутск (UTC+9)"},
    {"value": "Asia/Vladivostok", "label": "Владивосток (UTC+10)"},
    {"value": "Asia/Magadan", "label": "Магадан (UTC+11)"},
    {"value": "Asia/Kamchatka", "label": "Камчатка (UTC+12)"},
    {"value": "Asia/Almaty", "label": "Алматы (UTC+5)"},
    {"value": "Asia/Tbilisi", "label": "Тбилиси (UTC+4)"},
    {"value": "Asia/Yerevan", "label": "Ереван (UTC+4)"},
    {"value": "Asia/Baku", "label": "Баку (UTC+4)"},
    {"value": "Asia/Tashkent", "label": "Ташкент (UTC+5)"},
    {"value": "Asia/Dubai", "label": "Дубай (UTC+4)"},
    {"value": "Europe/Berlin", "label": "Берлин (UTC+1/2)"},
    {"value": "Europe/London", "label": "Лондон (UTC+0/1)"},
    {"value": "America/New_York", "label": "Нью-Йорк (UTC−5/−4)"},
    {"value": "America/Los_Angeles", "label": "Лос-Анджелес (UTC−8/−7)"},
    {"value": "UTC", "label": "UTC"},
]


def _serialize_reminder(reminder: Reminder) -> dict[str, Any]:
    return {
        "key": reminder.key,
        "title": reminder.title,
        "time": reminder.time,
        "enabled": reminder.enabled,
    }


async def build_settings(session: AsyncSession) -> dict[str, Any]:
    settings = await get_settings(session)
    reminders = list(
        (
            await session.scalars(
                select(Reminder).order_by(Reminder.sort_order, Reminder.id)
            )
        ).all()
    )
    return {
        "profile": {
            "telegram_user_id": settings.telegram_user_id,
            "display_name": settings.display_name,
            "timezone": settings.timezone,
            "owner_configured": bool(app_settings.owner_telegram_id),
            "dev_mode": app_settings.dev_mode,
        },
        "schedule": {
            "wake_up_time": settings.wake_up_time,
            "bedtime": settings.bedtime,
            "meal_times": settings.meal_times or [],
            "target_sleep_minutes": planned_sleep_minutes(
                settings.bedtime, settings.wake_up_time
            ),
        },
        "targets": {
            "protein_target_g": settings.protein_target_g,
            "water_target_ml": settings.water_target_ml,
            "bible_target_minutes": settings.bible_target_minutes,
            "exercise_targets": normalize_targets(settings.exercise_targets),
        },
        "reminders": [_serialize_reminder(reminder) for reminder in reminders],
        "timezones": TIMEZONE_OPTIONS,
        "telegram": {
            "webapp_url": app_settings.webapp_url,
            "bot_configured": bool(app_settings.bot_token),
        },
        "app": {
            "version": app_settings.app_version,
            "environment": app_settings.environment,
        },
    }


async def update_settings(
    session: AsyncSession, payload: SettingsIn
) -> dict[str, Any]:
    settings = await get_settings(session)

    if payload.timezone is not None:
        if not valid_timezone(payload.timezone):
            raise ValueError("Неизвестный часовой пояс")
        settings.timezone = payload.timezone
    if payload.wake_up_time is not None:
        settings.wake_up_time = payload.wake_up_time
    if payload.bedtime is not None:
        settings.bedtime = payload.bedtime
    duration = planned_sleep_minutes(settings.bedtime, settings.wake_up_time)
    if not (240 <= duration <= 720):
        raise ValueError(
            "Целевой сон должен быть от 4 до 12 часов. Проверьте время подъёма и отбоя"
        )

    if payload.meal_times is not None:
        settings.meal_times = sorted(payload.meal_times)
    if payload.protein_target_g is not None:
        settings.protein_target_g = payload.protein_target_g
    if payload.water_target_ml is not None:
        settings.water_target_ml = payload.water_target_ml
    if payload.bible_target_minutes is not None:
        settings.bible_target_minutes = payload.bible_target_minutes

    if payload.exercise_targets is not None:
        current = normalize_targets(settings.exercise_targets)
        updates = payload.exercise_targets.model_dump(exclude_none=True)
        for key, value in updates.items():
            if key in current:
                current[key] = {**current[key], **value}
        settings.exercise_targets = normalize_targets(current)

    if payload.reminders is not None:
        existing = {
            reminder.key: reminder
            for reminder in (
                await session.scalars(select(Reminder))
            ).all()
        }
        for item in payload.reminders:
            reminder = existing.get(item.key)
            if reminder is None:
                raise ValueError(f"Неизвестное напоминание: {item.key}")
            reminder.time = item.time
            reminder.enabled = item.enabled

    await session.commit()
    return await build_settings(session)


def _value(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _row(obj: Any) -> dict[str, Any]:
    return {
        column.name: _value(getattr(obj, column.name))
        for column in obj.__table__.columns
    }


async def export_data(session: AsyncSession) -> dict[str, Any]:
    settings = await get_settings(session)
    habits = list((await session.scalars(select(Habit).order_by(Habit.id))).all())
    daily_logs = list(
        (await session.scalars(select(DailyLog).order_by(DailyLog.date))).all()
    )
    workouts = list(
        (
            await session.scalars(
                select(Workout)
                .options(selectinload(Workout.sets))
                .order_by(Workout.date)
            )
        ).all()
    )
    meals = list((await session.scalars(select(Meal).order_by(Meal.date))).all())
    water = list(
        (await session.scalars(select(WaterLog).order_by(WaterLog.date))).all()
    )
    measurements = list(
        (
            await session.scalars(
                select(BodyMeasurement).order_by(BodyMeasurement.date)
            )
        ).all()
    )
    sleep = list(
        (await session.scalars(select(SleepLog).order_by(SleepLog.date))).all()
    )
    bible = list(
        (await session.scalars(select(BibleLog).order_by(BibleLog.date))).all()
    )
    reflections = list(
        (
            await session.scalars(
                select(DailyReflection).order_by(DailyReflection.date)
            )
        ).all()
    )
    reminders = list(
        (await session.scalars(select(Reminder).order_by(Reminder.sort_order))).all()
    )

    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "app": "Discipline OS",
        "version": app_settings.app_version,
        "settings": _row(settings),
        "habits": [_row(item) for item in habits],
        "daily_logs": [_row(item) for item in daily_logs],
        "workouts": [
            {**_row(item), "sets": [_row(exercise) for exercise in item.sets]}
            for item in workouts
        ],
        "exercise_sets": [
            _row(exercise) for item in workouts for exercise in item.sets
        ],
        "meals": [_row(item) for item in meals],
        "water_logs": [_row(item) for item in water],
        "body_measurements": [_row(item) for item in measurements],
        "sleep_logs": [_row(item) for item in sleep],
        "bible_logs": [_row(item) for item in bible],
        "daily_reflections": [_row(item) for item in reflections],
        "reminders": [_row(item) for item in reminders],
    }
