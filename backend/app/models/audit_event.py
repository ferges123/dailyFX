from datetime import datetime

from sqlalchemy import Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, UTCDateTime


class AuditEventModel(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    outcome: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    actor_type: Mapped[str] = mapped_column(String(50), nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    schedule_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    changes_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now())

    __table_args__ = (Index("ix_audit_events_target", "target_type", "target_id"),)
