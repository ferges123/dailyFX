from __future__ import annotations

import logging
import random
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageChops, ImageFilter, ImageFont, ImageOps
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
    """Film-like grain: Gaussian luminance noise + subtle chroma noise.

    Unlike flat uniform noise, this mimics real film grain which has a
    roughly Gaussian distribution and a small color component.
    """
    width, height = image.size
    arr = np.asarray(image, dtype=np.float32)

    # Luminance grain: Gaussian, centered at 0 (additive deviation)
    sigma = 18.0 * (strength * 4.0)  # scale strength -> perceptible sigma
    luma_noise = np.random.normal(0.0, sigma, size=(height, width)).astype(np.float32)

    # Apply luminance noise with perceptual weighting (Rec. 709 luma weights),
    # so highlights get slightly more grain (film response curve).
    weights = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    luma_dev = arr @ weights  # H x W
    gain = 0.7 + 0.6 * (luma_dev / 255.0)  # shadows ~0.7, highlights ~1.3
    luma_noise = luma_noise * gain

    # Chroma noise: much weaker, independent per channel (gives subtle color shimmer)
    chroma_sigma = sigma * 0.18
    chroma_noise = np.random.normal(0.0, chroma_sigma, size=arr.shape).astype(np.float32)

    noisy = arr + luma_noise[:, :, None] + chroma_noise
    noisy = np.clip(noisy, 0.0, 255.0).astype(np.uint8)
    grain_img = Image.fromarray(noisy, "RGB")

    if blur > 0:
        # Slight blur mimics the diffuse quality of real film grain
        grain_img = grain_img.filter(ImageFilter.GaussianBlur(radius=blur))
    return grain_img


def apply_vignette(image: Image.Image, *, strength: float = 0.45) -> Image.Image:
    """Smooth radial vignette using a cosine-based falloff.

    Produces a natural darkening towards the edges/corners (cosine curve)
    rather than a hard elliptical mask. `strength` is the maximum darkening
    at the corners (0..1).
    """
    strength = max(0.0, min(1.0, strength))
    if strength <= 0.0:
        return image

    width, height = image.size
    # Normalized coordinates centered at image center
    y_idx, x_idx = np.ogrid[:height, :width]
    nx = (x_idx - width * 0.5) / (width * 0.5)
    ny = (y_idx - height * 0.5) / (height * 0.5)
    # Radial distance from center, normalized so corners reach ~1.0
    radius = np.sqrt(nx * nx + ny * ny)
    radius = np.clip(radius, 0.0, 1.0)
    # Cosine falloff: 1.0 at center, ~0.0 at corners
    falloff = np.cos(radius * (np.pi / 2.0))
    # Darkening factor: at center -> 1.0 (no change), at corners -> (1 - strength)
    factor = 1.0 - strength * (1.0 - falloff)

    arr = np.asarray(image, dtype=np.float32)
    darkened = (arr * factor[:, :, None]).clip(0.0, 255.0).astype(np.uint8)
    return Image.fromarray(darkened, "RGB")


def apply_screen(base: Image.Image, overlay: Image.Image) -> Image.Image:
    return ImageChops.screen(base, overlay)


@lru_cache(maxsize=128)
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
