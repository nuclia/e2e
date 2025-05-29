install:
	uv sync --project nuclia_e2e --all-extras

lint:
	ruff check .
	mypy .

lint-autofix:
	ruff format .
	ruff check . --fix

format-check:
	ruff format . --check

format:
	ruff format .
