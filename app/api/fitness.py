"""Fitness endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import SessionDep, UserDep
from app.api.utils import bad_request, resolve_date, validate_days
from app.schemas import CompleteWorkoutIn, ExerciseSetIn
from app.services.fitness import add_set, build_fitness, complete_workout, delete_set

router = APIRouter()


@router.get("/fitness")
async def get_fitness(
    session: SessionDep,
    user: UserDep,
    date_value: str | None = Query(default=None, alias="date"),
    days: int = Query(default=30, ge=7, le=90),
) -> dict:
    day = await resolve_date(session, date_value)
    validate_days(days)
    return await build_fitness(session, day, days=days)


@router.post("/fitness/sets")
async def add_fitness_set(
    payload: ExerciseSetIn,
    session: SessionDep,
    user: UserDep,
) -> dict:
    day = payload.date or await resolve_date(session, None)
    try:
        await add_set(
            session,
            day,
            exercise_key=payload.exercise_key,
            exercise_name=payload.exercise_name,
            repetitions=payload.repetitions,
            duration_seconds=payload.duration_seconds,
            rest_seconds=payload.rest_seconds,
            mode=payload.mode,
        )
    except ValueError as exc:
        raise bad_request(exc) from exc
    return await build_fitness(session, day)


@router.delete("/fitness/sets/{set_id}")
async def delete_fitness_set(
    set_id: int,
    session: SessionDep,
    user: UserDep,
    date_value: str | None = Query(default=None, alias="date"),
) -> dict:
    day = await resolve_date(session, date_value)
    await delete_set(session, set_id)
    return await build_fitness(session, day)


@router.post("/fitness/complete")
async def complete_fitness(
    payload: CompleteWorkoutIn,
    session: SessionDep,
    user: UserDep,
) -> dict:
    day = payload.date or await resolve_date(session, None)
    try:
        await complete_workout(
            session,
            day,
            mode=payload.mode,
            completed=payload.completed,
            duration_minutes=payload.duration_minutes,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise bad_request(exc) from exc
    return await build_fitness(session, day)
