# CardioFlow Agent Service

Микросервис NLU/оркестрации: FastAPI + LangGraph (State Machine) + Pydantic Structured Output + Tool Calling в бэкенд через HTTPX +
RAG по утвержденным материалам + медицинские guardrails.

> Запуск всей системы одной командой описан в корневом `README.md`. Ниже - запуск одного агента.

## Локальный запуск

```bash
cd agent
python3.11 -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8001
```

Проверка: http://localhost:8001/health, Swagger: http://localhost:8001/docs. Для работы нужен запущенный бэкенд (`BACKEND_API_URL`).

Если `LLM_API_KEY` пуст, реплики разбираются по правилам (`_fallback_parse` в `app/graph/nodes.py`), внешних вызовов нет.
С ключом GigaChat (`app/llm/client.py`) модель выбирает функцию (Tool Calling), а числа проверяются по тексту сообщения. Сценарии диалога: `SCENARIOS.md`.

## API

`POST /api/v1/agent/process` (его вызывает бэкенд) и тот же обработчик на `POST /process`.
JWT пациента - в заголовке `Authorization: Bearer ...` либо в поле `jwt_token`.

```json
{ "patient_id": "d3b07384-d113-4ec6-a563-9a3d46532401", "text": "Давление 160/100, пульс 85, таблетку не принял, тошнит", "event_type": "user_message" }
```

(вместо `text` можно передать `message`; `event_type: "init_onboarding"` возвращает приветствие с назначениями врача)

```json
{ "reply_text": "...", "text": "...", "quick_replies": [], "action_required": "book_appointment", "events": [] }
```

## Граф

`init_onboarding` -> `greeting`; `appointment_booked` -> `booked`. Иначе `nlu` -> (`rag` | `plan` | `slots` | `report` -> (`confirm` | `clarify` -> `slots`) | `clarify` | `chat`).
Клинический риск и `action_required` приходят из ответа бэкенда (`POST /reports/`), агент их не вычисляет.

## RAG

Материалы - `.txt` файлы в `knowledge/` (абзацы разделяются пустой строкой). Индексация происходит при старте, внешних моделей нет.
Проверка поиска: `python -m app.tools.rag_retriever --query "сколько соли можно"`.
Если по вопросу ничего не найдено, агент не выдумывает ответ и предлагает передать вопрос врачу.

## Тесты

```bash
pytest -q
```

## Безопасность

Агент не ставит диагнозы, не меняет терапию и не придумывает назначения: используются только данные бэкенда.
