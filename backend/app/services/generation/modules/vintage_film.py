from __future__ import annotations

import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageOps

from app.models.settings import SettingsModel
from app.services.generation.modules.base import GenerationResult
from app.services.generation.modules.common import add_grain, apply_vignette, load_rgb, save_png

# Film presets with S-curve parameters
_FILM_PRESETS = {
    "kodachrome": {
        "red_boost": 1.15,
        "green_boost": 0.95,
        "blue_boost": 0.90,
        "contrast": 1.25,
        "saturation": 1.20,
        "warmth": (255, 240, 220),
        "curve_strength": 0.6,  # S-curve intensity
    },
    "fuji": {
        "red_boost": 1.05,
        "green_boost": 1.10,
        "blue_boost": 1.05,
        "contrast": 1.15,
        "saturation": 1.15,
        "warmth": (245, 250, 255),
        "curve_strength": 0.5,
    },
    "agfa": {
        "red_boost": 1.10,
        "green_boost": 1.00,
        "blue_boost": 0.85,
        "contrast": 1.20,
        "saturation": 1.10,
        "warmth": (255, 245, 230),
        "curve_strength": 0.55,
    },
}


class VintageFilmModule:
    name = "vintage_film"
    label = "Vintage Film"
    description = "Authentic film stock with S-curve tone mapping."
    default_weight = 3
    default_config = {"film_type": "kodachrome", "fade": 0.5}
    config_schema = [
        {
            "key": "film_type",
            "label": "Film type",
            "type": "select",
            "description": "Classic film stock to emulate.",
            "options": [
                {"value": "kodachrome", "label": "Kodachrome (warm reds)"},
                {"value": "fuji", "label": "Fuji (cool greens)"},
                {"value": "agfa", "label": "Agfa (golden)"},
            ],
            "default": "kodachrome",
        },
        {
            "key": "fade",
            "label": "Fade amount",
            "type": "number",
            "description": "Aging/fading intensity (0.3 = subtle, 0.8 = heavy).",
            "min": 0.3,
            "max": 0.8,
            "step": 0.05,
            "default": 0.5,
        },
    ]

    async def run(self, page_items: list, config: dict, client, settings: SettingsModel) -> GenerationResult:
        asset = page_items[0]
        image_bytes = await client.get_asset_data(asset.id)
        source = load_rgb(image_bytes)

        film_type = config.get("film_type", "kodachrome")
        if film_type not in _FILM_PRESETS:
            film_type = "kodachrome"
        fade = max(0.3, min(0.8, float(config.get("fade", 0.5) or 0.5)))

        result = _apply_vintage_film_opencv(source, film_type, fade)

        return GenerationResult(
            title=f"Vintage Film: {asset.original_file_name or asset.id}",
            summary=f"Authentic {film_type} with film curves.",
            image_bytes=save_png(result),
            generation_type="vintage_film",
            provider="local",
            model="opencv+pil",
            config={"film_type": film_type, "fade": fade},
            source_asset_ids=[asset.id],
        )


def _apply_vintage_film_opencv(img: Image.Image, film_type: str, fade: float) -> Image.Image:
    """Apply vintage film with OpenCV S-curves and CLAHE."""
    preset = _FILM_PRESETS[film_type]

    # Convert to OpenCV
    img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

    # Apply S-curve (film characteristic curve)
    img_cv = _apply_film_curve(img_cv, preset["curve_strength"])

    # CLAHE for local contrast (film grain structure)
    lab = cv2.cvtColor(img_cv, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    lab = cv2.merge([l, a, b])
    img_cv = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    # Convert back to PIL for color processing
    result = Image.fromarray(cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB))

    # Split channels and apply color shifts
    r, g, b = result.split()
    r = ImageEnhance.Brightness(r).enhance(preset["red_boost"])
    g = ImageEnhance.Brightness(g).enhance(preset["green_boost"])
    b = ImageEnhance.Brightness(b).enhance(preset["blue_boost"])
    result = Image.merge("RGB", (r, g, b))

    # Film characteristics
    result = ImageEnhance.Contrast(result).enhance(preset["contrast"])
    result = ImageEnhance.Color(result).enhance(preset["saturation"])

    # Fade effect (lift blacks)
    result = ImageEnhance.Brightness(result).enhance(1.0 + fade * 0.15)
    result = ImageOps.autocontrast(result, cutoff=int(fade * 3))

    # Color cast overlay
    warmth = Image.new("RGB", img.size, preset["warmth"])
    result = Image.blend(result, warmth, fade * 0.08)

    # Authentic film grain
    result = add_grain(result, strength=0.08 + fade * 0.05, blur=0.3)
    result = apply_vignette(result, strength=0.3 + fade * 0.2)

    return result


def _apply_film_curve(img: np.ndarray, strength: float) -> np.ndarray:
    """Apply S-curve LUT for film characteristic curve."""
    # Create S-curve lookup table
    lut = np.zeros(256, dtype=np.uint8)
    for i in range(256):
        x = i / 255.0
        # S-curve formula: smooth transition with lifted shadows and compressed highlights
        y = x + strength * (np.sin(2 * np.pi * (x - 0.5)) / (2 * np.pi))
        y = np.clip(y, 0, 1)
        lut[i] = int(y * 255)

    # Apply LUT to each channel
    return cv2.LUT(img, lut)
