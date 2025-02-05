install:
	pip install -r requirements.txt
	pip install -e .

lint:
	ruff check .
	mypy .

lint-autofix:
	ruff check . --fix
	mypy .

format-check:
	ruff format . --check

format:
	ruff format .
