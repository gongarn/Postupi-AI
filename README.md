# Postupi AI

## English

Postupi AI is a service for applicants to Russian universities. It analyzes
only public competition lists and does not access personal accounts,
Gosuslugi, cookies, or private applicant systems.

### Pilot Status

ITMO is the primary pilot source and HSE is the secondary pilot source. MIPT
is monitor-only. The remaining twelve universities are deferred to 0A.2 and
do not block MVP infrastructure.

The observed 2025 identity namespace is:

```text
admissions_uid:observed_cross_university:2025
```

Cross-university matching and forecasting are disabled by default until they
are implemented and validated.

### Privacy

- Raw applicant identifiers are not stored in the primary database.
- Technical matching uses namespaced HMAC-SHA256 hashes.
- The service does not expose other applicants' IDs, scores, applications,
  directions, or inferred preferences.
- There is no search by another applicant's identifier.
- Users can delete their data.
- Forecasts are not admission guarantees.

### Stack

- Python 3.12
- FastAPI
- aiogram 3
- PostgreSQL
- Redis
- ARQ
- SQLAlchemy 2 and Alembic
- Docker Compose
- pytest, Ruff, and mypy

### Local Run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
uvicorn apps.api.main:app --reload
```

### Docker Run

```powershell
docker compose up --build -d
Invoke-RestMethod http://localhost:8000/health/live
Invoke-RestMethod http://localhost:8000/health/ready
```

Run the bot only with a real token in `.env`:

```powershell
docker compose --profile bot up --build -d bot
```

Docker-based validation commands:

```powershell
docker compose run --rm --no-deps --build api pytest -q
docker compose run --rm --no-deps --build api ruff check .
docker compose run --rm --no-deps --build api mypy apps packages
```

Never put the ITMO raw fixture, source UIDs, credentials, or cookies in Git,
logs, public tests, or API responses. Stage 3 will use restricted local or
object storage for the real fixture.

### Status

The base infrastructure is available: FastAPI API, Telegram bot skeleton,
ARQ worker, Docker Compose, PostgreSQL, Redis, health checks, JSON logging,
and the initial data feasibility audit.

---

## Русский

Postupi AI — сервис для абитуриентов российских вузов. Он анализирует только
публичные конкурсные списки и не получает доступ к личным кабинетам,
Госуслугам, cookies или закрытым системам абитуриентов.

### Статус пилота

ИТМО — основной источник пилота, ВШЭ — второй источник. МФТИ работает только
в режиме мониторинга. Остальные двенадцать вузов отложены до этапа 0A.2 и не
блокируют инфраструктуру MVP.

Наблюдаемый namespace идентичности для кампании 2025:

```text
admissions_uid:observed_cross_university:2025
```

Межвузовое сопоставление и прогнозирование по умолчанию отключены до их
реализации и валидации.

### Приватность

- Исходные идентификаторы абитуриентов не сохраняются в основной базе данных.
- Для технического сопоставления используются namespaced HMAC-SHA256 хеши.
- Сервис не раскрывает чужие ID, баллы, заявления, направления или
  предполагаемые предпочтения.
- Поиск по чужому идентификатору отсутствует.
- Пользователь может удалить свои данные.
- Прогноз не является гарантией зачисления.

### Стек

- Python 3.12
- FastAPI
- aiogram 3
- PostgreSQL
- Redis
- ARQ
- SQLAlchemy 2 и Alembic
- Docker Compose
- pytest, Ruff и mypy

### Локальный запуск

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
uvicorn apps.api.main:app --reload
```

### Запуск в Docker

```powershell
docker compose up --build -d
Invoke-RestMethod http://localhost:8000/health/live
Invoke-RestMethod http://localhost:8000/health/ready
```

Бот запускается только с настоящим токеном в `.env`:

```powershell
docker compose --profile bot up --build -d bot
```

Команды проверки в Docker:

```powershell
docker compose run --rm --no-deps --build api pytest -q
docker compose run --rm --no-deps --build api ruff check .
docker compose run --rm --no-deps --build api mypy apps packages
```

Не добавляйте в Git, логи, публичные тесты или ответы API raw fixture ИТМО,
исходные UID, credentials или cookies. На Этапе 3 реальный fixture будет
храниться в ограниченном локальном или объектном хранилище.

### Текущий статус

Базовая инфраструктура готова: FastAPI API, skeleton Telegram-бота, ARQ
worker, Docker Compose, PostgreSQL, Redis, health checks, JSON-логирование и
первичный аудит пригодности источников.
