from datetime import datetime

from sqlalchemy import Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, UTCDateTime


class GenerationTaskModel(Base):
    __tablename__ = "generation_tasks"

    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued", index=True)
    step: Mapped[str | None] = mapped_column(String(64), nullable=True)
    progress: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    source: Mapped[str] = mapped_column(String(20), nullable=False, default="run_now", index=True)
    schedule_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default="normal", index=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    parent_task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    root_task_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    queued_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    worker_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True, index=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_retryable: Mapped[bool] = mapped_column(default=False)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )
