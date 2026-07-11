FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY pyproject.toml README.md ./
COPY apps ./apps
COPY packages ./packages
COPY docs ./docs
COPY tests ./tests
COPY alembic.ini ./alembic.ini
COPY infra ./infra
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir ".[dev]"

RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser
