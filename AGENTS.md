# Postupi AI

## Назначение

Postupi AI — сервис для абитуриентов российских вузов. Он анализирует только
публичные конкурсные списки и не получает доступ к личным кабинетам,
Госуслугам, cookies или закрытым системам абитуриентов. Пользователь выбирает
вуз и конкурсную группу, привязывает свой код абитуриента и получает оценку
шансов поступления, динамику позиции и уведомления об изменениях.

## Текущий MVP

- ИТМО — основной источник пилота кампании 2026: полный timestamped batch всех
  публичных бюджетных групп бакалавриата.
- ВШЭ — контролируемый пилот кампании 2026: перед каждым запросом списка
  выполняется свежее публичное discovery; локальный пилот загружает по одной
  конкурсной группе бакалавриата.
- МФТИ — только режим мониторинга, прогнозы для пользователей отсутствуют.
- Telegram-бот (aiogram 3): `/start`, `/help`, `/tracks`; добавление направления
  через inline-сценарий «вуз → конкурсная группа → код абитуриента».
- Бот передаёт код абитуриента только во внутренний API; API превращает его в
  namespaced HMAC-SHA256 до сохранения. Raw UID не хранится.
- Внутренний API (FastAPI, token-protected): список конкурсных групп и создание
  user target; системные роуты с health/live и health/ready (PostgreSQL + Redis).
- ARQ-worker: почасовая загрузка batch ИТМО, цепочка ingest → diff → forecast →
  notify, health-маркер в Redis.
- Diff между snapshot'ами: appeared/disappeared/rank_changed/score_changed/
  priority_changed/consent_changed/status_changed/bvi_changed/
  advantages_changed/condition_changed.
- Прогноз `probabilistic-2` (Monte Carlo, 4 000 симуляций) для отслеживаемых
  групп ИТМО; эвристика `deterministic-1` сохраняется как shadow run для
  сравнения.
- Уведомления: сдвиг вероятности ≥ 10 п.п., смена confidence или значимые
  события рядом с позицией; доставка через бота с dedup по delivery_key.

Вне MVP: cross-university matching (по умолчанию выключен), прогнозы для ВШЭ и
МФТИ, backtest-калибровка прогнозов, публичный дашборд агрегатов, поиск по
чужому идентификатору (запрещён политикой приватности).

## Стек

- Python 3.12 (`requires-python = ">=3.12,<3.13"`).
- FastAPI и uvicorn.
- aiogram 3 и long polling.
- PostgreSQL и SQLAlchemy 2 (async, asyncpg).
- Redis и ARQ (`arq==0.26.3`, фиксированная версия).
- Alembic и Docker Compose.
- httpx для публичных источников.
- structlog для JSON-логов.
- pytest, pytest-asyncio, Ruff и mypy (strict) для проверок.

## Структура

```text
apps/
  api/                    # FastAPI: main, dependencies, healthcheck.
    routes/
      internal.py         # Token-protected внутренний API (группы, user targets).
      system.py           # /, /health/live, /health/ready.
  bot/                    # aiogram-бот.
    main.py               # Сборка bot + engine, polling, доставка уведомлений.
    handlers/system.py    # /start, /help, /tracks и inline-сценарий добавления.
    keyboards.py          # Reply и inline-клавиатуры, пагинация групп.
    presenters.py         # Тексты карточек направлений и прогнозов.
    service.py            # Чтение треков и прогнозов из БД.
    target_api.py         # Клиент внутреннего API бота.
    delivery.py           # Доставка pending-уведомлений через Telegram.
    runtime.py            # Глобальная session_factory для бота.
  worker/                 # ARQ.
    main.py               # WorkerSettings, cron: health + почасовой refresh ИТМО
                          # + ingest_universities_job (полчаса).
    jobs.py               # Цепочка ingest → diff → forecast → notify.
    itmo_ingestion.py     # Полный batch ИТМО одним timestamped batch.
    hse_ingestion.py      # Локальный пилот ВШЭ с fresh discovery.
    universal_ingestion.py# Общий ингейшн вузов из реестра (кроме ИТМО/ВШЭ/МФТИ).
packages/
  common/                 # config (Settings, env_prefix POSTUPI_), logging, runtime, uid.
  forecasting/            # engine, features, persistence, recompute.
  notifications/          # policy, service.
  parsers/                # base, itmo, hse, hse_client, ingestion, storage.
                          # registry (реестр источников), fetchers, html_tables,
                          # sources (сборка реестра), universal_fetchers,
                          # rnimu/mpei/misis/fa/stankin/msu/rudn/sechenov.
  persistence/            # base, models, repositories, event_repository, uow.
  diff.py                 # snapshot-diff-1 между двумя snapshot'ами.
  domain/                 # Зарезервировано (пока пусто).
infra/
  docker/Dockerfile
  migrations/versions/    # 0001_initial_schema → … → 0006_stage7_notifications.
docs/                     # data_feasibility_audit.md, matrix, шаблон аудита вуза.
tests/
  unit/                   # bot, common, forecasting, notifications, parsers, worker.
  integration/            # diff, forecasting, HSE fresh ingestion, persistence,
                          # private ITMO fixture (маркер private_fixture, вне CI).
```

