# Postupi AI

## English

Postupi AI is a service for applicants to Russian universities. It analyzes
only public competition lists and does not access personal accounts,
Gosuslugi, cookies, or private applicant systems.

### Pilot Status

ITMO is the primary 2026 pilot source. HSE is a controlled 2026 pilot with a
fresh public discovery request before each applicant-list request. The local
pilot imports one HSE bachelor group at a time. MIPT is monitor-only.

The observed 2025 identity namespace is:

```text
admissions_uid:observed_cross_university:2025
```

Cross-university matching and forecasting remain disabled by default.

### Privacy

- Raw applicant identifiers are not stored in the primary database.
- Technical matching uses namespaced HMAC-SHA256 hashes.
- The service does not expose other applicants' IDs, scores, applications,
  directions, or inferred preferences.
- There is no search by another applicant's identifier.
- Users can delete their data.
- Forecasts are not admission guarantees.
- HSE source response bodies are discarded after privacy-safe normalization.

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
# Set POSTUPI_UID_HMAC_SECRET and POSTUPI_INTERNAL_API_TOKEN in .env.
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

The bot supports `/start`, `/help`, and `/tracks`. Use **Add direction** to
select a university and competition group, then submit your applicant code.
The bot sends the code only to the internal API; the API converts it to a
namespaced HMAC before persistence.

Refresh the local HSE pilot from the public source:

```powershell
docker compose run --rm --build api python -m apps.worker.hse_ingestion
```

Docker-based validation commands:

```powershell
docker compose run --rm --no-deps --build api pytest -q
docker compose run --rm --no-deps --build api ruff check .
docker compose run --rm --no-deps --build api mypy apps packages
```

Never put raw source responses, applicant identifiers, credentials, or cookies
in Git, logs, public tests, or API responses.

### Status

The service includes a FastAPI API, Telegram tracking bot, internal
token-protected target API, ARQ worker, PostgreSQL, Redis, notifications,
health checks, JSON logging, ITMO 2026 ingestion, and a bounded HSE 2026
pilot ingestion path.

---

## Русский

Postupi AI — сервис для абитуриентов российских вузов. Он анализирует только
публичные конкурсные списки и не получает доступ к личным кабинетам,
Госуслугам, cookies или закрытым системам абитуриентов.

### Статус пилота

ИТМО — основной источник пилота кампании 2026. ВШЭ подключена как
контролируемый пилот кампании 2026: перед каждым запросом списка выполняется
свежее публичное discovery. Локальный пилот загружает по одной конкурсной
группе ВШЭ. МФТИ работает только в режиме мониторинга.

Наблюдаемый namespace идентичности для кампании 2025:

```text
admissions_uid:observed_cross_university:2025
```

Межвузовое сопоставление и прогнозирование по умолчанию отключены.

### Приватность

- Исходные идентификаторы абитуриентов не сохраняются в основной базе данных.
- Для технического сопоставления используются namespaced HMAC-SHA256 хеши.
- Сервис не раскрывает чужие ID, баллы, заявления, направления или
  предполагаемые предпочтения.
- Поиск по чужому идентификатору отсутствует.
- Пользователь может удалить свои данные.
- Прогноз не является гарантией зачисления.
- Ответы источника ВШЭ удаляются после privacy-safe нормализации.

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
# Укажите POSTUPI_UID_HMAC_SECRET и POSTUPI_INTERNAL_API_TOKEN в .env.
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

Бот поддерживает `/start`, `/help` и `/tracks`. Для добавления направления
нажмите **«Добавить направление»**, выберите вуз и конкурсную группу, затем
отправьте код абитуриента. Бот передаёт код только во внутренний API, где он
превращается в namespaced HMAC до сохранения.

Обновление локального пилота ВШЭ из публичного источника:

```powershell
docker compose run --rm --build api python -m apps.worker.hse_ingestion
```

Команды проверки в Docker:

```powershell
docker compose run --rm --no-deps --build api pytest -q
docker compose run --rm --no-deps --build api ruff check .
docker compose run --rm --no-deps --build api mypy apps packages
```

Не добавляйте в Git, логи, публичные тесты или ответы API исходные ответы
источников, UID абитуриентов, credentials или cookies.

### Текущий статус

Готовы FastAPI API, Telegram-бот для отслеживания, защищённый token API для
создания направлений, ARQ worker, PostgreSQL, Redis, уведомления, health
checks, JSON-логирование, ingestion ИТМО 2026 и ограниченный pilot ingestion
ВШЭ 2026.
