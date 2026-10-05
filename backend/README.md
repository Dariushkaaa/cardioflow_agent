# CardioFlow Backend (FastAPI + PostgreSQL)

> Запуск всей системы (БД + бэкенд + агент + фронтенд) одной командой описан в корневом `README.md`.
> Ниже - запуск одного бэкенда отдельно.

Бэкенд-слой по спецификации `backend_1.md`: REST + WebSocket, JWT, детерминированный риск-движок,
воркер эскалации (+2ч / итог дня 22:00 / потеря контакта), Alembic-миграции.

## Быстрый старт

Нужен Python 3.10+ (рекомендуется 3.11-3.12).

### Вариант A. PostgreSQL в Docker, приложение локально

```bash
docker run -d --name cardioflow-db -p 5432:5432 -e POSTGRES_USER=user -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=cardioflow_db postgres:16-alpine
python -m venv .venv
source .venv/bin/activate               # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Вариант B. Всё в Docker

Из корня репозитория: `docker compose up --build`.

### Вариант C. Без PostgreSQL (SQLite, для быстрой проверки)

В `.env` замените строку:

```
DATABASE_URL=sqlite+aiosqlite:///./cardioflow.db
```

и запустите `uvicorn app.main:app --reload --port 8000`.

После старта:
- Swagger: http://localhost:8000/docs
- Проверка: `python scripts/smoke_test.py` (при запущенном сервере)

При первом запуске (`AUTO_CREATE_TABLES=true`, `SEED_DEMO_DATA=true`) создаются таблицы,
демо-пациент `d3b07384-d113-4ec6-a563-9a3d46532401` («Иванов Иван Иванович») и слоты записи на ближайшие 5 дней.

## Как получить токен

В спецификации нет эндпоинта логина, поэтому для разработки добавлен:

```bash
curl -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"patient_id": "d3b07384-d113-4ec6-a563-9a3d46532401"}'
```

В Swagger нажмите **Authorize** и вставьте `access_token`. Токен живет 30 минут.
Для продакшена отключите эндпоинт: `ENABLE_DEV_TOKEN=false`.

WebSocket: `ws://localhost:8000/ws/patient/{patient_id}?token=<JWT>`
(при невалидном токене соединение закрывается с кодом 4008).

## Эндпоинты

| Метод | Путь | Назначение |
|---|---|---|
| POST | `/api/v1/reports/` | Отчет агента (Tool Calling): замер АД/пульса, прием/пропуск таблетки |
| GET | `/api/v1/patient/treatment-plan` | План терапии, целевые показатели, время приема |
| GET | `/api/v1/patient/measurements/latest` | Последний сохраненный замер (или `null`) |
| POST | `/api/v1/patient/schedule` | Расписание приема (интервал 8-12 ч, иначе 400) |
| GET | `/api/v1/slots/available?doctor_type=therapist&limit=3` | Свободные слоты |
| POST | `/api/v1/appointments/book` | Бронирование слота (повторная бронь -> 409) |
| WS | `/ws/patient/{patient_id}?token=` | Чат и события интерфейса |
| POST | `/api/v1/auth/token` | Выдача JWT для разработки |

События WS сервер -> клиент: `agent_message`, `new_measurement_status`, `show_appointment_slots`,
`patient_status_update`. Клиент -> сервер: `{"action": "send_message", "data": {"text": "..."}}` или `{"action": "init_onboarding"}`.

## Структура

```
app/
├── core/        config, database, security (JWT, IDOR), timeutils, seed
├── models/      patient, measurement, adherence, slot
├── schemas/     patient, report, slot
├── services/    risk_engine, schedule_validator, escalation_service, agent_client, adherence_service
├── api/         v1/endpoints (reports, patient, slots, auth), websockets (manager, endpoint)
├── worker/      tasks.py (APScheduler)
└── main.py
alembic/         миграции
scripts/         smoke_test.py (бэкенд), e2e_check.py (бэкенд + агент)
```

## Принятые допущения (в спецификации не определены)

- **Пороги риска** (`risk_engine.py`): critical при САД >= 160 или ДАД >= 100, САД < 90 или ДАД < 60,
  пульсе < 40 или > 130; warning при САД/ДАД >= цель + 10 (по умолчанию 140/90), пульсе < 50 или > 100.
  `action_required`: `book_appointment` (critical либо `skip_reason = side_effects`),
  `repeat_measurement` (warning), иначе `none`. Без числовых данных `risk_level = "unknown"`.
- **Контракт Agent Service**: бэкенд шлет `POST AGENT_SERVICE_URL` с телом
  `{"patient_id": "...", "text": "...", "event_type": "user_message"}` и свежим JWT пациента в `Authorization`;
  ожидает ответ `{"text": "...", "quick_replies": [...]}` (подойдут и ключи `reply_text`/`reply`/`message`).
  `event_type: "init_onboarding"` запрашивает приветствие (WS-действие `init_onboarding`). Если агент недоступен,
  пациент получит сообщение-заглушку.
- **Часовой пояс**: расписание, окно тишины и планировщик работают в `TIMEZONE` (по умолчанию Europe/Moscow).
  Время слотов записи хранится и отдается в UTC (суффикс `Z`).
- **Воркер**: сеансы создаются раз в минуту, напоминания уровня 1 проверяются каждые 5 минут,
  итог дня и проверка потери контакта идут в 22:00. Отчет с `medication_taken` закрывает активный сеанс
  (статус `completed`); если пациент был `lost_to_follow_up`, при новом отчете статус возвращается в `active`.
- **WebSocket-менеджер хранит соединения в памяти**: запускайте один процесс uvicorn (без `--workers N`).
  События, отправленные офлайн-пациенту, не сохраняются.
- Параметр `doctor_type` в `/slots/available` принимается, но не фильтрует: в схеме `appointment_slots` нет такого поля.

## Миграции Alembic

По умолчанию таблицы создаются автоматически при старте. Чтобы использовать Alembic, отключите это
(`AUTO_CREATE_TABLES=false` в `.env`) и выполните:

```bash
alembic upgrade head
```

Готовая начальная миграция лежит в `alembic/versions/0001_initial_schema.py`. Для новых изменений схемы:
`alembic revision --autogenerate -m "описание"`. Миграция рассчитана на PostgreSQL.
Не смешивайте оба способа на одной БД: если таблицы уже созданы автоматически, удалите их или пересоздайте БД
(`docker compose down -v`).
