from __future__ import annotations

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

from app.models.settings import SettingsModel
from app.services.generation.modules.base import GenerationResult
from app.services.generation.modules.common import add_grain, apply_vignette, load_rgb, save_png, select_palette


def _duotone_lut(dark: tuple[int, int, int], light: tuple[int, int, int]) -> np.ndarray:
    """Build a 256-entry RGB lookup table mapping grayscale -> duotone.

    Uses a smoothstep (sigmoidal) curve rather than linear interpolation,
    which gives the duotone a more photographic transition through midtones
    (linear interpolation tends to flatten the mid-range).
    """
    t = np.linspace(0.0, 1.0, 256, dtype=np.float32)
    # Smoothstep: 3t^2 - 2t^3, slightly biased toward the light end
    s = t * t * (3.0 - 2.0 * t)
    dark_arr = np.array(dark, dtype=np.float32)
    light_arr = np.array(light, dtype=np.float32)
    lut = dark_arr[None, :] * (1.0 - s[:, None]) + light_arr[None, :] * s[:, None]
    return lut.clip(0.0, 255.0).astype(np.uint8)


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

        arr = np.asarray(base, dtype=np.float32)
        # Rec. 709 luma weights give a more perceptually accurate grayscale
        # than ImageOps.grayscale (which uses SDTV 0.299/0.587/0.114).
        gray = arr @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
        gray = gray.astype(np.float32)

        # Apply contrast as a pivot around mid-gray (128)
        gray = (gray - 128.0) * contrast + 128.0
        gray = np.clip(gray, 0.0, 255.0).astype(np.uint8)

        # Apply duotone via the smoothstep LUT
        lut = _duotone_lut(dark, light)
        toned_arr = lut[gray]
        toned = Image.fromarray(toned_arr, "RGB")

        # Unsharp mask for crisper edges (operates on the toned image so the
        # dark/light contrast is preserved).
        toned = toned.filter(ImageFilter.UnsharpMask(radius=1.5, percent=140))

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
            model="pil+numpy",
            config={"contrast": contrast, "palette": [list(dark), list(light)]},
            source_asset_ids=[asset.id],
        )