Миграционная цепочка: `0001_initial_schema → 0002_stage3_campaign_year →
0003_stage3_application_fk → 0004_stage4_application_events →
0005_stage5_forecast_identity → 0006_stage7_notifications`.

## Инварианты

- Идентичность абитуриента хранится только как
  `HMAC-SHA256(secret, f"{identity_namespace}:{normalized_uid}")`; normalize —
  NFKC + strip. Raw UID не попадает в БД, логи, API-ответы, фикстуры в Git и
  публичные тесты. `POSTUPI_UID_HMAC_SECRET` обязателен для любого доступа к
  данным (`require_uid_hmac_secret` fail-fast).
- Наблюдаемый namespace кампании 2025: `admissions_uid:observed_cross_university:2025`.
  Для кампании 2026 namespace создаётся заново и ревалидируется до включения
  cross-university matching. Каждая конкурсная группа хранит свой
  `identity_namespace`.
- Snapshot неизменяем: `content_hash`, `fetched_at`, `parser_version`, `status`
  (`valid`/`partial`/`failed`), `raw_payload` (JSONB). Сырые ответы источников
  не сохраняются: оба ингейшена используют `DiscardingRawSnapshotStorage`.
- Batch ИТМО атомарен: все группы загружаются одним timestamped batch
  (`batch_id`, `expected_group_count`); если хоть одна группа вернула не-200,
  выбрасывается `RuntimeError` и ничего не сохраняется.
- ВШЭ: перед каждым запросом обязателен свежий публичный discovery; загружается
  одна группа; тело ответа источника удаляется после privacy-safe нормализации.
- Diff считается только между valid snapshot'ами одной группы; одинаковый
  `content_hash` → skip. Тип события ограничен CHECK-констрейнтом; событие
  содержит `before_json`/`after_json`, `detected_at` и `diff_version=snapshot-diff-1`;
  дубликаты diff исключаются unique-индексами (включая NULL-condition вариант).
- Прогноз `probabilistic-2` строится только для вузов из реестра
  (`packages/parsers/registry.py`) с `forecast_eligible=True` и когда
  одновременно выполнены: абитуриент есть в последнем valid списке, известен
  положительный `seat_count`, в группе ≥ 3 valid snapshot, полный batch покрывает
  все отслеживаемые бюджетные группы, `priority_kind=UNIVERSITY_ENROLLMENT`.
  Иначе пересчёт пропускается с `reason` — это нормальное поведение, не ошибка.
  ИТМО — единственный eligible источник на старте; новые вузы подключаются к
  прогнозу по одному после валидации (см. `docs/integration-plan.md`).
- Модель: Beta prior с двумя retained и двумя departed псевдонаблюдениями;
  коррекции когорт: consent `+12%`, нет consent `-18%`, priority 1 `+4%`,
  priority > 3 `-2%`; кандидаты с подтверждённым проходным consented-выбором на
  более высоком приоритете исключаются из блокирующей когорты; 4 000
  детерминированных Monte Carlo симуляций; seed из snapshot/rank/seat/когорт —
  одинаковый вход даёт одинаковый результат. Диапазон — консервативный интервал
  ±1.28σ удерживаемости; сохраняются 10-й и 90-й перцентили ранга.
- `explanation` прогноза содержит только агрегированные счётчики и параметры
  модели — никогда ID абитуриентов, HMAC или исходные payload.
- Прогноз не является гарантией зачисления; backtest-калибровка не заявляется
  до появления финальных меток зачисления.
- Уведомление значимо при `material_forecast` (сдвиг ≥ 0.10 или смена
  confidence) или `near_threshold_event` (appeared/disappeared/rank_changed).
  `delivery_key = SHA-256(target:snapshot:engine:reason)`; повторная доставка
  того же ключа не создаёт новую запись; статусы `pending/sent/retry`,
  `attempt_count` и `last_error_code` обновляются при доставке ботом.
