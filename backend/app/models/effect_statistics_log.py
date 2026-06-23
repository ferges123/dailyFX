from datetime import datetime

from sqlalchemy import Boolean, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, UTCDateTime


class EffectStatisticsLogModel(Base):
    __tablename__ = "effect_statistics_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    effect_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True, index=True)
    liked: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now(), nullable=False)
