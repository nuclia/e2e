fmt:
	ruff format e2e
	ruff check e2e  --select I --fix

lint:
	ruff check e2e
	ruff format --check e2e
	mypy e2e

install:
	pip install -r requirements.txt

install-test:
	pip install -r requirements-test.txt

venv:
	if [ "`pyenv local`" != "nua_e2e" ]; then \
		pyenv virtualenv 3.10.13 nua_e2e | true; \
		pyenv local nua_e2e; \
	fi
