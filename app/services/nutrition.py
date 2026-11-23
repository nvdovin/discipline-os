"""Meals, hydration, body measurements and nutrition trends."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BodyMeasurement, Meal, WaterLog
from app.services.habits import get_settings, nutrition_totals
from app.timeutils import (
    date_range,
    local_now,
    local_today,
    parse_hhmm,
    weekday_short_ru,
)

MAX_MEAL_CALORIES = 5000
MAX_MEAL_MACRO = 500
MAX_WATER_ML = 3000
MAX_DAILY_WATER_ML = 10000


def _serialize_meal(meal: Meal) -> dict[str, Any]:
    return {
        "id": meal.id,
        "date": meal.date.isoformat(),
        "time": meal.time,
        "description": meal.description,
        "calories": meal.calories,
        "protein_g": meal.protein_g,
        "carbs_g": meal.carbs_g,
        "fats_g": meal.fats_g,
    }


def _serialize_measurement(item: BodyMeasurement | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        "date": item.date.isoformat(),
        "weight_kg": item.weight_kg,
        "waist_cm": item.waist_cm,
    }


def _delta(latest: float | None, earlier: float | None) -> float | None:
    if latest is None or earlier is None:
        return None
    return round(latest - earlier, 1)


async def build_nutrition(
    session: AsyncSession, day: date, days: int = 30
) -> dict[str, Any]:
    settings = await get_settings(session)
    start = day - timedelta(days=max(days, 30) - 1)
    meal_rows = list(
        (
            await session.scalars(
                select(Meal)
                .where(Meal.date.between(start, day))
                .order_by(Meal.date, Meal.time, Meal.id)
            )
        ).all()
    )
    today_meals = [meal for meal in meal_rows if meal.date == day]
    meals_by_day: dict[date, list[Meal]] = {}
    for meal in meal_rows:
        meals_by_day.setdefault(meal.date, []).append(meal)

    water_rows = list(
        (
            await session.scalars(
                select(WaterLog)
                .where(WaterLog.date == day)
                .order_by(WaterLog.id)
            )
        ).all()
    )
    water_total = sum(item.amount_ml for item in water_rows)

    measurements = list(
        (
            await session.scalars(
                select(BodyMeasurement)
                .where(BodyMeasurement.date.between(start, day))
                .order_by(BodyMeasurement.date)
            )
        ).all()
    )
    latest_measurement = measurements[-1] if measurements else None
    # A delta needs two distinct measurement dates. Using the latest item as
    # the "earlier" value would otherwise render a misleading 0 kg change.
    month_measurement = (
        next(
            (
                item
                for item in measurements
                if item.date >= day - timedelta(days=30)
                and item.date < latest_measurement.date
            ),
            None,
        )
        if latest_measurement is not None
        else None
    )

    target_meals = max(1, len(settings.meal_times or []))
    week_start = day - timedelta(days=6)
    week_days = date_range(day, 7)
    protein_series = []
    complete_days = 0
    logged_days = 0
    for current in week_days:
        meals = meals_by_day.get(current, [])
        protein = round(sum(meal.protein_g or 0 for meal in meals), 1)
        complete = len(meals) >= target_meals
        if meals:
            logged_days += 1
        if complete:
            complete_days += 1
        protein_series.append(
            {
                "date": current.isoformat(),
                "label": weekday_short_ru(current),
                "protein_g": protein,
                "target_g": settings.protein_target_g,
                "complete": complete,
                "has_meals": bool(meals),
            }
        )

    weight_series = [
        {
            "date": item.date.isoformat(),
            "label": weekday_short_ru(item.date),
            "value": item.weight_kg,
        }
        for item in measurements
        if item.weight_kg is not None
    ]
    waist_series = [
        {
            "date": item.date.isoformat(),
            "label": weekday_short_ru(item.date),
            "value": item.waist_cm,
        }
        for item in measurements
        if item.waist_cm is not None
    ]

    meal_times = settings.meal_times or []
    return {
        "date": day.isoformat(),
        "meals": [_serialize_meal(meal) for meal in today_meals],
        "totals": nutrition_totals(today_meals),
        "targets": {
            "protein_g": settings.protein_target_g,
            "water_ml": settings.water_target_ml,
            "meals": target_meals,
            "meal_times": meal_times,
            "eating_window": {
                "start": meal_times[0] if meal_times else None,
                "end": meal_times[-1] if meal_times else None,
            },
        },
        "water": {
            "total_ml": water_total,
            "target_ml": settings.water_target_ml,
            "entries": [
                {
                    "id": item.id,
                    "amount_ml": item.amount_ml,
                    "created_at": item.created_at.isoformat(),
                }
                for item in water_rows
            ],
        },
        "protein_series": protein_series,
        "consistency": {
            "days": 7,
            "logged": logged_days,
            "complete": complete_days,
            "pct": round(complete_days / 7 * 100),
            "week_start": week_start.isoformat(),
        },
        "measurements": {
            "latest": _serialize_measurement(latest_measurement),
            "weight_series": weight_series,
            "waist_series": waist_series,
            "weight_delta_30": _delta(
                latest_measurement.weight_kg if latest_measurement else None,
                month_measurement.weight_kg if month_measurement else None,
            ),
            "waist_delta_30": _delta(
                latest_measurement.waist_cm if latest_measurement else None,
                month_measurement.waist_cm if month_measurement else None,
            ),
        },
    }


async def add_meal(
    session: AsyncSession,
    day: date,
    description: str,
    *,
    time: str | None = None,
    calories: int | None = None,
    protein_g: float | None = None,
    carbs_g: float | None = None,
    fats_g: float | None = None,
) -> Meal:
    settings = await get_settings(session)
    if day > local_today(settings.timezone):
        raise ValueError("Нельзя записывать будущий приём пищи")
    description = (description or "").strip()
    if not description:
        raise ValueError("Опишите приём пищи")
    if len(description) > 300:
        raise ValueError("Описание слишком длинное")
    if calories is not None and not (0 <= calories <= MAX_MEAL_CALORIES):
        raise ValueError("Калории вне допустимого диапазона")
    for value in (protein_g, carbs_g, fats_g):
        if value is not None and not (0 <= value <= MAX_MEAL_MACRO):
            raise ValueError("Значение БЖУ вне допустимого диапазона")
    if time is None:
        time = local_now(settings.timezone).strftime("%H:%M")
    parse_hhmm(time)

    meal = Meal(
        date=day,
        time=time,
        description=description,
        calories=calories,
        protein_g=round(protein_g, 1) if protein_g is not None else None,
        carbs_g=round(carbs_g, 1) if carbs_g is not None else None,
        fats_g=round(fats_g, 1) if fats_g is not None else None,
    )
    session.add(meal)
    await session.commit()
    await session.refresh(meal)
    return meal


async def delete_meal(session: AsyncSession, meal_id: int) -> None:
    meal = await session.get(Meal, meal_id)
    if meal is not None:
        await session.delete(meal)
        await session.commit()


async def add_water(session: AsyncSession, day: date, amount_ml: int) -> WaterLog:
    settings = await get_settings(session)
    if day > local_today(settings.timezone):
        raise ValueError("Нельзя записывать будущую воду")
    if not (50 <= amount_ml <= MAX_WATER_ML):
        raise ValueError(f"Порция воды должна быть от 50 до {MAX_WATER_ML} мл")
    total = await session.scalar(
        select(func.sum(WaterLog.amount_ml)).where(WaterLog.date == day)
    )
    if (total or 0) + amount_ml > MAX_DAILY_WATER_ML:
        raise ValueError("Дневной объём воды выглядит неправдоподобно")
    item = WaterLog(date=day, amount_ml=amount_ml)
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


async def delete_water(session: AsyncSession, entry_id: int) -> None:
    item = await session.get(WaterLog, entry_id)
    if item is not None:
        await session.delete(item)
        await session.commit()


async def upsert_measurement(
    session: AsyncSession,
    day: date,
    *,
    weight_kg: float | None = None,
    waist_cm: float | None = None,
    notes: str | None = None,
) -> BodyMeasurement:
    settings = await get_settings(session)
    if day > local_today(settings.timezone):
        raise ValueError("Нельзя записывать будущий замер")
    if weight_kg is None and waist_cm is None:
        raise ValueError("Укажите вес или обхват талии")
    if weight_kg is not None and not (20 <= weight_kg <= 400):
        raise ValueError("Вес должен быть от 20 до 400 кг")
    if waist_cm is not None and not (30 <= waist_cm <= 250):
        raise ValueError("Обхват талии должен быть от 30 до 250 см")

    item = await session.scalar(
        select(BodyMeasurement).where(BodyMeasurement.date == day)
    )
    if item is None:
        item = BodyMeasurement(date=day)
        session.add(item)
    if weight_kg is not None:
        item.weight_kg = round(weight_kg, 1)
    if waist_cm is not None:
        item.waist_cm = round(waist_cm, 1)
    if notes is not None:
        item.notes = notes
    await session.commit()
    await session.refresh(item)
    return item
