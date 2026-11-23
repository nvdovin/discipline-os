"""HTTP API routers."""

from fastapi import APIRouter

from app.api import bible, dashboard, fitness, nutrition, priority, settings, sleep, stats

api_router = APIRouter()
api_router.include_router(dashboard.router, tags=["dashboard"])
api_router.include_router(fitness.router, tags=["fitness"])
api_router.include_router(nutrition.router, tags=["nutrition"])
api_router.include_router(sleep.router, tags=["sleep"])
api_router.include_router(bible.router, tags=["bible"])
api_router.include_router(priority.router, tags=["priority"])
api_router.include_router(stats.router, tags=["stats"])
api_router.include_router(settings.router, tags=["settings"])
