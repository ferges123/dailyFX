import os
from pathlib import Path

# Ensure all tests run with development settings and database/data inside data/tests
project_root = Path(__file__).resolve().parents[2]
test_data_dir = project_root / "data" / "tests"
test_data_dir.mkdir(parents=True, exist_ok=True)

os.environ["APP_ENV"] = "development"
os.environ["APP_SECRET_KEY"] = "test-api-secret"
os.environ["DATA_DIR"] = str(test_data_dir)

if "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = f"sqlite:///{test_data_dir / 'app.db'}"

# Disable rate limiting globally during test suite execution
from app.limiter import limiter

limiter.enabled = False

