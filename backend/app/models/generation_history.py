from datetime import datetime

from sqlalchemy import Boolean, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, UTCDateTime


class GenerationHistoryModel(Base):
    __tablename__ = "generation_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    generation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING_REVIEW")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    source_asset_ids: Mapped[str] = mapped_column(Text, nullable=False)
    output_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    total_token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    config_json: Mapped[str] = mapped_column(Text, nullable=False)
    tags_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list of tag strings
    task_step: Mapped[str | None] = mapped_column(String(255), nullable=True)

    uploaded_asset_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    upload_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    album_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    album_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    album_created: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    album_updated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    accept_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    schedule_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )
