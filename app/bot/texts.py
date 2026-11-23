"""Russian-language bot copy.

Tone rules: no shaming, no guilt, no "streak or nothing". Missed habits are
information, not failure.
"""

from __future__ import annotations

from html import escape
from typing import Any

from app.timeutils import format_minutes

HABIT_ICONS = {
    "sleep": "🌙",
    "exercise": "🏋️",
    "nutrition": "🍽",
    "bible": "📖",
    "priority": "🎯",
}


def progress_bar(percent: int, width: int = 10) -> str:
    percent = max(0, min(100, int(percent)))
    filled = round(width * percent / 100)
    return "█" * filled + "░" * (width - filled)


def _habit_lines(day_state: dict[str, Any]) -> str:
    lines = []
    for habit in day_state.get("habits", []):
        mark = "✅" if habit["completed"] else "⬜"
        icon = HABIT_ICONS.get(habit["key"], "•")
        lines.append(
            f"{mark} {icon} <b>{escape(habit['name'])}</b> — "
            f"{escape(habit['detail'])}"
        )
    return "\n".join(lines)


def today_text(day_state: dict[str, Any]) -> str:
    percent = day_state["completion"]
    lines = [
        f"<b>Сегодня, {escape(day_state['human_date'])}</b>",
        f"Дисциплина дня: <b>{percent}%</b> · "
        f"{day_state['completed_count']} из {day_state['habit_count']}",
        f"<code>{progress_bar(percent)}</code>",
        "",
        _habit_lines(day_state),
    ]
    priority = day_state.get("priority") or {}
    if priority.get("main_priority"):
        lines.extend(
            [
                "",
                f"🎯 Главное дело: <b>{escape(priority['main_priority'])}</b>",
                "Выполнено" if priority.get("priority_completed") else "В работе",
            ]
        )
    streak = day_state.get("streak", {}).get("current", 0)
    if streak:
        lines.extend(["", f"🔥 Серия: {streak} дн. подряд"])
    if percent >= 100:
        lines.extend(["", "Все привычки закрыты. Спокойно отдохните — это тоже часть дисциплины."])
    elif percent >= 60:
        lines.extend(["", "Хороший день. То, что получилось, уже имеет значение."])
    elif day_state["completed_count"]:
        lines.extend(["", "Уже есть движение. Одного маленького шага достаточно, чтобы продолжить."])
    else:
        lines.extend(["", "Можно начать с одного маленького шага. Без давления."])
    return "\n".join(lines)


def checkin_text(day_state: dict[str, Any]) -> str:
    lines = [
        "<b>Как прошёл день?</b>",
        "Отметьте то, что получилось. Это не экзамен — просто обратная связь.",
        "",
        _habit_lines(day_state),
        "",
        "Если что-то не получилось — это нормально. Завтра можно вернуться без долгов и чувства вины.",
    ]
    return "\n".join(lines)


def welcome_text(day_state: dict[str, Any] | None = None) -> str:
    lines = [
        "<b>Discipline OS</b>",
        "Личный помощник для сна, движения, питания, Библии и главного дела дня.",
        "",
        "Здесь нет наказаний за пропуски. Есть ритм, который можно восстановить.",
        "",
        "Команды:",
        "/today — прогресс на сегодня",
        "/exercise — записать тренировку",
        "/food — записать приём пищи",
        "/sleep — записать сон",
        "/bible — записать чтение",
        "/stats — короткий отчёт",
        "/settings — напоминания и цели",
        "/dashboard — открыть Mini App",
        "/help — помощь",
    ]
    if day_state is not None:
        lines.extend(
            [
                "",
                f"Сегодня: <b>{day_state['completion']}%</b> · "
                f"{day_state['completed_count']} из {day_state['habit_count']}",
            ]
        )
    return "\n".join(lines)


def help_text() -> str:
    return (
        "<b>Команды</b>\n"
        "/today — сегодняшние привычки и прогресс\n"
        "/exercise — план и быстрая запись подходов\n"
        "/food — записать приём пищи\n"
        "/sleep — записать время сна\n"
        "/bible — записать чтение Библии\n"
        "/priority — главное дело дня\n"
        "/stats — отчёт за неделю\n"
        "/settings — напоминания и цели\n"
        "/dashboard — открыть Mini App\n"
        "/checkin — вечерний чек-ин вручную\n"
        "/cancel — отменить ввод\n\n"
        "Все подробные формы и графики — в Mini App. Кнопки ниже работают и без него."
    )


