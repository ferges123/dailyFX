from datetime import datetime

from sqlalchemy import Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, UTCDateTime


class GenerationTaskModel(Base):
    __tablename__ = "generation_tasks"

    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    step: Mapped[str | None] = mapped_column(String(64), nullable=True)
    progress: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )
