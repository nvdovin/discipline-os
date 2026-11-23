"""Telegram command, FSM and callback handlers."""

from __future__ import annotations

import logging
import re
from datetime import date
from typing import Any

from aiogram import BaseMiddleware, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy import select

from app.bot.keyboards import (
    bible_minutes_keyboard,
    checkin_keyboard,
    exercise_keyboard,
    main_menu_keyboard,
    mini_app_button,
    reminder_keyboard,
    settings_keyboard,
    sleep_bedtime_keyboard,
    sleep_wake_keyboard,
    today_keyboard,
)
from app.bot.texts import (
    bible_text,
    checkin_text,
    exercise_text,
    help_text,
    nutrition_text,
    priority_text,
    settings_text,
    sleep_text,
    stats_text,
    today_text,
    welcome_text,
)
from app.config import settings as app_settings
from app.database import async_session_factory
from app.models import Reminder, UserSettings
from app.services.bible import build_bible, upsert_bible
from app.services.fitness import (
    add_set,
    build_fitness,
    complete_workout,
)
from app.services.habits import (
    build_dashboard,
    get_settings,
    toggle_habit,
)
from app.services.nutrition import add_meal, build_nutrition
from app.services.priority import build_priority
from app.services.settings import build_settings
from app.services.sleep import build_sleep, upsert_sleep
from app.services.stats import build_stats
from app.timeutils import local_today, parse_hhmm

logger = logging.getLogger(__name__)
router = Router(name="discipline")


class OwnerOnlyMiddleware(BaseMiddleware):
    """Personal app: only the configured owner may use the bot."""

    async def __call__(self, handler, event, data):  # type: ignore[no-untyped-def]
        user = data.get("event_from_user")
        if user is None:
            return await handler(event, data)
        allowed = True
        if app_settings.owner_telegram_id is not None:
            allowed = user.id == app_settings.owner_telegram_id
        else:
            async with async_session_factory() as session:
                owner_id = await session.scalar(
                    select(UserSettings.telegram_user_id).where(UserSettings.id == 1)
                )
            if owner_id is not None and owner_id != user.id:
                allowed = False
        if not allowed:
            if isinstance(event, CallbackQuery):
                await event.answer("Это личное приложение.", show_alert=True)
            elif isinstance(event, Message):
                await event.answer("Это личное приложение.")
            return None
        return await handler(event, data)


router.message.middleware(OwnerOnlyMiddleware())
router.callback_query.middleware(OwnerOnlyMiddleware())


class FoodForm(StatesGroup):
    description = State()


class SleepForm(StatesGroup):
    bedtime = State()
    wake = State()


class BibleForm(StatesGroup):
    minutes = State()


TIME_TOKEN = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
NUMBER = re.compile(r"\d{1,4}")


async def _today_date() -> date:
    async with async_session_factory() as session:
        user_settings = await get_settings(session)
        return local_today(user_settings.timezone)


async def _dashboard() -> dict[str, Any]:
    async with async_session_factory() as session:
        user_settings = await get_settings(session)
        return await build_dashboard(
            session, local_today(user_settings.timezone)
        )


async def _fitness() -> dict[str, Any]:
    async with async_session_factory() as session:
        user_settings = await get_settings(session)
        return await build_fitness(session, local_today(user_settings.timezone))


async def _stats() -> dict[str, Any]:
    async with async_session_factory() as session:
        user_settings = await get_settings(session)
        return await build_stats(
            session, local_today(user_settings.timezone), "week"
        )


async def _sleep() -> dict[str, Any]:
    async with async_session_factory() as session:
        user_settings = await get_settings(session)
        return await build_sleep(session, local_today(user_settings.timezone))


async def _bible() -> dict[str, Any]:
    async with async_session_factory() as session:
        user_settings = await get_settings(session)
        return await build_bible(session, local_today(user_settings.timezone))


async def _nutrition() -> dict[str, Any]:
    async with async_session_factory() as session:
        user_settings = await get_settings(session)
        return await build_nutrition(
            session, local_today(user_settings.timezone)
        )


async def _priority() -> dict[str, Any]:
    async with async_session_factory() as session:
        user_settings = await get_settings(session)
        return await build_priority(
            session, local_today(user_settings.timezone)
        )


async def _settings_data() -> dict[str, Any]:
    async with async_session_factory() as session:
        return await build_settings(session)


