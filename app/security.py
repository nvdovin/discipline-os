"""Telegram Mini App initData validation.

See https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
The bot token is the shared secret and is never sent to the client.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl


class InitDataError(ValueError):
    """Raised when initData is malformed, stale or has a bad signature."""


@dataclass(frozen=True)
class TelegramUser:
    id: int
    first_name: str = ""
    last_name: str = ""
    username: str = ""
    language_code: str = ""
    photo_url: str = ""

    @property
    def display_name(self) -> str:
        full = " ".join(part for part in (self.first_name, self.last_name) if part)
        return full or self.username or "Пользователь Telegram"


def _data_check_string(values: dict[str, str]) -> str:
    return "\n".join(f"{key}={values[key]}" for key in sorted(values))


def validate_init_data(
    init_data: str,
    bot_token: str,
    max_age_seconds: int = 86400,
    *,
    now: int | None = None,
) -> TelegramUser:
    if not init_data or not isinstance(init_data, str):
        raise InitDataError("Пустые данные Telegram")
    if not bot_token:
        raise InitDataError("BOT_TOKEN не настроен на сервере")

    pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=False)
    values: dict[str, str] = {}
    for key, value in pairs:
        if key in values:
            raise InitDataError("Повторяющееся поле initData")
        values[key] = value

    received_hash = values.pop("hash", "")
    if not received_hash:
        raise InitDataError("В initData отсутствует подпись")

    secret_key = hmac.new(
        b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256
    ).digest()
    calculated = hmac.new(
        secret_key,
        _data_check_string(values).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(calculated, received_hash.lower()):
        raise InitDataError("Подпись initData неверна")

    try:
        auth_date = int(values.get("auth_date", "0"))
    except (TypeError, ValueError) as exc:
        raise InitDataError("Некорректная дата авторизации") from exc

    current = int(time.time()) if now is None else int(now)
    if auth_date <= 0:
        raise InitDataError("В initData отсутствует auth_date")
    if auth_date > current + 60:
        raise InitDataError("Дата авторизации из будущего")
    if current - auth_date > max_age_seconds:
        raise InitDataError("Сессия Telegram устарела. Переоткройте приложение")

    raw_user = values.get("user")
    if not raw_user:
        raise InitDataError("В initData отсутствует пользователь")
    try:
        user_data = json.loads(raw_user)
        user_id = int(user_data["id"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise InitDataError("Некорректные данные пользователя") from exc

    return TelegramUser(
        id=user_id,
        first_name=str(user_data.get("first_name") or ""),
        last_name=str(user_data.get("last_name") or ""),
        username=str(user_data.get("username") or ""),
        language_code=str(user_data.get("language_code") or ""),
        photo_url=str(user_data.get("photo_url") or ""),
    )
