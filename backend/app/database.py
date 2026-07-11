import datetime
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.types import DateTime, TypeDecorator

from app.config import get_settings


class UTCDateTime(TypeDecorator):
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if value.tzinfo is None:
            return value.replace(tzinfo=datetime.timezone.utc)
        return value.astimezone(datetime.timezone.utc)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if value.tzinfo is None:
            return value.replace(tzinfo=datetime.timezone.utc)
        return value.astimezone(datetime.timezone.utc)


class Base(DeclarativeBase):
    pass


engine: Engine | None = None
SessionLocal = sessionmaker(autoflush=False, autocommit=False)
_current_database_url: str | None = None


def _ensure_engine() -> Engine:
    global engine, _current_database_url

    database_url = get_settings().database_url
    if engine is not None and database_url == _current_database_url:
        return engine

    if engine is not None:
        engine.dispose()

    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args = {
            "check_same_thread": False,
            "timeout": 30,
        }

    if database_url.startswith("sqlite") and "test" in database_url:
        from sqlalchemy.pool import NullPool

        engine = create_engine(
            database_url,
            connect_args=connect_args,
            poolclass=NullPool,
        )
    else:
        engine = create_engine(
            database_url,
            connect_args=connect_args,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            pool_timeout=30,
        )

    if database_url.startswith("sqlite"):
        from sqlalchemy import event

        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()

    SessionLocal.configure(bind=engine)
    _current_database_url = database_url
    return engine


def get_db() -> Generator[Session, None, None]:
    _ensure_engine()
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


_initialized_databases: set[str] = set()


def init_db() -> None:
    global _initialized_databases
    _ensure_engine()
    database_url = get_settings().database_url
    if database_url in _initialized_databases:
        return

    from alembic import command
    from alembic.config import Config

    import app.models  # noqa: F401
    from app.services.generation.bootstrap import bootstrap_builtin_ai_effects

    backend_root = Path(__file__).resolve().parents[1]
    alembic_ini_path = backend_root / "alembic.ini"
    if not alembic_ini_path.exists():
        # Fallback to alternative paths inside Docker container or cwd
        for fallback in [
            Path("/app/alembic.ini"),
            Path.cwd() / "alembic.ini",
            Path.cwd() / "backend" / "alembic.ini",
        ]:
            if fallback.exists():
                alembic_ini_path = fallback
                break
    alembic_cfg = Config(str(alembic_ini_path))
    alembic_cfg.set_main_option("script_location", str(backend_root / "app" / "migrations"))

    command.upgrade(alembic_cfg, "head")
    bootstrap_builtin_ai_effects()

    # Backfill asset usage registry from existing history
    db = SessionLocal()
    try:
        from app.services.generation.asset_usage import backfill_asset_usage

        backfill_asset_usage(db)
    finally:
        db.close()

    _initialized_databases.add(database_url)