async def _edit(
    message: Message | None, text: str, keyboard: InlineKeyboardMarkup | None = None
) -> None:
    if message is None:
        return
    try:
        await message.edit_text(
            text,
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc):
            logger.warning("Could not edit bot message: %s", exc)


def _cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Отмена", callback_data="flow:cancel")]
        ]
    )


def _extract_times(text: str) -> list[str]:
    values = []
    for hour, minute in TIME_TOKEN.findall(text):
        values.append(f"{int(hour):02d}:{minute}")
    return values


def _parse_food_text(raw: str) -> tuple[str, int | None, float | None]:
    text = raw.strip()
    calories: int | None = None
    protein: float | None = None
    description = text

    if "|" in text:
        parts = [part.strip() for part in text.split("|")]
        if len(parts) >= 2 and re.fullmatch(r"\d{1,4}", parts[1]):
            description = parts[0] or "Приём пищи"
            calories = int(parts[1])
            if len(parts) >= 3 and re.fullmatch(
                r"\d{1,3}(?:[.,]\d+)?", parts[2]
            ):
                protein = float(parts[2].replace(",", "."))
        else:
            description = text
    else:
        kcal_match = re.search(r"(\d{1,4})\s*(?:ккал|kcal)", text, re.I)
        protein_match = re.search(
            r"(\d{1,3}(?:[.,]\d+)?)\s*(?:г\s*)?(?:белка|protein)", text, re.I
        )
        spans: list[tuple[int, int]] = []
        if kcal_match:
            calories = int(kcal_match.group(1))
            spans.append(kcal_match.span())
        if protein_match:
            protein = float(protein_match.group(1).replace(",", "."))
            spans.append(protein_match.span())
        for start, end in sorted(spans, reverse=True):
            text = text[:start] + text[end:]
        description = re.sub(r"[\s,;|·\-]+$", "", text).strip(" ,;|·-")
        description = re.sub(r"^[\s,;|·\-]+", "", description)
        if not description:
            description = "Приём пищи"

    if calories is not None and not (0 <= calories <= 5000):
        raise ValueError("Калории должны быть от 0 до 5000")
    if protein is not None and not (0 <= protein <= 500):
        raise ValueError("Белок должен быть от 0 до 500 г")
    if not description:
        raise ValueError("Опишите, что вы съели")
    return description[:300], calories, protein


def _parse_bible_text(raw: str) -> tuple[int, str | None]:
    match = NUMBER.search(raw)
    if not match:
        raise ValueError("Напишите количество минут, например: 40 | мысль")
    minutes = int(match.group())
    if not (1 <= minutes <= 600):
        raise ValueError("Минуты должны быть от 1 до 600")
    note = raw[match.end() :].strip(" |-—.,:;")
    note = re.sub(r"^(?:мин(?:ут)?)\b[\s:—\-]*", "", note, flags=re.I).strip()
    return minutes, note or None


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    async with async_session_factory() as session:
        user_settings = await get_settings(session)
        if user_settings.telegram_user_id is None and message.from_user:
            user_settings.telegram_user_id = message.from_user.id
            if not user_settings.display_name or user_settings.display_name == "Атлет":
                user_settings.display_name = message.from_user.first_name or "Атлет"
            await session.commit()
        dashboard = await build_dashboard(
            session, local_today(user_settings.timezone)
        )
    await message.answer(
        welcome_text(dashboard), reply_markup=main_menu_keyboard()
    )


@router.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(help_text(), reply_markup=main_menu_keyboard())


@router.message(Command("today"))
async def cmd_today(message: Message, state: FSMContext) -> None:
    await state.clear()
    dashboard = await _dashboard()
    await message.answer(
        today_text(dashboard), reply_markup=today_keyboard(dashboard)
    )


@router.message(Command("stats"))
async def cmd_stats(message: Message, state: FSMContext) -> None:
    await state.clear()
    stats = await _stats()
    await message.answer(stats_text(stats), reply_markup=main_menu_keyboard())


@router.message(Command("exercise"))
async def cmd_exercise(message: Message, state: FSMContext) -> None:
    await state.clear()
    fitness = await _fitness()
    await message.answer(
        exercise_text(fitness), reply_markup=exercise_keyboard(fitness)
    )


@router.message(Command("food"))
async def cmd_food(message: Message, state: FSMContext) -> None:
    await _begin_food(message, state)


