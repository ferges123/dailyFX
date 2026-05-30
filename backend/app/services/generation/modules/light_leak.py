from __future__ import annotations

import random

from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageOps

from app.models.settings import SettingsModel
from app.services.generation.modules.base import GenerationResult
from app.services.generation.modules.common import add_grain, apply_vignette, load_rgb, save_png


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

        # Color-specific leaks
        width, height = faded.size
        if color_mode == "cool":
            overlay = Image.new("RGB", (width, height), (120, 200, 255))
            accent = Image.new("RGB", (width, height), (30, 150, 220))
        elif color_mode == "sunset":
            overlay = Image.new("RGB", (width, height), (255, 140, 180))
            accent = Image.new("RGB", (width, height), (200, 80, 150))
        else:  # warm
            overlay = Image.new("RGB", (width, height), (255, 180, 100))
            accent = Image.new("RGB", (width, height), (255, 100, 40))
        
        # Build leak with screen blend
        leak = Image.new("RGB", (width, height), (0, 0, 0))
        leak = ImageChops.screen(leak, overlay)
        leak = ImageChops.screen(leak, accent)
        leak = leak.filter(ImageFilter.GaussianBlur(radius=max(width, height) * 0.15))
        leak = ImageChops.offset(leak, random.randint(-width // 10, width // 10), random.randint(-height // 12, height // 12))

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
            model="pil",
            config={"intensity": intensity, "color": color_mode},
            source_asset_ids=[asset.id],
        )
