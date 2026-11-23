"""Small API helpers."""

from __future__ import annotations

from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.habits import get_settings
from app.timeutils import parse_date


async def resolve_date(session: AsyncSession, value: str | None) -> date:
    user_settings = await get_settings(session)
    try:
        return parse_date(value, user_settings.timezone)
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Дата должна быть в формате YYYY-MM-DD",
        ) from exc


def bad_request(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def validate_days(days: int, minimum: int = 7, maximum: int = 90) -> int:
    if not (minimum <= days <= maximum):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Период должен быть от {minimum} до {maximum} дней",
        )
    return days
