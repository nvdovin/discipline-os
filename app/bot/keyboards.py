"""Inline keyboards for the Telegram bot."""

from __future__ import annotations

from typing import Any

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
)

from app.config import settings

HABIT_ICONS = {
    "sleep": "🌙",
    "exercise": "🏋️",
    "nutrition": "🍽",
    "bible": "📖",
    "priority": "🎯",
}


def mini_app_button() -> InlineKeyboardButton | None:
    url = (settings.webapp_url or "").strip()
    if not url:
        return None
    if url.startswith("https://"):
        return InlineKeyboardButton(
            text="📱 Открыть приложение", web_app=WebAppInfo(url=url)
        )
    return InlineKeyboardButton(text="📱 Открыть приложение", url=url)


def _with_app(rows: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    button = mini_app_button()
    if button is not None:
        rows.append([button])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return _with_app(
        [
            [
                InlineKeyboardButton(text="Сегодня", callback_data="menu:today"),
                InlineKeyboardButton(text="Статистика", callback_data="menu:stats"),
            ],
            [
                InlineKeyboardButton(text="Тренировка", callback_data="menu:exercise"),
                InlineKeyboardButton(text="Питание", callback_data="menu:food"),
            ],
            [
                InlineKeyboardButton(text="Сон", callback_data="menu:sleep"),
                InlineKeyboardButton(text="Библия", callback_data="menu:bible"),
            ],
            [
                InlineKeyboardButton(text="Настройки", callback_data="menu:settings"),
                InlineKeyboardButton(text="Помощь", callback_data="menu:help"),
            ],
        ]
    )


def today_keyboard(day_state: dict[str, Any]) -> InlineKeyboardMarkup:
    rows = []
    for habit in day_state.get("habits", []):
        mark = "✅" if habit["completed"] else "⬜"
        icon = HABIT_ICONS.get(habit["key"], "•")
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{mark} {icon} {habit['name']}",
                    callback_data=f"habit:toggle:{habit['key']}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(text="🔄 Обновить", callback_data="today:refresh"),
        ]
    )
    return _with_app(rows)


def checkin_keyboard(day_state: dict[str, Any]) -> InlineKeyboardMarkup:
    rows = []
    for habit in day_state.get("habits", []):
        mark = "✅" if habit["completed"] else "⬜"
        icon = HABIT_ICONS.get(habit["key"], "•")
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{mark} {icon} {habit['name']}",
                    callback_data=f"checkin:toggle:{habit['key']}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(text="🔄 Обновить", callback_data="checkin:refresh"),
        ]
    )
    return _with_app(rows)


def exercise_keyboard(fitness: dict[str, Any]) -> InlineKeyboardMarkup:
    mode = fitness.get("mode", "full")
    exercises = fitness.get("modes", {}).get(mode) or fitness.get("modes", {}).get(
        "full", []
    )
    rows = []
    for exercise in exercises:
        target = exercise.get("target") or ""
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"＋ {exercise['name']} · {target}",
                    callback_data=f"wo:add:{exercise['key']}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(text="✅ Засчитать минимум", callback_data="wo:min"),
            InlineKeyboardButton(text="🏁 Завершить", callback_data="wo:complete"),
        ]
    )
    rows.append(
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="wo:refresh")]
    )
    return _with_app(rows)


def settings_keyboard(settings_data: dict[str, Any]) -> InlineKeyboardMarkup:
    rows = []
    for reminder in settings_data.get("reminders", []):
        mark = "✅" if reminder["enabled"] else "⏸"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{mark} {reminder['title']} · {reminder['time']}",
                    callback_data=f"rem:toggle:{reminder['key']}",
                )
            ]
        )
    rows.append(
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="settings:refresh")]
    )
    return _with_app(rows)


def sleep_bedtime_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="22:00", callback_data="sleep:bed:22:00"),
                InlineKeyboardButton(text="22:30", callback_data="sleep:bed:22:30"),
                InlineKeyboardButton(text="23:00", callback_data="sleep:bed:23:00"),
            ],
            [
                InlineKeyboardButton(text="23:30", callback_data="sleep:bed:23:30"),
                InlineKeyboardButton(text="00:00", callback_data="sleep:bed:00:00"),
                InlineKeyboardButton(text="00:30", callback_data="sleep:bed:00:30"),
            ],
        ]
    )


def sleep_wake_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="05:30", callback_data="sleep:wake:05:30"),
                InlineKeyboardButton(text="06:00", callback_data="sleep:wake:06:00"),
                InlineKeyboardButton(text="06:30", callback_data="sleep:wake:06:30"),
            ],
            [
                InlineKeyboardButton(text="07:00", callback_data="sleep:wake:07:00"),
                InlineKeyboardButton(text="07:30", callback_data="sleep:wake:07:30"),
                InlineKeyboardButton(text="08:00", callback_data="sleep:wake:08:00"),
            ],
        ]
    )


def bible_minutes_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="15 мин", callback_data="bible:min:15"),
                InlineKeyboardButton(text="30 мин", callback_data="bible:min:30"),
                InlineKeyboardButton(text="45 мин", callback_data="bible:min:45"),
            ],
            [
                InlineKeyboardButton(text="60 мин", callback_data="bible:min:60"),
                InlineKeyboardButton(text="Своё время", callback_data="bible:custom"),
            ],
        ]
    )


def reminder_keyboard(
    key: str, day_state: dict[str, Any] | None = None
) -> InlineKeyboardMarkup:
    if key == "checkin" and day_state is not None:
        return checkin_keyboard(day_state)
    rows: list[list[InlineKeyboardButton]] = []
    if key == "morning":
        rows.append(
            [InlineKeyboardButton(text="Посмотреть день", callback_data="menu:today")]
        )
    elif key == "bible":
        rows.append(
            [
                InlineKeyboardButton(text="30 мин", callback_data="bible:min:30"),
                InlineKeyboardButton(text="Своё время", callback_data="menu:bible"),
            ]
        )
    elif key == "exercise":
        rows.append(
            [
                InlineKeyboardButton(
                    text="Открыть тренировку", callback_data="menu:exercise"
                )
            ]
        )
    elif key in {"meal_1", "meal_2"}:
        rows.append(
            [InlineKeyboardButton(text="Записать приём", callback_data="menu:food")]
        )
    elif key == "sleep":
        rows.append(
            [InlineKeyboardButton(text="Записать сон", callback_data="menu:sleep")]
        )
    return _with_app(rows)
