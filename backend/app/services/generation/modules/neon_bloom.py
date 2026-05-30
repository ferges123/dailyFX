from __future__ import annotations

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from app.models.settings import SettingsModel
from app.services.generation.modules.base import GenerationResult
from app.services.generation.modules.common import apply_screen, load_rgb, save_png, select_palette


class NeonBloomModule:
    name = "neon_bloom"
    label = "Neon Bloom"
    description = "Vivid bloom with glowing highlights and neon saturation."
    default_weight = 2
    default_config = {"bloom_radius": 10, "intensity": 1.4}
    config_schema = [
        {
            "key": "bloom_radius",
            "label": "Bloom radius",
            "type": "number",
            "description": "Glow spread (6 = tight, 16 = wide).",
            "min": 6,
            "max": 16,
            "step": 2,
            "default": 10,
        },
        {
            "key": "intensity",
            "label": "Intensity",
            "type": "number",
            "description": "Color saturation (1.2 = subtle, 1.6 = extreme).",
            "min": 1.2,
            "max": 1.6,
            "step": 0.1,
            "default": 1.4,
        },
    ]

    async def run(self, page_items: list, config: dict, client, settings: SettingsModel) -> GenerationResult:
        asset = page_items[0]
        image_bytes = await client.get_asset_data(asset.id)
        source = load_rgb(image_bytes)
        dark, light = select_palette(config)
        bloom_radius = max(6, min(16, int(config.get("bloom_radius", 10) or 10)))
        intensity = max(1.2, min(1.6, float(config.get("intensity", 1.4) or 1.4)))
        
        # Enhanced base
        base = ImageOps.autocontrast(source, cutoff=2)
        base = ImageEnhance.Color(base).enhance(intensity)
        base = ImageEnhance.Contrast(base).enhance(1.3)
        base = ImageEnhance.Sharpness(base).enhance(1.25)

        # Multi-layer bloom for richness
        glow1 = base.filter(ImageFilter.GaussianBlur(radius=bloom_radius))
        glow1 = ImageEnhance.Brightness(glow1).enhance(1.4)
        
        glow2 = base.filter(ImageFilter.GaussianBlur(radius=bloom_radius // 2))
        glow2 = ImageEnhance.Brightness(glow2).enhance(1.2)
        
        # Combine blooms
        bloom = apply_screen(base, glow1)
        bloom = apply_screen(bloom, glow2)
        
        # Subtle color tint
        tint = ImageOps.colorize(ImageOps.grayscale(bloom), black=dark, white=light)
        result = Image.blend(bloom, tint, 0.15)
        
        # Final polish
        result = ImageEnhance.Contrast(result).enhance(1.1)
        result = ImageEnhance.Sharpness(result).enhance(1.15)

        return GenerationResult(
            title=f"Neon Bloom: {asset.original_file_name or asset.id}",
            summary="Vivid bloom with glowing highlights and neon saturation.",
            image_bytes=save_png(result),
            generation_type="neon_bloom",
            provider="local",
            model="pil",
            config={"bloom_radius": bloom_radius, "intensity": intensity, "palette": [list(dark), list(light)]},
            source_asset_ids=[asset.id],
        )
