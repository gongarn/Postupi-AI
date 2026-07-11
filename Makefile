.PHONY: install format lint typecheck test check up down

install:
	python -m pip install -e ".[dev]"

format:
	ruff format .

lint:
	ruff check .

typecheck:
	mypy apps packages

test:
	pytest -q

check: lint typecheck test

docker-test:
	docker compose run --rm --no-deps --build api pytest -q

docker-lint:
	docker compose run --rm --no-deps --build api ruff check .

docker-typecheck:
	docker compose run --rm --no-deps --build api mypy apps packages

migrate:
	docker compose run --rm api alembic upgrade head

migration-check:
	docker compose run --rm api alembic current --check-heads

up:
	docker compose up --build -d

down:
	docker compose down
