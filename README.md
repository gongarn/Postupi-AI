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

### Forecasting

When `POSTUPI_FORECASTING_ENABLED=true`, the worker calculates a
`probabilistic-2` forecast after a new snapshot is processed. It is currently
limited to ITMO groups and is skipped unless all of these conditions hold:

- the tracked applicant is present in the newest valid list;
- the group has a known positive seat count for the applicant's admission
  condition;
- at least three valid snapshots are available for the same competition group.
- one complete, timestamped public batch covers every tracked ITMO bachelor
  budget group and provides verified university-wide priority semantics.

HSE forecasts are deliberately disabled because reliable per-condition seat
counts are not yet available.

The model estimates the probability as follows:

1. It selects candidates ranked ahead of the tracked applicant in the same
   admission condition. Candidates with a confirmed consented, higher-priority,
   passing application in another group in the same complete ITMO batch are
   excluded from this blocking cohort.
2. It calculates historical retention from each pair of valid snapshots: how
   many candidates in the previous list remain in the next one.
3. It applies a Beta prior with two retained and two departed pseudo-observations
   so limited history cannot produce an exact 0% or 100% retention estimate.
4. It groups candidates ahead using non-identifying signals and adjusts their
   chance of remaining: consent `+12%`, no consent `-18%`, priority 1 `+4%`,
   and priority above 3 `-2%`. A priority alone does not exclude a candidate:
   that requires a confirmed passing, consented higher-priority alternative.
5. It runs 4,000 deterministic Monte Carlo simulations. Each simulation samples
   which candidates remain, calculates the applicant's effective rank, and
   counts an admission if that rank is within the number of seats.

The central probability is the successful-simulation share. The displayed
range uses a conservative retention interval of plus/minus 1.28 standard
deviations: higher retention produces the lower probability bound, and lower
retention produces the upper bound. The model also records the 10th and 90th
percentiles of simulated effective rank.

The simulation seed is derived from the snapshot, rank, seat count, and
aggregate candidate cohorts, so identical inputs produce identical results.
Explanations contain only aggregate counts and model parameters; they never
contain applicant IDs, HMAC values, or source payloads.

The existing `deterministic-1` heuristic is saved as a shadow run for later
comparison. Historical retention is only a proxy for staying in a public list,
not confirmed final enrollment; no backtest calibration is claimed until final
admission labels are available. Forecasts are not admission guarantees.

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

Refresh every public ITMO bachelor budget group as one timestamped batch:

```powershell
docker compose run --rm --build api python -m apps.worker.itmo_ingestion
```

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

### Прогнозирование

При `POSTUPI_FORECASTING_ENABLED=true` worker рассчитывает прогноз
`probabilistic-2` после обработки нового snapshot. Сейчас он ограничен группами
ИТМО и не строится, если не выполнено хотя бы одно условие:

- отслеживаемый абитуриент есть в последнем valid списке;
- известно положительное число мест для его условия поступления;
- для одной конкурсной группы есть минимум три valid snapshot.
- один полный публичный batch покрывает все отслеживаемые бюджетные группы
  бакалавриата ИТМО и содержит подтверждённую семантику университетских
  приоритетов.

Прогнозы для ВШЭ намеренно отключены: пока нет надёжных данных о числе мест по
каждому условию поступления.

Расчёт вероятности устроен так:

1. Выбираются абитуриенты, стоящие выше отслеживаемого в том же условии
   поступления. Из этой группы исключаются кандидаты с подтверждённым согласием,
   более высоким приоритетом и проходной позицией в другом направлении того же
   полного batch ИТМО.
2. Для каждой пары valid snapshot рассчитывается историческая удерживаемость:
   сколько абитуриентов из предыдущего списка остаётся в следующем.
3. Применяется Beta prior с двумя условно оставшимися и двумя условно ушедшими
   наблюдениями, поэтому короткая история не даёт точную оценку удерживаемости
   в 0% или 100%.
4. Абитуриенты выше позиции группируются по неидентифицирующим признакам, а их
   вероятность остаться корректируется так: согласие `+12%`, нет согласия
   `-18%`, приоритет 1 `+4%`, приоритет выше 3 `-2%`. Один только приоритет не
   исключает кандидата: для этого нужен подтверждённый проходной выбор с
   согласием на более высоком приоритете.
5. Выполняются 4 000 детерминированных Monte Carlo симуляций. В каждой случайно
   определяется, кто остаётся в конкурсе, рассчитывается эффективная позиция
   абитуриента и проверяется, попадает ли она в число мест.

Центральная вероятность равна доле успешных симуляций. Диапазон строится по
консервативному интервалу удерживаемости плюс-минус 1,28 стандартного
отклонения: больше оставшихся абитуриентов даёт нижнюю границу вероятности,
меньше оставшихся - верхнюю. Дополнительно сохраняются 10-й и 90-й перцентили
эффективной позиции.

Seed симуляции строится из snapshot, позиции, числа мест и агрегированных групп
кандидатов, поэтому одинаковые входные данные дают одинаковый результат.
Explanation содержит только агрегированные счётчики и параметры модели, но
никогда не содержит ID абитуриентов, HMAC или исходные payload.

Текущая эвристика `deterministic-1` сохраняется параллельно как shadow-run для
последующего сравнения. Историческая удерживаемость означает только сохранение
в публичном списке, а не подтверждённое итоговое зачисление; до появления таких
данных backtest-калибровка не заявляется. Прогноз не является гарантией
поступления.

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

Обновление всех публичных бюджетных групп бакалавриата ИТМО одним
timestamped batch:

```powershell
docker compose run --rm --build api python -m apps.worker.itmo_ingestion
```

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
