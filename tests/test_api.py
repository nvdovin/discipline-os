"""HTTP API tests for the Discipline OS Mini App backend."""

from __future__ import annotations

from datetime import date, timedelta


def _habit(dashboard: dict, key: str) -> dict:
    return next(item for item in dashboard["habits"] if item["key"] == key)


def test_health_and_auth_required(client, auth):
    assert client.get("/healthz").json()["status"] == "ok"
    assert client.get("/api/dashboard").status_code == 401
    assert client.get("/api/dashboard", headers=auth).status_code == 200
    assert client.get("/api/dashboard", headers={"X-Dev-Mode": "0"}).status_code == 401


def test_dashboard_shape_and_date_validation(client, auth):
    response = client.get("/api/dashboard", headers=auth)
    assert response.status_code == 200
    data = response.json()
    assert data["date"]
    assert len(data["habits"]) == 5
    assert data["completion"] == 0
    assert data["success"] is False
    assert data["priority"]["main_priority"] is None
    assert data["settings"]["timezone"] == "Europe/Moscow"

    bad = client.get("/api/dashboard?date=2026-13-40", headers=auth)
    assert bad.status_code == 422


def test_habit_toggle_overrides_derived_state(client, auth):
    dashboard = client.get("/api/dashboard", headers=auth).json()
    assert _habit(dashboard, "bible")["completed"] is False

    response = client.post(
        "/api/habits/bible/toggle", json={"completed": True}, headers=auth
    )
    assert response.status_code == 200
    assert response.json()["habit"]["completed"] is True

    dashboard = client.get("/api/dashboard", headers=auth).json()
    assert _habit(dashboard, "bible")["completed"] is True

    response = client.post(
        "/api/habits/bible/toggle", json={"completed": False}, headers=auth
    )
    assert response.status_code == 200
    dashboard = client.get("/api/dashboard", headers=auth).json()
    assert _habit(dashboard, "bible")["completed"] is False


def test_habit_toggle_rejects_unknown_key_and_future_day(client, auth, today):
    unknown = client.post(
        "/api/habits/coffee/toggle", json={"completed": True}, headers=auth
    )
    assert unknown.status_code == 400

    future = (date.fromisoformat(today) + timedelta(days=1)).isoformat()
    response = client.post(
        "/api/habits/bible/toggle",
        json={"completed": True, "date": future},
        headers=auth,
    )
    assert response.status_code == 400


