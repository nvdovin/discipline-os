"""Settings and data export endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.api.deps import SessionDep, UserDep
from app.api.utils import bad_request
from app.schemas import SettingsIn
from app.services.settings import build_settings, export_data, update_settings

router = APIRouter()


@router.get("/settings")
async def get_settings_endpoint(session: SessionDep, user: UserDep) -> dict:
    return await build_settings(session)


@router.put("/settings")
async def save_settings_endpoint(
    payload: SettingsIn,
    session: SessionDep,
    user: UserDep,
) -> dict:
    try:
        data = await update_settings(session, payload)
    except ValueError as exc:
        raise bad_request(exc) from exc
    try:
        from app.services.scheduler import reschedule_all

        await reschedule_all()
    except Exception:
        # Settings are saved even if the bot/scheduler is not running.
        pass
    return data


@router.get("/export")
async def export_endpoint(session: SessionDep, user: UserDep) -> JSONResponse:
    data = await export_data(session)
    return JSONResponse(
        content=data,
        headers={
            "Content-Disposition": 'attachment; filename="discipline-os-export.json"'
        },
    )
