# Discipline OS

Личный помощник для сна, движения, питания, чтения Библии и одного главного
дела дня. Один пользователь, один процесс: Telegram-бот, JSON API, Mini App и
планировщик напоминаний работают из одного FastAPI-приложения.

- Бот: `@vd_discipline_os_bot`
- Mini App: тёмный мобильный интерфейс на 6 экранов
- Стек: Python 3.10+, FastAPI, aiogram 3, SQLAlchemy 2 (async), SQLite,
  APScheduler, нативный JS + Chart.js
- Язык интерфейса и бота: русский

## Что умеет

| Блок | Возможности |
| --- | --- |
| Сон | цель по времени, запись за ночь, длительность, отклонение от графика, история и график |
| Тренировка | недельный план, режимы «полный» и «минимум», подходы/повторения/секунды/отдых, прогрессия, рекорды, восстановительные дни |
| Питание | 2 приёма пищи, необязательное окно питания, белок, вода, вес и талия, графики и динамика |
| Библия | минуты чтения, заметки, серия и недельная согласованность |
| Главное дело | один приоритет на день, вторичные задачи, вечерняя рефлексия |
| Статистика | неделя/месяц, процент дисциплины, серии, вехи, рекорды |
| Настройки | часовой пояс, расписание, цели, упражнения, напоминания, экспорт JSON |
| Бот | команды, inline-переключатели привычек, быстрые записи, напоминания, вечерний чек-ин |

Привычка дня считается выполненной по фактическим данным (сон записан,
тренировка засчитана, приёмы пищи есть, чтение отмечено, приоритет закрыт).
Ручное переключение в интерфейсе имеет приоритет над автологикой.
«Успешный день» — 60% и выше; пропуски не штрафуются.

## Быстрый старт

```bash
cd /root/projects/discipline-os
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Заполните `.env`:

```dotenv
ENVIRONMENT=development
DEV_MODE=true
BOT_TOKEN=123456:ваш-токен-от-BotFather
OWNER_TELEGRAM_ID=100000001
WEBAPP_URL=
DATABASE_URL=sqlite+aiosqlite:///./data/discipline.db
ENABLE_SCHEDULER=true
```

Запуск:

```bash
./scripts/dev.sh
# или
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

- Mini App: <http://127.0.0.1:8010/>
- Проверка: <http://127.0.0.1:8010/healthz>
- OpenAPI (не в production): <http://127.0.0.1:8010/api/docs>

Локальный браузер обращается к API с заголовком `X-Dev-Mode: 1`
(`DEV_MODE=true`). В production этот режим должен быть выключен.

Первый `/start` в Telegram закрепляет владельца: ID сохраняется в настройках,
дальше бот и API принимают только его. Если `OWNER_TELEGRAM_ID` задан заранее,
это происходит сразу.

## Telegram Mini App

Telegram открывает Web App только по публичному HTTPS-адресу. Локальный
`http://127.0.0.1:8010` подходит для браузера, но не для кнопки в Telegram.

1. Разместите приложение на HTTPS-домене (reverse proxy, VPS, туннель).
2. Укажите `WEBAPP_URL=https://ваш-домен/` в `.env`.
3. Перезапустите сервис и отправьте боту `/dashboard`.

Без `WEBAPP_URL` кнопка Mini App скрыта, но сам бот продолжает работать.
Подпись `initData` проверяется на сервере по HMAC-SHA256; токен бота на клиент
не попадает.

## Production

```dotenv
ENVIRONMENT=production
DEV_MODE=false
BOT_TOKEN=...
OWNER_TELEGRAM_ID=...
WEBAPP_URL=https://discipline.example.com/
ENABLE_SCHEDULER=true
```

- Запускайте **один** процесс: long polling не допускает два поллера с одним
  токеном, а APScheduler хранит задания в памяти.
- Поставьте HTTPS-терминацию перед приложением (Caddy, nginx, Traefik).
- `.env` должен быть с правами `600` и не попадать в git.
- SQLite-файл и каталог `data/` — единственное состояние; делайте резервные
  копии или используйте `/api/export`.
- Напоминания восстанавливаются из БД при старте с детерминированными ID и
  `replace_existing=True`, поэтому дубликаты после перезапуска не появляются.

## Напоминания по умолчанию

| Ключ | Время | Смысл |
| --- | --- | --- |
| `morning` | 06:00 | доброе утро |
| `bible` | 06:05 | чтение Библии |
| `exercise` | 06:45 | тренировка |
| `meal_1` | 11:00 | первый приём пищи |
| `meal_2` | 17:00 | второй приём пищи |
| `checkin` | 21:00 | вечерний чек-ин |
| `sleep` | 21:30 | подготовка ко сну |

