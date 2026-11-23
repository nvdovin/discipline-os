"""Authentication and shared API dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session
from app.security import InitDataError, validate_init_data


@dataclass(frozen=True)
class AuthUser:
    id: int
    display_name: str
    username: str = ""
    dev: bool = False


async def get_current_user(request: Request) -> AuthUser:
    init_data = request.headers.get("X-Telegram-Init-Data", "").strip()
    dev_header = request.headers.get("X-Dev-Mode", "").strip().lower()

    if init_data:
        if not settings.bot_token:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="BOT_TOKEN не настроен на сервере",
            )
        try:
            user = validate_init_data(
                init_data,
                settings.bot_token,
                settings.init_data_max_age_seconds,
            )
        except InitDataError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(exc),
            ) from exc
        if (
            settings.owner_telegram_id is not None
            and user.id != settings.owner_telegram_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Это личное приложение",
            )
        return AuthUser(
            id=user.id,
            display_name=user.display_name,
            username=user.username,
        )

    if settings.dev_mode and dev_header in {"1", "true", "yes"}:
        return AuthUser(
            id=settings.owner_telegram_id or 0,
            display_name="Локальный режим",
            dev=True,
        )

    if not settings.dev_mode and settings.owner_telegram_id is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OWNER_TELEGRAM_ID не настроен на сервере",
        )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Откройте приложение через Telegram",
    )


SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserDep = Annotated[AuthUser, Depends(get_current_user)]