def stats_text(stats: dict[str, Any]) -> str:
    delta = stats["completion_delta"]
    if delta > 0:
        comparison = f"+{delta}% к прошлому периоду"
    elif delta < 0:
        comparison = f"{delta}% к прошлому периоду"
    else:
        comparison = "как в прошлом периоде"
    lines = [
        f"<b>Отчёт за {stats['days']} дней</b>",
        escape(stats["range"]["label"]),
        "",
        f"Дисциплина: <b>{stats['completion']}%</b> ({comparison})",
        f"<code>{progress_bar(stats['completion'])}</code>",
        "",
        f"🏋️ Тренировок: <b>{stats['exercise_days']}</b>",
        f"📖 Библия: <b>{stats['bible_minutes']} мин</b>",
        f"🌙 Сон в среднем: <b>{escape(stats['avg_sleep_label'])}</b>",
        f"🍽 Питание по плану: <b>{stats['nutrition_days']} из {stats['days']}</b>",
        f"🔥 Текущая серия: <b>{stats['streak']['current']} дн.</b> "
        f"(лучшая — {stats['streak']['best']})",
    ]
    if stats["weight"]["latest"] is not None:
        weight = f"⚖️ Вес: <b>{stats['weight']['latest']} кг</b>"
        if stats["weight"]["delta"] is not None:
            weight += f" ({stats['weight']['delta']:+} кг за период)"
        lines.append(weight)
    if stats["waist"]["latest"] is not None:
        waist = f"📏 Талия: <b>{stats['waist']['latest']} см</b>"
        if stats["waist"]["delta"] is not None:
            waist += f" ({stats['waist']['delta']:+} см за период)"
        lines.append(waist)
    lines.extend(
        [
            "",
            "Смотрите на тренд, а не на отдельный день. Пропуск — не приговор.",
        ]
    )
    return "\n".join(lines)


def exercise_text(fitness: dict[str, Any]) -> str:
    plan = fitness["plan"]
    workout = fitness.get("workout")
    mode = fitness.get("mode", "full")
    exercises = fitness["modes"].get(mode, [])
    lines = [
        f"<b>{escape(plan['title'])}</b> · {escape(plan['subtitle'])}",
        f"Режим: {'минимум' if mode == 'minimum' else 'полный'}",
        "",
    ]
    for exercise in exercises:
        done = exercise["done_sets"]
        if exercise["kind"] == "reps":
            done_label = f"{done} подх. · {exercise['done_reps']} повт."
        else:
            done_label = f"{done} подх. · {format_minutes(round(exercise['done_duration_seconds'] / 60))}"
        lines.append(
            f"• <b>{escape(exercise['name'])}</b> — цель {exercise['target']}, "
            f"сделано {done_label}"
        )
    if workout and workout["status"] == "completed":
        lines.extend(["", "✅ Тренировка засчитана. Любая активность считается."])
    elif workout and workout["sets_count"]:
        lines.extend(["", "Уже есть подходы. Завершите, когда будете готовы."])
    else:
        lines.extend(["", "Пока пусто. Минимум тоже считается полноценным днём."])
    lines.extend(
        [
            "",
            "Работайте без отказа. Отдых и восстановление — часть плана.",
        ]
    )
    return "\n".join(lines)


def nutrition_text(nutrition: dict[str, Any]) -> str:
    totals = nutrition["totals"]
    targets = nutrition["targets"]
    meals = nutrition["meals"]
    lines = [
        "<b>Питание сегодня</b>",
        f"Приёмов: <b>{len(meals)} из {targets['meals']}</b>",
        f"Белок: <b>{totals['protein_g']:.0f} из {targets['protein_g']} г</b>",
    ]
    if totals["calories"]:
        lines.append(f"Калории: <b>{totals['calories']} ккал</b> (по записям)")
    water = nutrition["water"]
    lines.append(
        f"Вода: <b>{water['total_ml']} из {water['target_ml']} мл</b>"
    )
    if meals:
        lines.append("")
        for meal in meals:
            details = []
            if meal["calories"] is not None:
                details.append(f"{meal['calories']} ккал")
            if meal["protein_g"] is not None:
                details.append(f"{meal['protein_g']:g} г белка")
            suffix = f" · {', '.join(details)}" if details else ""
            lines.append(
                f"• {meal['time']} — {escape(meal['description'])}{escape(suffix)}"
            )
    if totals["has_missing_values"]:
        lines.extend(["", "Часть значений не указана — цифры только по записанным данным."])
    lines.extend(
        [
            "",
            "Голодание опционально. Пропущенный приём или еда вне окна — не ошибка.",
        ]
    )
    return "\n".join(lines)


def sleep_text(sleep: dict[str, Any]) -> str:
    target = sleep["target"]
    today = sleep.get("today")
    consistency = sleep["consistency"]
    lines = [
        "<b>Сон</b>",
        f"Цель: <b>{target['bedtime']} → {target['wake_up_time']}</b> · "
        f"{target['duration_label']}",
        "",
    ]
    if today:
        lines.extend(
            [
                f"Последняя ночь: <b>{today['bedtime']} → {today['wake_up_time']}</b>",
                f"Продолжительность: <b>{today['duration_label']}</b>",
                "В режиме" if today["on_schedule"] else "Вне целевого окна — это просто данные",
            ]
        )
    else:
        lines.append("Запись за сегодня ещё не добавлена.")
    lines.extend(
        [
            "",
            f"За 7 дней: {consistency['logged']} записей, "
            f"{consistency['on_schedule']} в целевом окне (±45 мин).",
            "",
            "Не сокращайте сон ради раннего подъёма. Сдвигайте режим постепенно, по 15 минут.",
        ]
    )
    return "\n".join(lines)


