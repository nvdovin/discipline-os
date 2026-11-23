"""Statistics endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import SessionDep, UserDep
from app.api.utils import bad_request, resolve_date
from app.services.stats import build_stats

router = APIRouter()


@router.get("/stats")
async def get_stats(
    session: SessionDep,
    user: UserDep,
    period: str = Query(default="week", pattern="^(week|month)$"),
    date_value: str | None = Query(default=None, alias="date"),
) -> dict:
    day = await resolve_date(session, date_value)
    try:
        return await build_stats(session, day, period)
    except ValueError as exc:
        raise bad_request(exc) from exc
