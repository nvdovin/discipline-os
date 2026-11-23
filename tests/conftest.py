"""Shared pytest fixtures.

The application reads its configuration at import time, so every override
below is applied before ``app.main`` is imported. Tests run against a
throw-away SQLite database and never touch ``data/discipline.db``.
"""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

TMP_DIR = Path(tempfile.mkdtemp(prefix="discipline-tests-", dir="/tmp/opencode"))
DB_PATH = TMP_DIR / "test.db"

os.environ.update(
    {
        "DATABASE_URL": f"sqlite+aiosqlite:///{DB_PATH}",
        "DEV_MODE": "true",
        "BOT_TOKEN": "",
        "OWNER_TELEGRAM_ID": "100000001",
        "ENABLE_SCHEDULER": "false",
        "ENVIRONMENT": "test",
        "WEBAPP_URL": "",
    }
)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services.plan import (  # noqa: E402
    DEFAULT_EXERCISE_TARGETS,
    normalize_targets,
)

DOMAIN_TABLES = (
    "daily_logs",
    "exercise_sets",
    "workouts",
    "meals",
    "water_logs",
    "body_measurements",
    "sleep_logs",
    "bible_logs",
    "daily_reflections",
)


@pytest.fixture(scope="session")
def client() -> TestClient:
    """One TestClient for the whole session.

    A single client keeps one event loop for the async engine. Using a new
    client per test would hand pooled aiosqlite connections to a different
    loop and produce flaky cross-loop errors.
    """
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def reset_database(client: TestClient) -> None:
    """Remove domain data and restore default settings before every test."""
    exercise_targets = json.dumps(normalize_targets(DEFAULT_EXERCISE_TARGETS))
    connection = sqlite3.connect(DB_PATH)
    try:
        for table in DOMAIN_TABLES:
            connection.execute(f"DELETE FROM {table}")
        connection.execute(
            """
            UPDATE user_settings
               SET timezone = ?,
                   wake_up_time = ?,
                   bedtime = ?,
                   meal_times = ?,
                   protein_target_g = ?,
                   water_target_ml = ?,
                   bible_target_minutes = ?,
                   exercise_targets = ?,
                   telegram_user_id = ?,
                   display_name = ?
             WHERE id = 1
            """,
            (
                "Europe/Moscow",
                "06:00",
                "22:00",
                json.dumps(["11:00", "17:00"]),
                140,
                2000,
                30,
                exercise_targets,
                100000001,
                "Nikita",
            ),
        )
        connection.commit()
    finally:
        connection.close()
    yield


@pytest.fixture
def auth() -> dict[str, str]:
    """Local development auth header used by the Mini App in browser mode."""
    return {"X-Dev-Mode": "1"}


@pytest.fixture
def today(client: TestClient, auth: dict[str, str]) -> str:
    response = client.get("/api/dashboard", headers=auth)
    assert response.status_code == 200
    return response.json()["date"]
