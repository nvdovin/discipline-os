#!/usr/bin/env python3
"""Browser smoke test for the Discipline OS Mini App.

Run it against a live server:

    python3 scripts/e2e_smoke.py
    BASE_URL=https://discipline.example.com/ python3 scripts/e2e_smoke.py

It checks every screen at 375/768/1440 px, fails on console errors or
horizontal overflow, exercises the sheet open/close keyboard path and writes
screenshots to ``staff/screenshots``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8010/")
SCREENSHOT_DIR = Path(
    os.getenv("SCREENSHOT_DIR", Path(__file__).resolve().parent.parent / "staff" / "screenshots")
)
ROUTES = ("today", "fitness", "nutrition", "sleep", "stats", "settings")
VIEWPORTS = ((375, 812, "375"), (768, 1024, "768"), (1440, 1000, "1440"))


def check_route(page, route: str, label: str, failures: list[str]) -> None:
    page.goto(f"{BASE_URL}#/{route}", wait_until="networkidle")
    page.wait_for_selector(".screen-head, .error-screen", timeout=15000)
    page.wait_for_timeout(450)

    if page.locator(".error-screen").count():
        failures.append(f"[{label}] {route}: error screen rendered")
        return

    overflow = page.evaluate(
        "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    if overflow > 0:
        failures.append(f"[{label}] {route}: horizontal overflow {overflow}px")

    expected_title = {
        "today": "Сегодня",
        "fitness": "Тренировка",
        "nutrition": "Питание",
        "sleep": "Сон",
        "stats": "Статистика",
        "settings": "Настройки",
    }[route]
    if expected_title not in page.title():
        failures.append(f"[{label}] {route}: unexpected title {page.title()!r}")

    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SCREENSHOT_DIR / f"{route}-{label}-viewport.png"))
    page.screenshot(path=str(SCREENSHOT_DIR / f"{route}-{label}.png"), full_page=True)
    print(f"[{label}] {route}: ok")


def check_sheet_keyboard(page, route: str, trigger: str, failures: list[str]) -> None:
    page.goto(f"{BASE_URL}#/{route}", wait_until="networkidle")
    page.wait_for_selector(".screen-head")
    button = page.locator(trigger).first
    if not button.count():
        failures.append(f"[375] {route}: trigger {trigger} not found")
        return
    button.click()
    page.wait_for_selector("#sheet-root .sheet", timeout=5000)
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    if page.locator("#sheet-root .sheet").count():
        failures.append(f"[375] {route}: sheet did not close on Escape")
    else:
        print(f"[375] {route}: sheet opens and closes on Escape")


def main() -> int:
    failures: list[str] = []
    console_errors: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for width, height, label in VIEWPORTS:
            context = browser.new_context(
                viewport={"width": width, "height": height},
                device_scale_factor=2,
                locale="ru-RU",
                timezone_id="Europe/Moscow",
            )
            page = context.new_page()
            page.on(
                "console",
                lambda message: console_errors.append(f"{message.type}: {message.text}")
                if message.type == "error"
                else None,
            )
            page.on(
                "pageerror",
                lambda error: console_errors.append(f"PAGEERROR: {error}"),
            )

            for route in ROUTES:
                check_route(page, route, label, failures)

            if label == "375":
                check_sheet_keyboard(page, "today", "[data-reflection]", failures)
                check_sheet_keyboard(page, "nutrition", "[data-add-meal]", failures)
                check_sheet_keyboard(page, "sleep", "[data-sleep-edit]", failures)

            context.close()
        browser.close()

    for message in console_errors:
        failures.append(f"console: {message}")

    if failures:
        print("\nFAILED:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print(f"\nOK: {len(ROUTES) * len(VIEWPORTS)} screens, 0 console errors")
    return 0


if __name__ == "__main__":
    sys.exit(main())
