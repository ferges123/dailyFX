from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, func, Table, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, UTCDateTime


schedule_notification_preset_association = Table(
    "schedule_notification_presets",
    Base.metadata,
    Column("schedule_id", Integer, ForeignKey("schedules.id", ondelete="CASCADE"), primary_key=True),
    Column("notification_preset_id", Integer, ForeignKey("notification_presets.id", ondelete="CASCADE"), primary_key=True),
)


class ScheduleModel(Base):
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    schedule_expr: Mapped[str] = mapped_column(String(100), nullable=False, default="weekly")
    filter_preset_id: Mapped[int] = mapped_column(Integer, ForeignKey("filter_presets.id"), nullable=False)
    effect_preset_id: Mapped[int] = mapped_column(Integer, ForeignKey("effect_presets.id"), nullable=False)
    
    notification_presets: Mapped[list["NotificationPresetModel"]] = relationship(
        "NotificationPresetModel",
        secondary=schedule_notification_preset_association,
        backref="schedules",
    )
    
    album_name: Mapped[str] = mapped_column(String(255), nullable=False, default="AI Photos")
    ai_vision_provider: Mapped[str] = mapped_column(String(50), nullable=False, default="none")
    ai_vision_model: Mapped[str] = mapped_column(String(100), nullable=False, default="gpt-4o-mini")
    ai_image_provider: Mapped[str] = mapped_column(String(50), nullable=False, default="none")
    ai_image_model: Mapped[str] = mapped_column(String(100), nullable=False, default="gpt-image-1")
    ai_prompt_enrichment: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_run_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    last_tick_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_tick_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now(), onupdate=func.now())
