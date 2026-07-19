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

        # Foliage detection with a smooth Gaussian-weighted falloff.
        # A linear weight (1 - dist/sensitivity) creates a hard cut at the
        # sensitivity boundary, which produces visible banding. A Gaussian
        # falloff produces a smooth transition where the foliage blend
        # gradually fades at the edges.
        # Center of foliage Hue in OpenCV HSV space is around 50 (greenish-yellow)
        dist = np.abs(h - 50.0)
        # Gaussian: weight = exp(-(dist/sigma)^2), sigma chosen so the
        # sensitivity range corresponds to ~2 sigma (covers ~95% of mass).
        sigma = foliage_sensitivity / 2.0
        weight = np.exp(-(dist * dist) / (2.0 * sigma * sigma))
        # Hard zero outside the sensitivity range (so unrelated hues are
        # not affected at all by the long Gaussian tail).
        weight = np.where(dist > foliage_sensitivity, 0.0, weight)

        # Shift foliage Hue to target red_hue. Hue is circular in HSV
        # (wraps at 180 in OpenCV's 0-180 range), so we use a circular
        # interpolation rather than a linear blend. Without this, shifting
        # green (50) to deep red (170) via linear interpolation passes through
        # yellow/orange — producing a sickly transitional tint in the
        # feathered edge instead of a clean red.
        # Circular: rotate h toward red_hue along the shorter arc.
        diff = red_hue - h
        # Wrap to [-90, 90]
        diff = ((diff + 90.0) % 180.0) - 90.0
        h_new = (h + diff * weight) % 180.0

        # Boost saturation of shifted foliage
        s_new = s * (1.0 - weight) + (s * saturation_boost) * weight
        s_new = np.clip(s_new, 0.0, 255.0)

        # Apply sky shift if enabled — also with a smooth Gaussian mask
        # so the transition is gradual rather than a hard hue step.
        if sky_cyan_shift:
            # Blue skies are around Hue 100 to 125 in OpenCV
            sky_center = 112.5
            sky_dist = np.abs(h_new - sky_center)
            sky_sigma = 12.5
            sky_weight = np.exp(-(sky_dist * sky_dist) / (2.0 * sky_sigma * sky_sigma))
            sky_weight = np.where(sky_dist > 25.0, 0.0, sky_weight)
            # Shift sky hue toward cyan/teal (OpenCV Hue ~90)
            sky_diff = 90.0 - h_new
            sky_diff = ((sky_diff + 90.0) % 180.0) - 90.0
            h_new = (h_new + sky_diff * sky_weight * 0.8) % 180.0
            # Slightly desaturate sky to emulate old film chemistry
            s_new = s_new * (1.0 - sky_weight * 0.1)

        # Merge channels and convert back to PIL Image
        hsv_new = cv2.merge([h_new, s_new, v]).astype(np.uint8)
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
