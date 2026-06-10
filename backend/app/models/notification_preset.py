from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Column, ForeignKey, Integer, String, Table, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, UTCDateTime

if TYPE_CHECKING:
    from app.models.push import PushSubscriptionModel

preset_push_subscription_association = Table(
    "preset_push_subscriptions",
    Base.metadata,
    Column(
        "notification_preset_id",
        Integer,
        ForeignKey("notification_presets.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "push_subscription_id",
        Integer,
        ForeignKey("push_subscriptions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class NotificationPresetModel(Base):
    __tablename__ = "notification_presets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    provider: Mapped[str] = mapped_column(String(100), nullable=False, default="web")
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    topic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    encrypted_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    webhook_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now(), onupdate=func.now())

    push_subscriptions: Mapped[list["PushSubscriptionModel"]] = relationship(
        "PushSubscriptionModel",
        secondary=preset_push_subscription_association,
        backref="notification_presets",
    )