Время меняется в `/settings` или на экране «Настройки». Часовой пояс влияет на
все расчёты, включая «сегодня» и расписание.

## Команды бота

```text
/start      — приветствие и главное меню
/today      — привычки и прогресс на сегодня
/exercise   — план тренировки и быстрая запись подхода
/food       — записать приём пищи
/sleep      — записать сон
/bible      — записать чтение
/priority   — главное дело дня
/checkin    — вечерняя рефлексия
/stats      — короткий отчёт
/settings   — напоминания и цели
/dashboard  — открыть Mini App
/help       — помощь
/cancel     — отменить ввод
```

## API

Все маршруты, кроме `/healthz`, требуют авторизацию:

- production: `X-Telegram-Init-Data: <initData>`;
- локально: `X-Dev-Mode: 1` при `DEV_MODE=true`.

| Метод | Путь | Назначение |
| --- | --- | --- |
| GET | `/api/dashboard` | день, привычки, приоритет, серия |
| POST | `/api/habits/{key}/toggle` | переключить привычку |
| GET | `/api/fitness` | план, подходы, прогрессия, рекорды |
| POST | `/api/fitness/sets` | добавить подход |
| DELETE | `/api/fitness/sets/{id}` | удалить подход |
| POST | `/api/fitness/complete` | засчитать тренировку |
| GET | `/api/nutrition` | приёмы пищи, вода, замеры, графики |
| POST | `/api/nutrition/meals` | добавить приём пищи |
| DELETE | `/api/nutrition/meals/{id}` | удалить приём пищи |
| POST | `/api/nutrition/water` | добавить воду |
| DELETE | `/api/nutrition/water/{id}` | удалить запись воды |
| POST | `/api/nutrition/measurements` | вес/талия за дату |
| GET | `/api/sleep` | сон, история, согласованность |
| POST | `/api/sleep` | записать/изменить сон |
| DELETE | `/api/sleep` | удалить запись сна |
| GET | `/api/bible` | чтение, серия, история |
| POST | `/api/bible` | записать чтение |
| DELETE | `/api/bible` | удалить чтение |
| GET | `/api/priority` | приоритет, задачи, рефлексия |
| PUT | `/api/priority` | сохранить приоритет и рефлексию |
| GET | `/api/stats?period=week\|month` | статистика |
| GET | `/api/settings` | настройки и напоминания |
| PUT | `/api/settings` | сохранить настройки |
| GET | `/api/export` | полный экспорт JSON |

## Тесты

```bash
pip install -r requirements-dev.txt
python3 -m pytest -q tests          # backend, временная SQLite
python3 scripts/e2e_smoke.py        # браузерный smoke против запущенного сервера
```

`scripts/e2e_smoke.py` проверяет 6 экранов на 375/768/1440 px, горизонтальный
скролл, ошибки консоли и закрытие sheet по Escape, а также обновляет скриншоты
в `staff/screenshots/`.

Профили и карта изменений — в `staff/test-strategy.json`. Дизайн-контракт — в
`staff/design-brief.md`, вердикт ревью — `staff/design-review.md`
(`DESIGN: PASS`), итоговый статус — `staff/final-report.md`.

## Структура

```text
app/
  api/            JSON endpoints
  bot/            aiogram handlers, keyboards, texts
  services/       доменная логика: привычки, фитнес, питание, сон, статистика
  static/         Mini App: HTML, CSS-токены, JS-экраны, vendor-библиотеки
  config.py       настройки из env
  database.py     async SQLite engine
  main.py         FastAPI, lifespan, бот, планировщик
  models.py       SQLAlchemy-модели
  security.py     проверка Telegram initData
data/             SQLite (не коммитится)
scripts/          dev.sh, e2e_smoke.py
staff/            дизайн-бриф, тест-стратегия, скриншоты
tests/            pytest
```

## Безопасность

- Токен бота и `OWNER_TELEGRAM_ID` — только в `.env`; в коде и репозитории их нет.
- `initData` проверяется по подписи и сроку; чужой Telegram ID получает 403.
- Pydantic-схемы ограничивают длины, диапазоны и форматы времени/дат.
- SQLAlchemy использует параметризованные запросы; SQL-конкатенации нет.
- CSP, `nosniff`, `Referrer-Policy`, `Permissions-Policy` выставляются middleware.
- Секреты не логируются; в логах только события и ошибки.
- `DEV_MODE=true` — только для локальной разработки, в production выключен.

## Ограничения MVP

- Один пользователь и один экземпляр приложения; социальных функций нет.
- SQLite без Alembic: схема создаётся при старте, изменения — аддитивные.
- Mini App требует HTTPS в Telegram; локальный браузер — через dev-режим.
- Калории и макросы не рассчитываются автоматически: пользователь вводит то,
  что знает, пустые значения не выдумываются.
