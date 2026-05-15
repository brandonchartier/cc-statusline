.PHONY: setup lint test

setup:
	git config core.hooksPath .githooks

lint:
	uv run ruff check .
	uv run ruff format --check .

test:
	uv run pytest
