# Postupi AI

Postupi AI is a service for Russian university applicants. It analyzes only
public competition lists and does not access personal accounts, Gosuslugi,
cookies or private applicant systems.

## Pilot Status

ITMO is the primary pilot source and HSE is the secondary pilot source. MIPT
is monitor-only. The remaining twelve universities are deferred to 0A.2 and
do not block MVP infrastructure.

The 2025 observed identity namespace is
`admissions_uid:observed_cross_university:2025`. Cross-university matching and
forecasting are disabled by default until implemented and validated.

## Privacy

- Raw applicant identifiers are not stored in the primary database.
- Technical matching uses namespaced HMAC-SHA256 hashes.
- The service does not expose other applicants' IDs, scores, applications,
  directions or inferred preferences.
- There is no search by another applicant's identifier.
- Users can delete their data.
- Forecasts are not admission guarantees.

## Stack

- Python 3.12
- FastAPI
- aiogram 3
- PostgreSQL
- Redis
- ARQ
- SQLAlchemy 2 and Alembic
- Docker Compose
- pytest, Ruff and mypy

## Local Run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
uvicorn apps.api.main:app --reload
```

## Docker Run

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
docker compose run --rm --no-deps --build api mypy apps packages
```

Never put the ITMO raw fixture, source UIDs, credentials or cookies in Git,
logs, public tests or API responses. Stage 3 will use restricted local/object
storage for the real fixture.

## Status

The base infrastructure is available: FastAPI API, Telegram bot skeleton,
ARQ worker, Docker Compose, PostgreSQL, Redis, health checks, JSON logging and
the initial data feasibility audit.
