"""Telegram initData validation tests."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest

from app.config import settings
from app.security import InitDataError, validate_init_data

BOT_TOKEN = "123456:test-token"
OWNER_ID = 100000001


def build_init_data(
    *,
    bot_token: str = BOT_TOKEN,
    user_id: int = OWNER_ID,
    auth_date: int | None = None,
    tamper: bool = False,
) -> str:
    values = {
        "auth_date": str(int(time.time()) if auth_date is None else auth_date),
        "query_id": "AAH-test-query",
        "user": json.dumps(
            {"id": user_id, "first_name": "Nikita", "username": "nikita"},
            separators=(",", ":"),
        ),
    }
    check_string = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    signature = hmac.new(
        secret, check_string.encode(), hashlib.sha256
    ).hexdigest()
    values["hash"] = "0" * 64 if tamper else signature
    return urlencode(values)


def test_valid_init_data_returns_user():
    user = validate_init_data(build_init_data(), BOT_TOKEN)
    assert user.id == OWNER_ID
    assert user.display_name == "Nikita"
    assert user.username == "nikita"


def test_tampered_signature_is_rejected():
    with pytest.raises(InitDataError, match="Подпись"):
        validate_init_data(build_init_data(tamper=True), BOT_TOKEN)


def test_stale_and_future_auth_dates_are_rejected():
    now = int(time.time())
    with pytest.raises(InitDataError, match="устарела"):
        validate_init_data(
            build_init_data(auth_date=now - 90000),
            BOT_TOKEN,
            max_age_seconds=86400,
            now=now,
        )
    with pytest.raises(InitDataError, match="будущего"):
        validate_init_data(
            build_init_data(auth_date=now + 600),
            BOT_TOKEN,
            now=now,
        )


def test_missing_fields_are_rejected():
    with pytest.raises(InitDataError):
        validate_init_data("", BOT_TOKEN)
    with pytest.raises(InitDataError, match="подпись"):
        validate_init_data("auth_date=1&user=%7B%7D", BOT_TOKEN)
    with pytest.raises(InitDataError, match="BOT_TOKEN"):
        validate_init_data(build_init_data(), "")


def test_api_accepts_valid_init_data_when_bot_token_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "bot_token", BOT_TOKEN)
    monkeypatch.setattr(settings, "owner_telegram_id", OWNER_ID)

    response = client.get(
        "/api/dashboard",
        headers={"X-Telegram-Init-Data": build_init_data()},
    )
    assert response.status_code == 200
    assert response.json()["date"]


def test_api_rejects_foreign_telegram_user(client, monkeypatch):
    monkeypatch.setattr(settings, "bot_token", BOT_TOKEN)
    monkeypatch.setattr(settings, "owner_telegram_id", OWNER_ID)

    response = client.get(
        "/api/dashboard",
        headers={"X-Telegram-Init-Data": build_init_data(user_id=123)},
    )
    assert response.status_code == 403


def test_api_reports_missing_bot_token(client, monkeypatch):
    monkeypatch.setattr(settings, "bot_token", "")

    response = client.get(
        "/api/dashboard",
        headers={"X-Telegram-Init-Data": build_init_data()},
    )
    assert response.status_code == 503
