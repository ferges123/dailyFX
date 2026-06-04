from collections.abc import Generator
import datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.types import TypeDecorator, DateTime
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

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

    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False}
        if database_url.startswith("sqlite")
        else {},
    )
    SessionLocal.configure(bind=engine)
    _current_database_url = database_url
    return engine


def get_db() -> Generator[Session, None, None]:
    _ensure_engine()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    import app.models  # noqa: F401
    from alembic import command
    from alembic.config import Config
    from app.services.generation.bootstrap import bootstrap_builtin_ai_effects

    _ensure_engine()
    alembic_cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "app" / "migrations"))

    command.upgrade(alembic_cfg, "head")
    bootstrap_builtin_ai_effects()
