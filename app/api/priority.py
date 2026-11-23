"""Daily priority and evening reflection endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import SessionDep, UserDep
from app.api.utils import bad_request, resolve_date
from app.schemas import PriorityIn
from app.services.priority import build_priority, upsert_priority

router = APIRouter()


@router.get("/priority")
async def get_priority(
    session: SessionDep,
    user: UserDep,
    date_value: str | None = Query(default=None, alias="date"),
) -> dict:
    day = await resolve_date(session, date_value)
    return await build_priority(session, day)


@router.put("/priority")
async def save_priority(
    payload: PriorityIn,
    session: SessionDep,
    user: UserDep,
) -> dict:
    day = payload.date or await resolve_date(session, None)
    updates = payload.model_dump(exclude={"date"}, exclude_none=True)
    try:
        await upsert_priority(session, day, **updates)
    except ValueError as exc:
        raise bad_request(exc) from exc
    return await build_priority(session, day)
