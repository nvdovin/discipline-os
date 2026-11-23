"""APScheduler reminders, rehydrated from SQLite on every start.

There is exactly one scheduler process. Jobs use deterministic ids and
``replace_existing`` so restarting or saving settings cannot create duplicate
reminders. If the server is down at the scheduled minute, APScheduler fires
the job on startup when it is less than 10 minutes late; otherwise the
reminder is skipped instead of arriving at a random time.
"""

from __future__ import annotations

import logging

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.bot.instance import get_bot
from app.bot.keyboards import reminder_keyboard
from app.bot.texts import reminder_text
from app.config import settings as app_settings
from app.database import async_session_factory
from app.models import Reminder
from app.services.habits import build_dashboard, get_settings
from app.timeutils import local_today, parse_hhmm

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def _send_reminder(key: str) -> None:
    bot = get_bot()
    if bot is None:
        return
    async with async_session_factory() as session:
        user_settings = await get_settings(session)
        if not user_settings.reminders_enabled:
            return
        reminder = await session.scalar(
            select(Reminder).where(Reminder.key == key)
        )
        if reminder is None or not reminder.enabled:
            return
        recipient = (
            user_settings.telegram_user_id or app_settings.owner_telegram_id
        )
        if not recipient:
            logger.info("Reminder %s skipped: no Telegram recipient", key)
            return
        dashboard = await build_dashboard(
            session, local_today(user_settings.timezone)
        )

    try:
        await bot.send_message(
            recipient,
            reminder_text(key, dashboard),
            reply_markup=reminder_keyboard(key, dashboard),
            disable_web_page_preview=True,
        )
        logger.info("Reminder sent: %s", key)
    except Exception:  # pragma: no cover - network dependent
        logger.exception("Could not send reminder %s", key)


async def reschedule_all() -> None:
    """Rebuild every reminder job from the database."""
    if _scheduler is None or not _scheduler.running:
        return
    for job in _scheduler.get_jobs():
        if job.id.startswith("reminder:"):
            job.remove()

    async with async_session_factory() as session:
        user_settings = await get_settings(session)
        if not user_settings.reminders_enabled:
            logger.info("All reminders are disabled")
            return
        reminders = list(
            (
                await session.scalars(
                    select(Reminder).where(Reminder.enabled.is_(True))
                )
            ).all()
        )
        timezone = pytz.timezone(user_settings.timezone)

    for reminder in reminders:
        parsed = parse_hhmm(reminder.time)
        _scheduler.add_job(
            _send_reminder,
            trigger=CronTrigger(
                hour=parsed.hour,
                minute=parsed.minute,
                timezone=timezone,
            ),
            args=[reminder.key],
            id=f"reminder:{reminder.key}",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
            misfire_grace_time=600,
        )
    logger.info("Scheduled %d reminders", len(reminders))


async def start_scheduler() -> AsyncIOScheduler | None:
    global _scheduler
    if not app_settings.enable_scheduler:
        logger.info("Scheduler disabled by configuration")
        return None
    if not app_settings.bot_token:
        logger.info("Scheduler not started: BOT_TOKEN is empty")
        return None
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone=pytz.UTC)
        _scheduler.start()
    await reschedule_all()
    return _scheduler


async def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler stopped")