def bible_text(bible: dict[str, Any]) -> str:
    today = bible.get("today")
    lines = [
        "<b>Библия</b>",
        f"Цель: {bible['target_minutes']}–45 минут в день",
        "",
    ]
    if today:
        lines.append(
            f"Сегодня: <b>{today['duration_minutes']} мин</b>"
        )
        if today.get("notes"):
            lines.append(f"Заметка: {escape(today['notes'])}")
    else:
        lines.append("Сегодня ещё не записано. Можно начать с 10 минут.")
    lines.extend(
        [
            "",
            f"За 7 дней: <b>{bible['totals']['minutes_7']} мин</b>",
            f"Серия: <b>{bible['streak']['current']} дн.</b>",
        ]
    )
    return "\n".join(lines)


def priority_text(priority: dict[str, Any]) -> str:
    today = priority["today"]
    lines = ["<b>Главное дело дня</b>", ""]
    if today.get("main_priority"):
        mark = "✅" if today["priority_completed"] else "⬜"
        lines.append(f"{mark} <b>{escape(today['main_priority'])}</b>")
    else:
        lines.append("Главное дело ещё не назначено.")
    tasks = today.get("secondary_tasks") or []
    if tasks:
        lines.extend(["", "<b>Второстепенные задачи</b>"])
        for task in tasks:
            mark = "✅" if task["done"] else "⬜"
            lines.append(f"{mark} {escape(task['text'])}")
    if today.get("positive_result"):
        lines.extend(["", f"<b>Что получилось:</b> {escape(today['positive_result'])}"])
    if today.get("tomorrow_priority"):
        lines.extend(
            ["", f"<b>Завтра:</b> {escape(today['tomorrow_priority'])}"]
        )
    lines.extend(["", "Одно главное дело — достаточно. Остальное подождёт."])
    return "\n".join(lines)


def settings_text(settings_data: dict[str, Any]) -> str:
    schedule = settings_data["schedule"]
    targets = settings_data["targets"]
    lines = [
        "<b>Настройки</b>",
        f"Подъём: <b>{schedule['wake_up_time']}</b> · Отбой: <b>{schedule['bedtime']}</b>",
        f"Приёмы пищи: <b>{', '.join(schedule['meal_times']) or '—'}</b>",
        f"Белок: <b>{targets['protein_target_g']} г</b> · Вода: <b>{targets['water_target_ml']} мл</b>",
        f"Библия: <b>{targets['bible_target_minutes']} мин</b>",
        "",
        "<b>Напоминания</b>",
    ]
    for reminder in settings_data["reminders"]:
        mark = "✅" if reminder["enabled"] else "⏸"
        lines.append(f"{mark} {reminder['title']} — {reminder['time']}")
    lines.extend(
        [
            "",
            "Нажмите на напоминание, чтобы включить или выключить. Время и цели меняются в Mini App.",
        ]
    )
    return "\n".join(lines)


def reminder_text(key: str, day_state: dict[str, Any] | None = None) -> str:
    plan_title = (
        day_state.get("exercise", {}).get("title") if day_state else None
    )
    if key == "morning":
        return (
            "<b>Доброе утро!</b>\n"
            "Пора начинать день. Не нужно делать всё сразу — выберите один шаг.\n\n"
            + (f"Сегодня по плану: <b>{escape(plan_title)}</b>.\n" if plan_title else "")
            + "Хорошего и спокойного дня."
        )
    if key == "bible":
        return (
            "<b>Время для Библии</b>\n"
            "30–45 минут без спешки. Если сегодня получается меньше — тоже хорошо.\n\n"
            "Можно записать чтение прямо здесь."
        )
    if key == "exercise":
        return (
            "<b>Время движения</b>\n"
            + (f"Сегодня: <b>{escape(plan_title)}</b>.\n" if plan_title else "")
            + "Полная тренировка или минимум — обе считаются. Не до отказа."
        )
    if key == "meal_1":
        return (
            "<b>Первый приём пищи</b>\n"
            "Ориентир — 11:00. Это не жёсткое правило: голодание опционально.\n"
            "Запишите то, что действительно съели."
        )
    if key == "meal_2":
        return (
            "<b>Второй приём пищи</b>\n"
            "Ориентир — 17:00. Если планы изменились — ничего страшного.\n"
            "Запишите приём, чтобы видеть недельный тренд."
        )
    if key == "sleep":
        return (
            "<b>Пора готовиться ко сну</b>\n"
            "Цель — отбой около 22:00. Если не получается, сдвигайтесь на 15 минут за раз.\n\n"
            "Не сокращайте сон ради раннего подъёма. Восстановление важнее цифры."
        )
    if key == "checkin" and day_state is not None:
        return checkin_text(day_state)
    return "<b>Discipline OS</b>\nНебольшой шаг сегодня лучше идеального плана завтра."
