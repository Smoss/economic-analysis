.PHONY: setup test format lint typecheck check download-data dry-run-data

setup:
	uv sync --extra dev

test:
	uv run pytest

format:
	uv run ruff format economic_analysis tests

lint:
	uv run ruff check economic_analysis tests

typecheck:
	uv run mypy economic_analysis

check: lint typecheck test

download-data:
	uv run python -m economic_analysis fetch all

dry-run-data:
	uv run python -m economic_analysis fetch all --dry-run
