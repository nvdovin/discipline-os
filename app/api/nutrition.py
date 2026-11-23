"""Nutrition, water and body measurement endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import SessionDep, UserDep
from app.api.utils import bad_request, resolve_date, validate_days
from app.schemas import MealIn, MeasurementIn, WaterIn
from app.services.nutrition import (
    add_meal,
    add_water,
    build_nutrition,
    delete_meal,
    delete_water,
    upsert_measurement,
)

router = APIRouter()


@router.get("/nutrition")
async def get_nutrition(
    session: SessionDep,
    user: UserDep,
    date_value: str | None = Query(default=None, alias="date"),
    days: int = Query(default=30, ge=7, le=90),
) -> dict:
    day = await resolve_date(session, date_value)
    validate_days(days)
    return await build_nutrition(session, day, days=days)


@router.post("/nutrition/meals")
async def create_meal(
    payload: MealIn,
    session: SessionDep,
    user: UserDep,
) -> dict:
    day = payload.date or await resolve_date(session, None)
    try:
        await add_meal(
            session,
            day,
            payload.description,
            time=payload.time,
            calories=payload.calories,
            protein_g=payload.protein_g,
            carbs_g=payload.carbs_g,
            fats_g=payload.fats_g,
        )
    except ValueError as exc:
        raise bad_request(exc) from exc
    return await build_nutrition(session, day)


@router.delete("/nutrition/meals/{meal_id}")
async def remove_meal(
    meal_id: int,
    session: SessionDep,
    user: UserDep,
    date_value: str | None = Query(default=None, alias="date"),
) -> dict:
    day = await resolve_date(session, date_value)
    await delete_meal(session, meal_id)
    return await build_nutrition(session, day)


@router.post("/nutrition/water")
async def create_water(
    payload: WaterIn,
    session: SessionDep,
    user: UserDep,
) -> dict:
    day = payload.date or await resolve_date(session, None)
    try:
        await add_water(session, day, payload.amount_ml)
    except ValueError as exc:
        raise bad_request(exc) from exc
    return await build_nutrition(session, day)


@router.delete("/nutrition/water/{entry_id}")
async def remove_water(
    entry_id: int,
    session: SessionDep,
    user: UserDep,
    date_value: str | None = Query(default=None, alias="date"),
) -> dict:
    day = await resolve_date(session, date_value)
    await delete_water(session, entry_id)
    return await build_nutrition(session, day)


@router.post("/nutrition/measurements")
async def create_measurement(
    payload: MeasurementIn,
    session: SessionDep,
    user: UserDep,
) -> dict:
    day = payload.date or await resolve_date(session, None)
    try:
        await upsert_measurement(
            session,
            day,
            weight_kg=payload.weight_kg,
            waist_cm=payload.waist_cm,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise bad_request(exc) from exc
    return await build_nutrition(session, day)
