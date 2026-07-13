import os

import pytest

os.environ["APP_ACCESS_TOKEN"] = ""
os.environ.setdefault("APP_SECRET_KEY", "test-api-secret")

from app.immich.client import _client_cache
from app.limiter import limiter


@pytest.fixture(autouse=True)
def clear_immich_client_cache():
    _client_cache.clear()


@pytest.fixture(autouse=True)
def clear_settings_cache():
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def configure_limiter(request):
    if "test_rate_limits" not in request.node.fspath.strpath:
        limiter.enabled = False


@pytest.fixture(autouse=True)
def isolate_database(request):
    import os
    from pathlib import Path

    import app.database as database
    from app.config import get_settings

    module = request.module
    test_db = getattr(module, "test_db", None)
    if test_db is not None:
        db_url = f"sqlite:///{test_db}"
    else:
        project_root = Path(__file__).resolve().parents[2]
        test_data_dir = project_root / "data" / "tests" / "default"
        test_data_dir.mkdir(parents=True, exist_ok=True)
        db_url = f"sqlite:///{test_data_dir}/app.db"

    db_path = None
    if db_url.startswith("sqlite:///"):
        db_path = Path(db_url.replace("sqlite:///", ""))

    if database._current_database_url == db_url and (db_path is None or db_path.exists()):
        return

    os.environ["DATABASE_URL"] = db_url
    get_settings.cache_clear()

    if database.engine is not None:
        database.engine.dispose()
    database.engine = None
    database._current_database_url = None
    database._initialized_databases.clear()
