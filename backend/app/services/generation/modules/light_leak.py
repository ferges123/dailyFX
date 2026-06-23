from __future__ import annotations

import random

import numpy as np
from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageOps

from app.models.settings import SettingsModel
from app.services.generation.modules.base import GenerationResult
from app.services.generation.modules.common import add_grain, apply_vignette, load_rgb, save_png

# Leak origin presets: (x_fraction, y_fraction) — where the leak starts
_LEAK_ORIGINS = [
    (0.9, 0.1),  # top-right
    (0.1, 0.9),  # bottom-left
    (0.85, 0.85),  # bottom-right
    (0.15, 0.15),  # top-left
    (0.5, 0.0),  # top-center
]


def _build_radial_gradient(width: int, height: int, cx: float, cy: float, color: tuple[int, int, int]) -> Image.Image:
    """Build a radial gradient image fading from *color* at (cx,cy) to black."""
    y_idx, x_idx = np.ogrid[:height, :width]
    dx = (x_idx - cx) / width
    dy = (y_idx - cy) / height
    dist = np.sqrt(dx * dx + dy * dy)
    # Normalize so the furthest corner is ~1.0
    max_dist = np.sqrt(2.0)
    alpha = np.clip(1.0 - dist / max_dist, 0.0, 1.0)
    # Apply gamma to shape the falloff (softer than linear)
    alpha = np.power(alpha, 1.8)

    arr = np.zeros((height, width, 3), dtype=np.uint8)
    arr[:, :, 0] = (color[0] * alpha).astype(np.uint8)
    arr[:, :, 1] = (color[1] * alpha).astype(np.uint8)
    arr[:, :, 2] = (color[2] * alpha).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


def _build_accent_gradient(width: int, height: int, cx: float, cy: float, color: tuple[int, int, int]) -> Image.Image:
    """Build a tighter accent gradient for depth."""
    y_idx, x_idx = np.ogrid[:height, :width]
    dx = (x_idx - cx) / width
    dy = (y_idx - cy) / height
    dist = np.sqrt(dx * dx + dy * dy)
    alpha = np.clip(1.0 - dist / 0.7, 0.0, 1.0)
    alpha = np.power(alpha, 2.5)

    arr = np.zeros((height, width, 3), dtype=np.uint8)
    arr[:, :, 0] = (color[0] * alpha).astype(np.uint8)
    arr[:, :, 1] = (color[1] * alpha).astype(np.uint8)
    arr[:, :, 2] = (color[2] * alpha).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


class LightLeakModule:
    name = "light_leak"
    label = "Light Leak"
    description = "Warm film leaks with faded blacks and dreamy glow."
    default_weight = 2
    default_config = {"intensity": 0.35, "color": "warm"}
    config_schema = [
        {
            "key": "intensity",
            "label": "Intensity",
            "type": "number",
            "description": "Leak intensity (0.2 = subtle, 0.5 = strong).",
            "min": 0.2,
            "max": 0.5,
            "step": 0.05,
            "default": 0.35,
        },
        {
            "key": "color",
            "label": "Color",
            "type": "select",
            "description": "Leak color tone.",
            "options": [
                {"value": "warm", "label": "Warm (orange/red)"},
                {"value": "cool", "label": "Cool (blue/cyan)"},
                {"value": "sunset", "label": "Sunset (pink/purple)"},
            ],
            "default": "warm",
        },
    ]

    async def run(self, page_items: list, config: dict, client, settings: SettingsModel) -> GenerationResult:
        asset = page_items[0]
        image_bytes = await client.get_asset_data(asset.id)
        source = load_rgb(image_bytes)
        intensity = max(0.2, min(0.5, float(config.get("intensity", 0.35) or 0.35)))
        color_mode = config.get("color", "warm")

        # Faded film look
        faded = ImageEnhance.Contrast(source).enhance(0.88)
        faded = ImageEnhance.Color(faded).enhance(1.15)
        faded = ImageEnhance.Brightness(faded).enhance(1.08)

        width, height = faded.size

        # Color-specific leak palettes
        if color_mode == "cool":
            primary = (120, 200, 255)
            accent = (30, 150, 220)
        elif color_mode == "sunset":
            primary = (255, 140, 180)
            accent = (200, 80, 150)
        else:  # warm
            primary = (255, 180, 100)
            accent = (255, 100, 40)

        # Pick a random origin for the leak
        ox_frac, oy_frac = random.choice(_LEAK_ORIGINS)
        # Add some jitter
        ox = ox_frac * width + random.randint(-width // 10, width // 10)
        oy = oy_frac * height + random.randint(-height // 12, height // 12)
        ox = max(0, min(width - 1, ox))
        oy = max(0, min(height - 1, oy))

        # Build radial gradients
        overlay = _build_radial_gradient(width, height, ox, oy, primary)
        accent_img = _build_accent_gradient(width, height, ox, oy, accent)

        # Compose leak: screen blend the two radial gradients
        leak = ImageChops.screen(overlay, accent_img)
        # Soften with blur
        leak = leak.filter(ImageFilter.GaussianBlur(radius=max(width, height) * 0.12))

        # Blend with intensity control
        combined = Image.blend(faded, leak, intensity)
        combined = add_grain(combined, strength=0.07, blur=0.12)
        combined = apply_vignette(combined, strength=0.3)
        combined = ImageOps.autocontrast(combined, cutoff=1)

        return GenerationResult(
            title=f"Light Leak: {asset.original_file_name or asset.id}",
            summary=f"Dreamy {color_mode} film leak with faded contrast.",
            image_bytes=save_png(combined),
            generation_type="light_leak",
            provider="local",
            model="pil+numpy",
            config={"intensity": intensity, "color": color_mode},
            source_asset_ids=[asset.id],
        )
