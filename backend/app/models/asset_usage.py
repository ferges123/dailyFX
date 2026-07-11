from datetime import datetime

from sqlalchemy import Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, UTCDateTime


class AssetUsageModel(Base):
    __tablename__ = "asset_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    task_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    schedule_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    generation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    usage_source: Mapped[str] = mapped_column(String(20), nullable=False)  # "automatic" or "manual"
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # "pending", "accepted", "released"
    selected_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=func.now())
    accepted_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True, index=True)
    released_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    release_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)  # "rejected", "failed", "deleted"
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (UniqueConstraint("task_id", "asset_id", name="uq_asset_usage_task_asset"),)
