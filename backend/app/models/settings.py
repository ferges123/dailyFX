from datetime import datetime

from sqlalchemy import Boolean, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, UTCDateTime


class SettingsModel(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    immich_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    encrypted_immich_api_key: Mapped[str | None] = mapped_column(String, nullable=True)
    encrypted_openai_api_key: Mapped[str | None] = mapped_column(String, nullable=True)
    encrypted_gemini_api_key: Mapped[str | None] = mapped_column(String, nullable=True)
    encrypted_openrouter_api_key: Mapped[str | None] = mapped_column(String, nullable=True)
    encrypted_byteplus_api_key: Mapped[str | None] = mapped_column(String, nullable=True)
    encrypted_xiaomi_api_key: Mapped[str | None] = mapped_column(String, nullable=True)
    encrypted_local_ai_api_key: Mapped[str | None] = mapped_column(String, nullable=True)
    local_ai_base_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    # Transient fields for generation pipeline backward compatibility (no database columns)
    default_ai_provider: str = "none"
    default_ai_model: str = "gpt-image-1"
    ai_image_provider: str = "none"
    ai_image_model: str = "gpt-image-1"
    ai_prompt_enrichment: bool = False
    ai_photo_selection_enabled: bool = False

    ai_vision_hourly_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    ai_image_hourly_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    debug_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    favorite_albums_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_custom_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )
