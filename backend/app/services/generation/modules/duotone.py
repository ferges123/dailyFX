from __future__ import annotations

from PIL import ImageEnhance, ImageFilter, ImageOps

from app.models.settings import SettingsModel
from app.services.generation.modules.base import GenerationResult
from app.services.generation.modules.common import add_grain, apply_vignette, load_rgb, save_png, select_palette


class DuotoneModule:
    name = "duotone"
    label = "Duotone"
    description = "Rich duotone grading with depth and texture."
    default_weight = 2
    default_config = {"contrast": 1.4}
    config_schema = [
        {
            "key": "contrast",
            "label": "Contrast",
            "type": "number",
            "description": "Contrast intensity.",
            "min": 1.0,
            "max": 2.0,
            "step": 0.1,
            "default": 1.4,
        },
    ]

    async def run(self, page_items: list, config: dict, client, settings: SettingsModel) -> GenerationResult:
        asset = page_items[0]
        image_bytes = await client.get_asset_data(asset.id)
        base = load_rgb(image_bytes)
        dark, light = select_palette(config)
        contrast = max(1.0, min(2.0, float(config.get("contrast", 1.4) or 1.4)))
        
        # Enhanced grayscale conversion
        gray = ImageOps.grayscale(base)
        gray = ImageEnhance.Contrast(gray).enhance(contrast)
        gray = gray.filter(ImageFilter.UnsharpMask(radius=1.5, percent=150))
        
        # Apply duotone with midtones
        toned = ImageOps.colorize(gray, black=dark, white=light)
        
        # Add richness with color enhancement
        toned = ImageEnhance.Color(toned).enhance(1.15)
        toned = ImageEnhance.Sharpness(toned).enhance(1.25)
        
        # Subtle grain and vignette for depth
        toned = add_grain(toned, strength=0.08, blur=0.15)
        toned = apply_vignette(toned, strength=0.35)

        return GenerationResult(
            title=f"Duotone: {asset.original_file_name or asset.id}",
            summary="Rich duotone grading with depth and texture.",
            image_bytes=save_png(toned),
            generation_type="duotone",
            provider="local",
            model="pil",
            config={"contrast": contrast, "palette": [list(dark), list(light)]},
            source_asset_ids=[asset.id],
        )
