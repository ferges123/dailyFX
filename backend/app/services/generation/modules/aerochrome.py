from __future__ import annotations

import cv2
import numpy as np
from PIL import Image, ImageEnhance

from app.models.settings import SettingsModel
from app.services.generation.modules.base import GenerationResult
from app.services.generation.modules.common import add_grain, apply_vignette, load_rgb, save_png


class AerochromeModule:
    name = "aerochrome"
    label = "Kodak Aerochrome"
    description = "Infrared film simulation turning green foliage into vivid red/pink, with cool teal skies."
    default_weight = 2
    default_config = {
        "red_hue": 170,
        "foliage_sensitivity": 20,
        "saturation_boost": 1.3,
        "sky_cyan_shift": "1",
    }
    config_schema = [
        {
            "key": "red_hue",
            "label": "Red/Pink Hue",
            "type": "number",
            "description": "Foliage hue target (140 = Pink/Magenta, 170 = Classic Crimson, 180 = Deep Red).",
            "min": 140,
            "max": 180,
            "step": 5,
            "default": 170,
        },
        {
            "key": "foliage_sensitivity",
            "label": "Green Sensitivity",
            "type": "number",
            "description": "Foliage detection range (10 = narrow/pure greens, 30 = wide/includes yellow/browns).",
            "min": 10,
            "max": 30,
            "step": 2,
            "default": 20,
        },
        {
            "key": "saturation_boost",
            "label": "Vibrancy Boost",
            "type": "number",
            "description": "Red foliage saturation multiplier.",
            "min": 1.0,
            "max": 1.8,
            "step": 0.1,
            "default": 1.3,
        },
        {
            "key": "sky_cyan_shift",
            "label": "Teal Skies",
            "type": "select",
            "description": "Shift blue skies towards a cool retro cyan/teal.",
            "options": [
                {"label": "Enabled", "value": "1"},
                {"label": "Disabled", "value": "0"},
            ],
            "default": "1",
        },
    ]

    async def run(self, page_items: list, config: dict, client, settings: SettingsModel) -> GenerationResult:
        asset = page_items[0]
        image_bytes = await client.get_asset_data(asset.id)
        source = load_rgb(image_bytes)

        red_hue = max(140, min(180, int(config.get("red_hue", 170) or 170)))
        foliage_sensitivity = max(10, min(30, int(config.get("foliage_sensitivity", 20) or 20)))
        saturation_boost = max(1.0, min(1.8, float(config.get("saturation_boost", 1.3) or 1.3)))
        sky_cyan_shift = str(config.get("sky_cyan_shift", "1")).strip() == "1"

        img_cv = cv2.cvtColor(np.array(source), cv2.COLOR_RGB2BGR)

        # Convert to HSV to shift colors
        hsv = cv2.cvtColor(img_cv, cv2.COLOR_BGR2HSV).astype(np.float32)
        h, s, v = cv2.split(hsv)

        # Foliage detection (greens and yellow-greens)
        # Center of foliage Hue in OpenCV HSV space is around 50 (greenish-yellow)
        lower_green = 50.0 - foliage_sensitivity
        upper_green = 50.0 + foliage_sensitivity

        # Calculate a smooth weight (feathering) based on distance to the foliage hue center
        dist = np.abs(h - 50.0)
        weight = 1.0 - (dist / foliage_sensitivity)
        weight = np.clip(weight, 0.0, 1.0)

        # Create foliage mask (where weight > 0)
        green_mask = (h >= lower_green) & (h <= upper_green)
        weight[~green_mask] = 0.0

        # Shift foliage Hue to target red_hue
        h = h * (1.0 - weight) + red_hue * weight

        # Boost saturation of shifted foliage
        s = s * (1.0 - weight) + (s * saturation_boost) * weight
        s = np.clip(s, 0.0, 255.0)

        # Apply sky shift if enabled
        if sky_cyan_shift:
            # Blue skies are around Hue 100 to 125 in OpenCV
            sky_mask = (h >= 100.0) & (h <= 125.0)
            # Shift sky hue towards cyan/teal (OpenCV Hue 90)
            h[sky_mask] = np.clip(h[sky_mask] - 10.0, 85.0, 120.0)
            # Slightly desaturate sky to emulate old film chemistry
            s[sky_mask] = np.clip(s[sky_mask] * 0.9, 0.0, 255.0)

        # Merge channels and convert back to PIL Image
        hsv_new = cv2.merge([h, s, v]).astype(np.uint8)
        result_cv = cv2.cvtColor(hsv_new, cv2.COLOR_HSV2RGB)
        result = Image.fromarray(result_cv)

        # Film simulation aesthetics: enhance contrast & color saturation slightly
        result = ImageEnhance.Contrast(result).enhance(1.15)
        result = ImageEnhance.Color(result).enhance(1.05)

        # Add classic film grain and soft vignette
        result = add_grain(result, strength=0.08, blur=0.1)
        result = apply_vignette(result, strength=0.3)

        return GenerationResult(
            title=f"Aerochrome: {asset.original_file_name or asset.id}",
            summary="Infrared film simulation turning green foliage into vivid red/pink, with cool teal skies.",
            image_bytes=save_png(result),
            generation_type="aerochrome",
            provider="local",
            model="opencv",
            config={
                "red_hue": red_hue,
                "foliage_sensitivity": foliage_sensitivity,
                "saturation_boost": saturation_boost,
                "sky_cyan_shift": sky_cyan_shift,
            },
            source_asset_ids=[asset.id],
        )
