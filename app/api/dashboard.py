"""Dashboard and habit toggle endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import SessionDep, UserDep
from app.api.utils import bad_request, resolve_date
from app.schemas import ToggleHabitIn
from app.services.habits import build_dashboard, toggle_habit

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard(
    session: SessionDep,
    user: UserDep,
    date_value: str | None = Query(default=None, alias="date"),
) -> dict:
    day = await resolve_date(session, date_value)
    return await build_dashboard(session, day)


@router.post("/habits/{key}/toggle")
async def toggle_habit_endpoint(
    key: str,
    payload: ToggleHabitIn,
    session: SessionDep,
    user: UserDep,
) -> dict:
    day = payload.date or await resolve_date(session, None)
    try:
        day_state = await toggle_habit(session, key, day, payload.completed)
    except ValueError as exc:
        raise bad_request(exc) from exc
    habit = next(
        (item for item in day_state["habits"] if item["key"] == key), None
    )
    return {"day": day_state, "habit": habit}


@router.get("/health")
async def api_health() -> dict:
    return {"status": "ok"}
