"""Aiogram bot/dispatcher singletons and polling lifecycle."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from app.config import settings

logger = logging.getLogger(__name__)

_bot: Bot | None = None
_dispatcher: Dispatcher | None = None
_polling_task: asyncio.Task | None = None

BOT_COMMANDS = [
    BotCommand(command="today", description="Прогресс на сегодня"),
    BotCommand(command="exercise", description="Записать тренировку"),
    BotCommand(command="food", description="Записать приём пищи"),
    BotCommand(command="sleep", description="Записать сон"),
    BotCommand(command="bible", description="Записать чтение Библии"),
    BotCommand(command="stats", description="Короткий отчёт"),
    BotCommand(command="settings", description="Напоминания и цели"),
    BotCommand(command="dashboard", description="Открыть Mini App"),
    BotCommand(command="help", description="Помощь"),
]


def get_bot() -> Bot | None:
    global _bot
    if not settings.bot_token:
        return None
    if _bot is None:
        _bot = Bot(
            token=settings.bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
    return _bot


def get_dispatcher() -> Dispatcher | None:
    global _dispatcher
    if not settings.bot_token:
        return None
    if _dispatcher is None:
        from app.bot.handlers import router

        _dispatcher = Dispatcher(storage=MemoryStorage())
        _dispatcher.include_router(router)
    return _dispatcher


async def set_bot_commands(bot: Bot) -> None:
    try:
        await bot.set_my_commands(BOT_COMMANDS)
    except Exception:  # pragma: no cover - network dependent
        logger.warning("Could not set bot commands", exc_info=True)


async def start_polling() -> asyncio.Task | None:
    """Start long polling as a background task.

    Polling (rather than webhooks) keeps local development and small-server
    deployment simple. Telegram queues updates while the app is down, so
    reminders and messages survive restarts.
    """
    global _polling_task
    bot = get_bot()
    dispatcher = get_dispatcher()
    if bot is None or dispatcher is None:
        return None
    await set_bot_commands(bot)

    async def _run() -> None:
        try:
            await dispatcher.start_polling(
                bot,
                handle_signals=False,
                close_bot_session=False,
            )
        except asyncio.CancelledError:  # pragma: no cover - shutdown path
            raise
        except Exception:
            logger.exception("Telegram polling stopped unexpectedly")

    _polling_task = asyncio.create_task(_run(), name="telegram-polling")
    logger.info("Telegram polling started")
    return _polling_task


async def stop_polling() -> None:
    global _polling_task
    if _polling_task is not None:
        _polling_task.cancel()
        try:
            await _polling_task
        except asyncio.CancelledError:
            pass
        except Exception:  # pragma: no cover - shutdown path
            logger.debug("Polling task finished with error", exc_info=True)
        _polling_task = None
    if _bot is not None:
        await _bot.session.close()
    logger.info("Telegram bot stopped")
