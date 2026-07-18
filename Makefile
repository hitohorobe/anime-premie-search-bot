.PHONY: lint fmt test

lint:
	uv run ruff check .

fmt:
	uv run ruff check --fix .
	uv run ruff format .

test:
	uv run pytest
