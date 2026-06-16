from __future__ import annotations

import logging
import random
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps
from pillow_heif import register_heif_opener

register_heif_opener()

logger = logging.getLogger(__name__)

PALETTE_POOL: list[tuple[tuple[int, int, int], tuple[int, int, int]]] = [
    ((255, 40, 80), (255, 230, 0)),
    ((0, 180, 255), (255, 80, 200)),
    ((80, 255, 120), (80, 0, 180)),
    ((255, 140, 0), (0, 220, 220)),
    ((200, 0, 255), (255, 255, 80)),
    ((0, 240, 180), (255, 30, 100)),
    ((255, 80, 0), (0, 80, 255)),
    ((180, 255, 0), (180, 0, 200)),
    ((255, 20, 180), (20, 255, 200)),
    ((0, 60, 255), (255, 200, 0)),
]


def load_rgb(image_bytes: bytes) -> Image.Image:
    if len(image_bytes) > 50 * 1024 * 1024:  # 50MB hard limit
        raise ValueError("Image too large (max 50MB)")
    img = Image.open(BytesIO(image_bytes))
    # Apply EXIF orientation
    img = ImageOps.exif_transpose(img) or img
    img = img.convert("RGB")
    # Downscale if too large (>3840px on any side)
    if max(img.size) > 3840:
        img.thumbnail((3840, 3840), Image.Resampling.LANCZOS)
    return img


def save_png(image: Image.Image) -> bytes:
    out = BytesIO()
    image.save(out, format="PNG", optimize=True)
    return out.getvalue()


def select_palette(config: dict[str, Any] | None = None) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    palette = (config or {}).get("palette")
    if (
        isinstance(palette, list)
        and len(palette) == 2
        and all(
            isinstance(item, list) and len(item) == 3 and all(isinstance(channel, int) for channel in item)
            for item in palette
        )
    ):
        return tuple(tuple(int(channel) for channel in item) for item in palette)  # type: ignore[return-value]
    return random.choice(PALETTE_POOL)


def add_grain(image: Image.Image, *, strength: float = 0.12, blur: float = 0.0) -> Image.Image:
    noise = Image.effect_noise(image.size, 24).convert("L")
    noise = ImageOps.autocontrast(noise)
    noise_rgb = Image.merge("RGB", (noise, noise, noise))
    blended = Image.blend(image, noise_rgb, strength)
    if blur > 0:
        blended = blended.filter(ImageFilter.GaussianBlur(radius=blur))
    return blended


def apply_vignette(image: Image.Image, *, strength: float = 0.45) -> Image.Image:
    width, height = image.size
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    inset = int(min(width, height) * 0.08)
    draw.ellipse((-inset, -inset, width + inset, height + inset), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=min(width, height) * 0.18))
    dark = Image.new("RGB", (width, height), (0, 0, 0))
    return Image.composite(image, dark, mask.point(lambda value: int(value * (1.0 - strength / 2))))


def apply_screen(base: Image.Image, overlay: Image.Image) -> Image.Image:
    return ImageChops.screen(base, overlay)


def get_font(name: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a font from static/fonts or fallback to standard ones."""
    # Path logic: common.py is in app/services/generation/modules/
    # We want app/static/fonts/
    base_path = Path(__file__).resolve().parent.parent.parent.parent
    font_path = base_path / "static" / "fonts" / f"{name}.ttf"

    # Try the requested font
    try:
        if font_path.exists():
            return ImageFont.truetype(str(font_path), size)
        logger.warning("Font not found at %s, trying fallbacks", font_path)
    except Exception as e:
        logger.error("Failed to load requested font %s: %s", name, e)

    # Hard fallback to DejaVuSans which we know exists and supports scaling
    fallback_path = base_path / "static" / "fonts" / "DejaVuSans.ttf"
    try:
        if fallback_path.exists():
            return ImageFont.truetype(str(fallback_path), size)
    except Exception:
        pass

    logger.error("ALL fonts failed (including DejaVu fallback). Using internal 10px default.")
    return ImageFont.load_default()


def frames_to_animation(
    frames: list[Image.Image],
    *,
    fps: int = 12,
    output_format: str = "gif",
    loop: int = 0,
    quality: int = 85,
    max_bytes: int = 10 * 1024 * 1024,
) -> bytes:
    import imageio.v3 as iio
    import numpy as np

    from app.services.generation.output_format import normalize_output_format

    if not frames:
        raise ValueError("Cannot create animation from empty frames")
    if fps <= 0:
        raise ValueError("Animation fps must be greater than zero")

    output_format = normalize_output_format(output_format)
    if output_format == "png":
        raise ValueError("frames_to_animation only supports gif and webp")

    working_frames = [frame.convert("RGB") for frame in frames]
    attempts: list[list[Image.Image]] = [
        working_frames,
        working_frames[::2] if len(working_frames) > 2 else working_frames,
    ]

    for attempt_index, attempt_frames in enumerate(attempts):
        frame_arrays = [np.array(frame) for frame in attempt_frames]
        kwargs = {"loop": loop, "duration": 1000 / fps}
        if output_format == "webp":
            kwargs["quality"] = quality if attempt_index == 0 else min(quality, 70)
        result = iio.imwrite("<bytes>", frame_arrays, extension=f".{output_format}", **kwargs)
        if len(result) <= max_bytes:
            return result

    resized = []
    for frame in working_frames[::2] if len(working_frames) > 2 else working_frames:
        copy = frame.copy()
        copy.thumbnail((800, 800), Image.Resampling.LANCZOS)
        resized.append(copy)
    frame_arrays = [np.array(frame) for frame in resized]
    kwargs = {"loop": loop, "duration": 1000 / fps}
    if output_format == "webp":
        kwargs["quality"] = min(quality, 70)
    return iio.imwrite("<bytes>", frame_arrays, extension=f".{output_format}", **kwargs)
