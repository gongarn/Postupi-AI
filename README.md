# Postupi AI

Postupi AI evaluates public university competition lists without accessing
personal accounts, Gosuslugi, cookies or private applicant systems.

## Stage 0A.1 Decision

ITMO is the primary pilot source and HSE is the secondary pilot source. MIPT
is monitor-only. The remaining twelve universities are deferred to 0A.2 and
do not block MVP infrastructure.

The 2025 observed identity namespace is
`admissions_uid:observed_cross_university:2025`. Cross-university matching and
forecasting are disabled by default until the corresponding feature is
implemented and validated.

## Local Run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
uvicorn apps.api.main:app --reload
```

The API exposes `/health/live` and `/health/ready`.

## Docker Run

```powershell
Invoke-RestMethod http://localhost:8000/health/live
Invoke-RestMethod http://localhost:8000/health/ready
```

The bot is opt-in and requires a real token in `.env`:

```powershell
```

Never put the ITMO raw fixture, source UIDs, credentials or cookies in Git,
logs, public tests or API responses. Stage 3 will use restricted local/object
storage for the real fixture.
