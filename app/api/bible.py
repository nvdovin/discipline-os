"""Bible study endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import SessionDep, UserDep
from app.api.utils import bad_request, resolve_date, validate_days
from app.schemas import BibleIn
from app.services.bible import build_bible, delete_bible, upsert_bible

router = APIRouter()


@router.get("/bible")
async def get_bible(
    session: SessionDep,
    user: UserDep,
    date_value: str | None = Query(default=None, alias="date"),
    days: int = Query(default=30, ge=7, le=90),
) -> dict:
    day = await resolve_date(session, date_value)
    validate_days(days)
    return await build_bible(session, day, days=days)


@router.post("/bible")
async def save_bible(
    payload: BibleIn,
    session: SessionDep,
    user: UserDep,
) -> dict:
    day = payload.date or await resolve_date(session, None)
    try:
        await upsert_bible(
            session, day, payload.duration_minutes, payload.notes
        )
    except ValueError as exc:
        raise bad_request(exc) from exc
    return await build_bible(session, day)


@router.delete("/bible")
async def remove_bible(
    session: SessionDep,
    user: UserDep,
    date_value: str | None = Query(default=None, alias="date"),
) -> dict:
    day = await resolve_date(session, date_value)
    await delete_bible(session, day)
    return await build_bible(session, day)