def test_priority_flow_and_toggle_guard(client, auth, today):
    guard = client.post(
        "/api/habits/priority/toggle", json={"completed": True}, headers=auth
    )
    assert guard.status_code == 400

    response = client.put(
        "/api/priority",
        headers=auth,
        json={
            "date": today,
            "main_priority": "Закрыть квартальный отчёт",
            "secondary_tasks": [
                {"text": "Проверить почту"},
                {"text": "Позвонить в банк", "done": True},
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["today"]["main_priority"] == "Закрыть квартальный отчёт"
    assert [item["text"] for item in body["today"]["secondary_tasks"]] == [
        "Проверить почту",
        "Позвонить в банк",
    ]

    toggled = client.post(
        "/api/habits/priority/toggle", json={"completed": True}, headers=auth
    )
    assert toggled.status_code == 200
    dashboard = client.get("/api/dashboard", headers=auth).json()
    assert _habit(dashboard, "priority")["completed"] is True


def test_fitness_logged_sets_regression(client, auth):
    fitness = client.get("/api/fitness", headers=auth).json()
    exercise = fitness["modes"]["full"][0]
    planned_sets = exercise["sets"]
    assert isinstance(planned_sets, int)
    assert exercise["logged_sets"] == []

    payload = {"exercise_key": exercise["key"]}
    if exercise["kind"] == "duration":
        payload["duration_seconds"] = exercise["duration_seconds"]
    else:
        payload["repetitions"] = exercise["reps"]

    response = client.post("/api/fitness/sets", json=payload, headers=auth)
    assert response.status_code == 200
    row = next(
        item
        for item in response.json()["modes"]["full"]
        if item["key"] == exercise["key"]
    )
    # ``sets`` is the planned number of sets; logged sets live separately.
    assert row["sets"] == planned_sets
    assert len(row["logged_sets"]) == 1
    assert row["done_sets"] == 1

    completed = client.post(
        "/api/fitness/complete", json={"mode": "full"}, headers=auth
    )
    assert completed.status_code == 200
    assert completed.json()["workout"]["status"] == "completed"
    dashboard = client.get("/api/dashboard", headers=auth).json()
    assert _habit(dashboard, "exercise")["completed"] is True


def test_fitness_set_validation(client, auth):
    empty = client.post("/api/fitness/sets", json={"exercise_key": "pushups"}, headers=auth)
    assert empty.status_code == 422

    too_many = client.post(
        "/api/fitness/sets",
        json={"exercise_key": "pushups", "repetitions": 500},
        headers=auth,
    )
    assert too_many.status_code == 422


def test_nutrition_meal_water_and_measurement_delta(client, auth, today):
    meal = client.post(
        "/api/nutrition/meals",
        headers=auth,
        json={"description": "Омлет с овощами", "protein_g": 32.5, "calories": 410},
    )
    assert meal.status_code == 200
    body = meal.json()
    assert body["totals"]["protein_g"] == 32.5
    assert body["totals"]["calories"] == 410
    assert len(body["meals"]) == 1

    water = client.post("/api/nutrition/water", json={"amount_ml": 250}, headers=auth)
    assert water.status_code == 200
    assert water.json()["water"]["total_ml"] == 250

    measured = client.post(
        "/api/nutrition/measurements",
        headers=auth,
        json={"weight_kg": 81.3, "waist_cm": 87.5},
    )
    assert measured.status_code == 200
    measurements = measured.json()["measurements"]
    assert measurements["latest"]["weight_kg"] == 81.3
    # One measurement is not a trend: the delta must stay null.
    assert measurements["weight_delta_30"] is None
    assert measurements["waist_delta_30"] is None

    earlier = (date.fromisoformat(today) - timedelta(days=5)).isoformat()
    client.post(
        "/api/nutrition/measurements",
        headers=auth,
        json={"date": earlier, "weight_kg": 82.0, "waist_cm": 88.0},
    )
    nutrition = client.get("/api/nutrition", headers=auth).json()
    assert nutrition["measurements"]["weight_delta_30"] == -0.7
    assert nutrition["measurements"]["waist_delta_30"] == -0.5

    invalid = client.post(
        "/api/nutrition/measurements", headers=auth, json={"notes": "нет данных"}
    )
    assert invalid.status_code == 422


def test_sleep_log_schedule_and_habit(client, auth, today):
    response = client.post(
        "/api/sleep",
        headers=auth,
        json={"bedtime": "23:30", "wake_up_time": "07:30"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["today"]["duration_minutes"] == 480
    assert body["today"]["on_schedule"] is False
    assert body["today"]["date"] == today

    dashboard = client.get("/api/dashboard", headers=auth).json()
    assert _habit(dashboard, "sleep")["completed"] is True

    deleted = client.delete("/api/sleep", headers=auth)
    assert deleted.status_code == 200
    assert deleted.json()["today"] is None
    dashboard = client.get("/api/dashboard", headers=auth).json()
    assert _habit(dashboard, "sleep")["completed"] is False


def test_sleep_rejects_invalid_time_and_future(client, auth, today):
    bad_time = client.post(
        "/api/sleep",
        headers=auth,
        json={"bedtime": "25:00", "wake_up_time": "07:00"},
    )
    assert bad_time.status_code == 422

    future = (date.fromisoformat(today) + timedelta(days=1)).isoformat()
    future_log = client.post(
        "/api/sleep",
        headers=auth,
        json={"date": future, "bedtime": "22:00", "wake_up_time": "06:00"},
    )
    assert future_log.status_code == 400


def test_bible_log_and_habit(client, auth):
    response = client.post(
        "/api/bible",
        headers=auth,
        json={"duration_minutes": 35, "notes": "Псалом 23"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["today"]["duration_minutes"] == 35
    assert body["today"]["notes"] == "Псалом 23"
    assert body["streak"]["current"] == 1

    dashboard = client.get("/api/dashboard", headers=auth).json()
    assert _habit(dashboard, "bible")["completed"] is True

    deleted = client.delete("/api/bible", headers=auth)
    assert deleted.status_code == 200
    assert deleted.json()["today"] is None


def test_settings_update_validation_and_export(client, auth):
    defaults = client.get("/api/settings", headers=auth).json()
    assert defaults["targets"]["water_target_ml"] == 2000
    assert defaults["schedule"]["bedtime"] == "22:00"

    response = client.put(
        "/api/settings",
        headers=auth,
        json={
            "water_target_ml": 2100,
            "meal_times": ["10:00", "18:00"],
            "bedtime": "22:30",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["targets"]["water_target_ml"] == 2100
    assert body["schedule"]["meal_times"] == ["10:00", "18:00"]
    assert body["schedule"]["bedtime"] == "22:30"

    invalid = client.put(
        "/api/settings", headers=auth, json={"meal_times": ["10:00", "10:00"]}
    )
    assert invalid.status_code == 422

    export = client.get("/api/export", headers=auth)
    assert export.status_code == 200
    assert export.headers["content-disposition"].endswith(
        'filename="discipline-os-export.json"'
    )
    payload = export.json()
    assert payload["app"] == "Discipline OS"
    assert payload["exported_at"].endswith("+00:00")
    assert len(payload["habits"]) == 5
    assert len(payload["reminders"]) == 7


def test_stats_periods(client, auth):
    week = client.get("/api/stats?period=week", headers=auth)
    assert week.status_code == 200
    body = week.json()
    assert body["period"] == "week"
    assert len(body["daily"]) == 7
    assert "milestones" in body
    assert "records" in body

    month = client.get("/api/stats?period=month", headers=auth)
    assert month.status_code == 200
    assert month.json()["period"] == "month"

    invalid = client.get("/api/stats?period=year", headers=auth)
    assert invalid.status_code == 422