@router.message(Command("sleep"))
async def cmd_sleep(message: Message, state: FSMContext) -> None:
    await _begin_sleep(message, state)


@router.message(Command("bible"))
async def cmd_bible(message: Message, state: FSMContext) -> None:
    await _begin_bible(message, state)


@router.message(Command("priority"))
async def cmd_priority(message: Message, state: FSMContext) -> None:
    await state.clear()
    priority = await _priority()
    rows: list[list[InlineKeyboardButton]] = []
    if priority["today"].get("main_priority"):
        mark = "✅" if priority["today"]["priority_completed"] else "⬜"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{mark} Отметить главное дело",
                    callback_data="priority:toggle",
                )
            ]
        )
    button = mini_app_button()
    if button:
        rows.append([button])
    await message.answer(
        priority_text(priority),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows) if rows else None,
    )


@router.message(Command("settings"))
async def cmd_settings(message: Message, state: FSMContext) -> None:
    await state.clear()
    data = await _settings_data()
    await message.answer(
        settings_text(data), reply_markup=settings_keyboard(data)
    )


@router.message(Command("dashboard"))
async def cmd_dashboard(message: Message, state: FSMContext) -> None:
    await state.clear()
    button = mini_app_button()
    if button is None:
        await message.answer(
            "Mini App ещё не настроен. Укажите <code>WEBAPP_URL</code> "
            "(HTTPS-адрес приложения) в <code>.env</code> и перезапустите сервер."
        )
        return
    await message.answer(
        "<b>Discipline OS Mini App</b>\n"
        "Дашборд, графики, тренировки, питание, сон и настройки — в одном экране.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[button]]),
    )


