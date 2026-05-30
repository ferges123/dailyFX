.PHONY: backend-install backend-test backend-lint backend-format

backend-install:
	cd backend && if [ -d ".venv" ]; then .venv/bin/pip install -e ".[test,lint]"; else python3 -m pip install -e ".[test,lint]"; fi

backend-test:
	cd backend && if [ -d ".venv" ]; then .venv/bin/pytest; else python3 -m pytest; fi

backend-lint:
	cd backend && if [ -d ".venv" ]; then .venv/bin/ruff check app/api/routes_debug.py app/api/routes_settings.py app/schemas/presets.py app/schemas/settings.py tests/test_presets_routes.py tests/test_settings_routes.py app/utils/url_utils.py; else python3 -m ruff check app/api/routes_debug.py app/api/routes_settings.py app/schemas/presets.py app/schemas/settings.py tests/test_presets_routes.py tests/test_settings_routes.py app/utils/url_utils.py; fi

backend-format:
	cd backend && if [ -d ".venv" ]; then .venv/bin/ruff format app/api/routes_debug.py app/api/routes_settings.py app/schemas/presets.py app/schemas/settings.py tests/test_presets_routes.py tests/test_settings_routes.py app/utils/url_utils.py; else python3 -m ruff format app/api/routes_debug.py app/api/routes_settings.py app/schemas/presets.py app/schemas/settings.py tests/test_presets_routes.py tests/test_settings_routes.py app/utils/url_utils.py; fi
