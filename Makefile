.PHONY: backend-install backend-test backend-lint backend-format

backend-install:
	cd backend && if [ -d ".venv" ]; then .venv/bin/pip install -e ".[test,lint]"; else python3 -m pip install -e ".[test,lint]"; fi

backend-test:
	cd backend && if [ -d ".venv" ]; then .venv/bin/pytest; else python3 -m pytest; fi

backend-lint:
	cd backend && if [ -d ".venv" ]; then .venv/bin/ruff check .; else python3 -m ruff check .; fi

backend-format:
	cd backend && if [ -d ".venv" ]; then .venv/bin/ruff format .; else python3 -m ruff format .; fi