@router.message(Command("checkin"))
async def cmd_checkin(message: Message, state: FSMContext) -> None:
    await state.clear()
    dashboard = await _dashboard()
    await message.answer(
        checkin_text(dashboard), reply_markup=checkin_keyboard(dashboard)
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Ввод отменён.", reply_markup=main_menu_keyboard())


# ---------------------------------------------------------------------------
# Food flow
# ---------------------------------------------------------------------------


async def _begin_food(message: Message, state: FSMContext) -> None:
    await state.set_state(FoodForm.description)
    await message.answer(
        "<b>Что вы съели?</b>\n"
        "Опишите приём пищи. Если знаете, добавьте калории и белок:\n"
        "<code>Курица с рисом | 600 | 40</code>\n"
        "Можно без цифр — приложение не выдумывает значения.",
        reply_markup=_cancel_keyboard(),
    )


@router.message(FoodForm.description, ~F.text.startswith("/"))
async def food_description(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Нужен текст с описанием приёма пищи.")
        return
    try:
        description, calories, protein = _parse_food_text(message.text)
        async with async_session_factory() as session:
            await add_meal(
                session,
                await _today_date(),
                description,
                calories=calories,
                protein_g=protein,
            )
    except ValueError as exc:
        await message.answer(
            f"Не получилось записать: {exc}\n\nПопробуйте ещё раз."
        )
        return
    await state.clear()
    nutrition = await _nutrition()
    await message.answer(
        "Записано.\n\n" + nutrition_text(nutrition),
        reply_markup=main_menu_keyboard(),
    )


# ---------------------------------------------------------------------------
# Sleep flow
# ---------------------------------------------------------------------------


async def _begin_sleep(message: Message, state: FSMContext) -> None:
    await state.set_state(SleepForm.bedtime)
    await message.answer(
        "<b>Записываем сон</b>\n"
        "Во сколько легли? Напишите время, например <code>23:30</code>, "
        "или выберите кнопку. Можно сразу два времени: <code>23:30 06:30</code>.",
        reply_markup=sleep_bedtime_keyboard(),
    )


async def _finish_sleep(
    target: Message,
    state: FSMContext,
    bedtime: str,
    wake_up_time: str,
    *,
    edit: bool = False,
) -> bool:
    try:
        async with async_session_factory() as session:
            await upsert_sleep(
                session, await _today_date(), bedtime, wake_up_time
            )
    except ValueError as exc:
        await target.answer(
            f"Не получилось сохранить сон: {exc}\n"
            "Проверьте время и попробуйте снова."
        )
        return False
    await state.clear()
    sleep = await _sleep()
    text = "Сон записан.\n\n" + sleep_text(sleep)
    if edit:
        await _edit(target, text, main_menu_keyboard())
    else:
        await target.answer(text, reply_markup=main_menu_keyboard())
    return True


@router.message(SleepForm.bedtime, ~F.text.startswith("/"))
async def sleep_bedtime(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Напишите время в формате ЧЧ:ММ.")
        return
    times = _extract_times(message.text)
    if len(times) >= 2:
        await _finish_sleep(message, state, times[0], times[1])
        return
    if not times:
        await message.answer(
            "Не вижу время. Напишите, например, <code>23:30</code>."
        )
        return
    try:
        parse_hhmm(times[0])
    except ValueError as exc:
        await message.answer(str(exc))
        return
    await state.update_data(bedtime=times[0])
    await state.set_state(SleepForm.wake)
    await message.answer(
        f"Отбой: <b>{times[0]}</b>. Во сколько встали? "
        "Напишите время или выберите кнопку.",
        reply_markup=sleep_wake_keyboard(),
    )


@router.message(SleepForm.wake, ~F.text.startswith("/"))
async def sleep_wake(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Напишите время в формате ЧЧ:ММ.")
        return
    times = _extract_times(message.text)
    if not times:
        await message.answer(
            "Не вижу время. Напишите, например, <code>06:30</code>."
        )
        return
    data = await state.get_data()
    bedtime = data.get("bedtime")
    if not bedtime:
        await state.set_state(SleepForm.bedtime)
        await message.answer(
            "Сначала запишем отбой. Во сколько легли?",
            reply_markup=sleep_bedtime_keyboard(),
        )
        return
    await _finish_sleep(message, state, bedtime, times[0])


# ---------------------------------------------------------------------------
# Bible flow
# ---------------------------------------------------------------------------


async def _begin_bible(message: Message, state: FSMContext) -> None:
    await state.set_state(BibleForm.minutes)
    await message.answer(
        "<b>Чтение Библии</b>\n"
        "Сколько минут сегодня читали? Напишите число или выберите кнопку.\n"
        "Можно добавить заметку: <code>40 | мысль</code>.",
        reply_markup=bible_minutes_keyboard(),
    )


async def _finish_bible(
    target: Message,
    state: FSMContext | None,
    minutes: int,
    notes: str | None = None,
    *,
    edit: bool = False,
) -> bool:
    try:
        async with async_session_factory() as session:
            await upsert_bible(
                session, await _today_date(), minutes, notes
            )
    except ValueError as exc:
        await target.answer(f"Не получилось сохранить: {exc}")
        return False
    if state is not None:
        await state.clear()
    bible = await _bible()
    text = "Чтение записано.\n\n" + bible_text(bible)
    if edit:
        await _edit(target, text, main_menu_keyboard())
    else:
        await target.answer(text, reply_markup=main_menu_keyboard())
    return True


@router.message(BibleForm.minutes, ~F.text.startswith("/"))
async def bible_minutes(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Напишите количество минут, например 40.")
        return
    try:
        minutes, notes = _parse_bible_text(message.text)
    except ValueError as exc:
        await message.answer(str(exc))
        return
    await _finish_bible(message, state, minutes, notes)


# ---------------------------------------------------------------------------
# Callbacks: menu and flows
# ---------------------------------------------------------------------------


@router.callback_query(F.data == "flow:cancel")
async def callback_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await _edit(callback.message, "Ввод отменён.")
    await callback.answer()


@router.callback_query(F.data == "menu:today")
async def menu_today(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    dashboard = await _dashboard()
    if callback.message:
        await callback.message.answer(
            today_text(dashboard), reply_markup=today_keyboard(dashboard)
        )
    await callback.answer()


@router.callback_query(F.data == "menu:stats")
async def menu_stats(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    stats = await _stats()
    if callback.message:
        await callback.message.answer(
            stats_text(stats), reply_markup=main_menu_keyboard()
        )
    await callback.answer()


@router.callback_query(F.data == "menu:exercise")
async def menu_exercise(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    fitness = await _fitness()
    if callback.message:
        await callback.message.answer(
            exercise_text(fitness), reply_markup=exercise_keyboard(fitness)
        )
    await callback.answer()


@router.callback_query(F.data == "menu:food")
async def menu_food(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message:
        await _begin_food(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "menu:sleep")
async def menu_sleep(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message:
        await _begin_sleep(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "menu:bible")
async def menu_bible(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message:
        await _begin_bible(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "menu:settings")
async def menu_settings(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    data = await _settings_data()
    if callback.message:
        await callback.message.answer(
            settings_text(data), reply_markup=settings_keyboard(data)
        )
    await callback.answer()


@router.callback_query(F.data == "menu:help")
async def menu_help(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if callback.message:
        await callback.message.answer(
            help_text(), reply_markup=main_menu_keyboard()
        )
    await callback.answer()


@router.callback_query(F.data == "menu:dashboard")
async def menu_dashboard(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    button = mini_app_button()
    if callback.message:
        if button is None:
            await callback.message.answer(
                "Mini App ещё не настроен. Укажите WEBAPP_URL в .env."
            )
        else:
            await callback.message.answer(
                "Откройте Mini App:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[button]]),
            )
    await callback.answer()


@router.callback_query(F.data.startswith("sleep:bed:"))
async def sleep_bed_callback(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data:
        return
    parts = callback.data.split(":")
    bedtime = f"{parts[-2]}:{parts[-1]}"
    await state.update_data(bedtime=bedtime)
    await state.set_state(SleepForm.wake)
    await _edit(
        callback.message,
        f"Отбой: <b>{bedtime}</b>. Во сколько встали?",
        sleep_wake_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("sleep:wake:"))
async def sleep_wake_callback(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or callback.message is None:
        return
    parts = callback.data.split(":")
    wake = f"{parts[-2]}:{parts[-1]}"
    data = await state.get_data()
    bedtime = data.get("bedtime")
    if not bedtime:
        await state.set_state(SleepForm.bedtime)
        await _edit(
            callback.message,
            "Сначала выберите отбой.",
            sleep_bedtime_keyboard(),
        )
        await callback.answer()
        return
    await _finish_sleep(callback.message, state, bedtime, wake, edit=True)
    await callback.answer()


@router.callback_query(F.data.startswith("bible:min:"))
async def bible_min_callback(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or callback.message is None:
        return
    try:
        minutes = int(callback.data.split(":")[-1])
    except ValueError:
        await callback.answer("Некорректное время", show_alert=True)
        return
    await _finish_bible(callback.message, state, minutes, edit=True)
    await callback.answer("Записано")


@router.callback_query(F.data == "bible:custom")
async def bible_custom_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(BibleForm.minutes)
    if callback.message:
        await _edit(
            callback.message,
            "Напишите количество минут и, если хотите, заметку:\n"
            "<code>40 | мысль</code>",
            _cancel_keyboard(),
        )
    await callback.answer()


# ---------------------------------------------------------------------------
# Habit toggles and exercise quick actions
# ---------------------------------------------------------------------------


async def _toggle_habit_callback(
    callback: CallbackQuery, key: str, checkin: bool
) -> None:
    try:
        async with async_session_factory() as session:
            await toggle_habit(session, key, await _today_date())
    except ValueError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    dashboard = await _dashboard()
    if checkin:
        await _edit(
            callback.message,
            checkin_text(dashboard),
            checkin_keyboard(dashboard),
        )
    else:
        await _edit(
            callback.message,
            today_text(dashboard),
            today_keyboard(dashboard),
        )
    await callback.answer("Обновлено")


@router.callback_query(F.data.startswith("habit:toggle:"))
async def habit_toggle(callback: CallbackQuery) -> None:
    if not callback.data:
        return
    await _toggle_habit_callback(callback, callback.data.split(":")[-1], False)


@router.callback_query(F.data.startswith("checkin:toggle:"))
async def checkin_toggle(callback: CallbackQuery) -> None:
    if not callback.data:
        return
    await _toggle_habit_callback(callback, callback.data.split(":")[-1], True)


@router.callback_query(F.data == "today:refresh")
async def today_refresh(callback: CallbackQuery) -> None:
    dashboard = await _dashboard()
    await _edit(
        callback.message, today_text(dashboard), today_keyboard(dashboard)
    )
    await callback.answer("Обновлено")


@router.callback_query(F.data == "checkin:refresh")
async def checkin_refresh(callback: CallbackQuery) -> None:
    dashboard = await _dashboard()
    await _edit(
        callback.message, checkin_text(dashboard), checkin_keyboard(dashboard)
    )
    await callback.answer("Обновлено")


@router.callback_query(F.data == "priority:toggle")
async def priority_toggle(callback: CallbackQuery) -> None:
    try:
        async with async_session_factory() as session:
            await toggle_habit(session, "priority", await _today_date())
    except ValueError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    priority = await _priority()
    rows: list[list[InlineKeyboardButton]] = []
    if priority["today"].get("main_priority"):
        mark = "✅" if priority["today"]["priority_completed"] else "⬜"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{mark} Отметить главное дело",
                    callback_data="priority:toggle",
                )
            ]
        )
    button = mini_app_button()
    if button:
        rows.append([button])
    await _edit(
        callback.message,
        priority_text(priority),
        InlineKeyboardMarkup(inline_keyboard=rows) if rows else None,
    )
    await callback.answer("Обновлено")


@router.callback_query(F.data.startswith("wo:add:"))
async def workout_add(callback: CallbackQuery) -> None:
    if not callback.data:
        return
    key = callback.data.split(":", 2)[2]
    fitness = await _fitness()
    mode = fitness.get("mode", "full")
    exercises = fitness["modes"].get(mode, [])
    exercise = next((item for item in exercises if item["key"] == key), None)
    if exercise is None:
        await callback.answer("Упражнение не найдено", show_alert=True)
        return
    try:
        async with async_session_factory() as session:
            await add_set(
                session,
                await _today_date(),
                exercise_key=key,
                repetitions=exercise["reps"]
                if exercise["kind"] == "reps"
                else None,
                duration_seconds=exercise["duration_seconds"]
                if exercise["kind"] == "duration"
                else None,
                rest_seconds=exercise["rest_seconds"],
                mode=mode,
            )
    except ValueError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    fitness = await _fitness()
    await _edit(
        callback.message,
        exercise_text(fitness),
        exercise_keyboard(fitness),
    )
    await callback.answer("Подход записан")


@router.callback_query(F.data == "wo:min")
async def workout_minimum(callback: CallbackQuery) -> None:
    try:
        async with async_session_factory() as session:
            await complete_workout(
                session, await _today_date(), mode="minimum", completed=True
            )
    except ValueError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    fitness = await _fitness()
    await _edit(
        callback.message,
        exercise_text(fitness),
        exercise_keyboard(fitness),
    )
    await callback.answer("Минимум засчитан")


@router.callback_query(F.data == "wo:complete")
async def workout_complete(callback: CallbackQuery) -> None:
    try:
        async with async_session_factory() as session:
            await complete_workout(
                session, await _today_date(), mode="full", completed=True
            )
    except ValueError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    fitness = await _fitness()
    await _edit(
        callback.message,
        exercise_text(fitness),
        exercise_keyboard(fitness),
    )
    await callback.answer("Тренировка засчитана")


@router.callback_query(F.data == "wo:refresh")
async def workout_refresh(callback: CallbackQuery) -> None:
    fitness = await _fitness()
    await _edit(
        callback.message,
        exercise_text(fitness),
        exercise_keyboard(fitness),
    )
    await callback.answer("Обновлено")


# ---------------------------------------------------------------------------
# Settings callbacks
# ---------------------------------------------------------------------------


@router.callback_query(F.data.startswith("rem:toggle:"))
async def reminder_toggle(callback: CallbackQuery) -> None:
    if not callback.data:
        return
    key = callback.data.split(":", 2)[2]
    async with async_session_factory() as session:
        reminder = await session.scalar(
            select(Reminder).where(Reminder.key == key)
        )
        if reminder is None:
            await callback.answer("Напоминание не найдено", show_alert=True)
            return
        reminder.enabled = not reminder.enabled
        await session.commit()
        data = await build_settings(session)
    try:
        from app.services.scheduler import reschedule_all

        await reschedule_all()
    except Exception:  # pragma: no cover - scheduler may be off in tests
        logger.debug("Could not reschedule reminders", exc_info=True)
    await _edit(
        callback.message, settings_text(data), settings_keyboard(data)
    )
    await callback.answer(
        "Включено" if reminder.enabled else "Выключено"
    )


@router.callback_query(F.data == "settings:refresh")
async def settings_refresh(callback: CallbackQuery) -> None:
    data = await _settings_data()
    await _edit(
        callback.message, settings_text(data), settings_keyboard(data)
    )
    await callback.answer("Обновлено")
