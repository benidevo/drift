.PHONY: help build run test lint format type-check clean setup-pre-commit

help:
	@echo "Available commands:"
	@echo "  make build           - Build Docker image"
	@echo "  make run             - Run development container"
	@echo "  make test            - Run tests in Docker"
	@echo "  make lint            - Run linting in Docker"
	@echo "  make format          - Format code in Docker"
	@echo "  make type-check      - Run type checking with mypy"
	@echo "  make clean           - Clean Docker images and containers"
	@echo "  make setup-pre-commit - Install pre-commit hooks"

build:
	docker compose build drift-dev

run:
	docker compose run --rm --remove-orphans drift-dev

test:
	docker compose run --rm --remove-orphans drift-dev poetry run pytest

lint:
	docker compose run --rm --remove-orphans drift-dev poetry run ruff check src tests

format:
	docker compose run --rm --remove-orphans drift-dev poetry run ruff format src tests

type-check:
	docker compose run --rm --remove-orphans -e PYTHONPATH=/app/src drift-dev poetry run mypy -p drift

clean:
	docker compose down -v
	docker images -q *drift* | xargs -r docker rmi -f

setup-pre-commit:
	poetry run pre-commit install
	poetry run pre-commit install --hook-type commit-msg
	@echo "Pre-commit hooks installed successfully!"
