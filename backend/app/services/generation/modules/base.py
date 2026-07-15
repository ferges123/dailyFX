from dataclasses import dataclass


@dataclass
class GenerationResult:
    title: str
    summary: str
    image_bytes: bytes
    generation_type: str
    provider: str
    model: str
    config: dict
    source_asset_ids: list[str]
    output_format: str = "png"
    frame_count: int | None = None
