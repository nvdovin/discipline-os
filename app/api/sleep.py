"""Sleep endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import SessionDep, UserDep
from app.api.utils import bad_request, resolve_date, validate_days
from app.schemas import SleepIn
from app.services.sleep import build_sleep, delete_sleep, upsert_sleep

router = APIRouter()


@router.get("/sleep")
async def get_sleep(
    session: SessionDep,
    user: UserDep,
    date_value: str | None = Query(default=None, alias="date"),
    days: int = Query(default=30, ge=7, le=90),
) -> dict:
    day = await resolve_date(session, date_value)
    validate_days(days)
    return await build_sleep(session, day, days=days)


@router.post("/sleep")
async def save_sleep(
    payload: SleepIn,
    session: SessionDep,
    user: UserDep,
) -> dict:
    day = payload.date or await resolve_date(session, None)
    try:
        await upsert_sleep(
            session,
            day,
            payload.bedtime,
            payload.wake_up_time,
            payload.notes,
        )
    except ValueError as exc:
        raise bad_request(exc) from exc
    return await build_sleep(session, day)


@router.delete("/sleep")
async def remove_sleep(
    session: SessionDep,
    user: UserDep,
    date_value: str | None = Query(default=None, alias="date"),
) -> dict:
    day = await resolve_date(session, date_value)
    await delete_sleep(session, day)
    return await build_sleep(session, day)