- Внутренний API защищён `X-Internal-Token` (сравнение через `compare_digest`);
  без настроенного токена — 503. Университеты с code `test-*` не показываются.
  Дубликат user target → 409 Conflict.
- Worker-цепочка: `ingest_itmo_batch_job → diff_snapshot_job →
  forecast_recompute_job → notify_users_job`; forecast и notify выполняются
  только при `POSTUPI_FORECASTING_ENABLED=true`. Почасовой cron
  `enqueue_itmo_refresh`; health-маркер в Redis обновляется каждую секунду,
  max age по умолчанию 60 с. `max_jobs=5`, `max_tries=3`.
- Бот не принимает и не хранит чужие идентификаторы: код абитуриента уходит во
  внутренний API, HMAC-хэширование выполняется только там. Бот запускается
  только с настоящим токеном (fail-fast). Разметка сообщений — HTML
  (ParseMode.HTML).
- Сервис не раскрывает чужие ID, баллы, заявления, направления или
  предполагаемые предпочтения; поиск по чужому идентификатору отсутствует.
- Никогда не клади в Git `.env`, секреты, raw payload источников, фикстуры с
  реальными UID, логи и локальные артефакты. Не логируй токены и ключи.
- Тесты: `asyncio_mode=auto`, `testpaths=["tests"]`; маркер `private_fixture`
  требует локальную приватную фикстуру и исключён из обычного CI. Ruff:
  line-length 100, select E/F/I/B/UP. Mypy: strict, python 3.12.

## Конфигурация

Скопировать `.env.example` в `.env` и заполнить:

```text
POSTUPI_ENVIRONMENT=local
POSTUPI_LOG_LEVEL=INFO
POSTUPI_DATABASE_URL=postgresql+asyncpg://postupi:postupi@localhost:5432/postupi
POSTUPI_REDIS_URL=redis://localhost:6379/0
POSTUPI_UID_HMAC_SECRET=
POSTUPI_TELEGRAM_BOT_TOKEN=
POSTUPI_INTERNAL_API_TOKEN=
POSTUPI_INTERNAL_API_BASE_URL=http://api:8000
POSTUPI_CROSS_UNIVERSITY_MATCHING_ENABLED=false
POSTUPI_FORECASTING_ENABLED=false
POSTUPI_WORKER_HEALTH_KEY=postupi:worker:health
POSTUPI_WORKER_HEALTH_MAX_AGE_SECONDS=60
```

`.env`, учётные данные PostgreSQL и локальные артефакты исключены из Git.
PostgreSQL — единственный поддерживаемый backend. В Docker миграции выполняет
`make migrate` (или `docker compose run --rm api alembic upgrade head`);
миграции поверх Docker Compose (`postgres`, `redis`, `api`, `worker`, `bot`
в profile `bot`). Telegram ID хранится как `BIGINT`, поскольку может превышать
32-битный `INTEGER`.

## Команды

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
uvicorn apps.api.main:app --reload
```

Docker:

```powershell
docker compose up --build -d
docker compose --profile bot up --build -d bot
docker compose run --rm --build api python -m apps.worker.itmo_ingestion
docker compose run --rm --build api python -m apps.worker.hse_ingestion
docker compose run --rm --no-deps --build api pytest -q
docker compose run --rm --no-deps --build api ruff check .
docker compose run --rm --no-deps --build api mypy apps packages
```

Makefile: `install`, `format`, `lint`, `typecheck`, `test`, `check`,
`docker-test`, `docker-lint`, `docker-typecheck`, `migrate`, `migration-check`,
`up`, `down`.

## Правило актуализации

После каждого значительного изменения обновляй этот файл в том же наборе
изменений. Значительными считаются изменения пользовательского сценария,
архитектуры, модели данных, конфигурации, зависимостей, способа запуска,
проверок, ограничений MVP или известных рисков. Для локальных исправлений,
которые не меняют эти сведения, обновление не требуется.

## Git-правило

После каждого завершённого изменения проекта обязательно:

1. Запусти подходящие проверки.
2. Проверь `git status`, `git diff` и последние коммиты.
3. Убедись, что в изменения не попали `.env`, секреты, виртуальное окружение,
   кэши и другие локальные артефакты.
4. В итоговом отчёте предложи осмысленное название коммита.

Создавай коммит и выполняй push только после прямого запроса пользователя.
Не изменяй и не отменяй посторонние незакоммиченные изменения.
Не используй force push, `git reset --hard` или `git clean -fd` без явного разрешения.

Никогда не добавляй в Git `.env`, виртуальное окружение, кэши или другие
локальные артефакты.
