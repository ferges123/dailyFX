# API Contract Tests

This folder contains contract tests that pin the exact JSON shape for the main backend API surfaces.

## Covered Areas

- `test_api_contracts_immich.py`
  - Immich options
  - Immich asset search results
- `test_api_contracts_generation.py`
  - generation task status
  - generation history page
- `test_api_contracts_settings_presets.py`
  - settings read/update responses
  - filter presets
  - effect presets
  - notification presets
- `test_api_contracts_settings_tests.py`
  - `settings/test-*` connection test responses
  - Immich connection test
  - OpenAI, Gemini, OpenRouter, BytePlus, and Xiaomi provider checks
- `test_api_contracts_notification_preset_tests.py`
  - notification preset test response payload
  - per-provider success and error aggregation shape

## Notes

- These tests intentionally assert exact response payloads, not just loose field subsets.
- Shared fixtures and fake objects live in [`backend/tests/_contract_helpers.py`](/home/ferges/Projects/dailyFX/backend/tests/_contract_helpers.py).
- `conftest.py` only adds the parent `tests/` directory to `sys.path` so the shared helpers stay importable from this subfolder.
