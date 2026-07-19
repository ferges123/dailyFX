from __future__ import annotations

import cv2
import numpy as np
from PIL import Image, ImageEnhance

from app.models.settings import SettingsModel
from app.services.generation.modules.base import GenerationResult
from app.services.generation.modules.common import load_rgb, save_png


class HDRModule:
    name = "hdr"
    label = "HDR"
    description = "HDR tone mapping with vivid colors and enhanced dynamic range."
    default_weight = 2
    default_config = {"algorithm": "drago", "gamma": 1.0}
    config_schema = [
        {
            "key": "algorithm",
            "label": "Algorithm",
            "type": "select",
            "options": [
                {"value": "drago", "label": "Drago (natural)"},
                {"value": "reinhard", "label": "Reinhard (vivid)"},
                {"value": "mantiuk", "label": "Mantiuk (cinematic)"},
            ],
            "default": "drago",
        },
        {
            "key": "gamma",
            "label": "Gamma",
            "type": "number",
            "description": "Output gamma (0.8 = dark, 1.5 = bright).",
            "min": 0.8,
            "max": 1.5,
            "step": 0.1,
            "default": 1.0,
        },
    ]

    async def run(self, page_items: list, config: dict, client, settings: SettingsModel) -> GenerationResult:
        asset = page_items[0]
        image_bytes = await client.get_asset_data(asset.id)
        source = load_rgb(image_bytes)

        algorithm = config.get("algorithm", "drago")
        if algorithm not in ("drago", "reinhard", "mantiuk"):
            algorithm = "drago"
        gamma = max(0.8, min(1.5, float(config.get("gamma", 1.0) or 1.0)))

        # Convert to float32 HDR-like input
        img_cv = cv2.cvtColor(np.array(source), cv2.COLOR_RGB2BGR)
        hdr = img_cv.astype(np.float32) / 255.0

        if algorithm == "drago":
            tonemap = cv2.createTonemapDrago(gamma=gamma, saturation=1.0, bias=0.85)
        elif algorithm == "reinhard":
            tonemap = cv2.createTonemapReinhard(gamma=gamma, intensity=0.0, light_adapt=0.8, color_adapt=0.0)
        else:  # mantiuk
            tonemap = cv2.createTonemapMantiuk(gamma=gamma, scale=0.7, saturation=1.0)

        ldr = tonemap.process(hdr)
        ldr = np.nan_to_num(ldr, nan=0.0, posinf=1.0, neginf=0.0)
        ldr = np.clip(ldr, 0.0, 1.0)

        # Local contrast enhancement (CLAHE on L channel of LAB). The global
        # tonemapper above compresses dynamic range, which can make the image
        # look flat. CLAHE restores local punch — the "HDR look" — by
        # enhancing contrast in small neighborhoods without changing global
        # brightness. This is what gives real HDR photos their characteristic
        # texture/detail pop.
        ldr_uint8 = (ldr * 255.0).astype(np.uint8)
        lab = cv2.cvtColor(ldr_uint8, cv2.COLOR_BGR2LAB)
        l_chan, a_chan, b_chan = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        l_chan = clahe.apply(l_chan)
        lab = cv2.merge([l_chan, a_chan, b_chan])
        ldr_uint8 = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

        result = Image.fromarray(cv2.cvtColor(ldr_uint8, cv2.COLOR_BGR2RGB))

        # Final saturation boost — HDR photography is typically vivid.
        result = ImageEnhance.Color(result).enhance(1.12)

        return GenerationResult(
            title=f"HDR: {asset.original_file_name or asset.id}",
            summary=f"HDR tone mapping with {algorithm} algorithm.",
            image_bytes=save_png(result),
            generation_type="hdr",
            provider="local",
            model="opencv",
            config={"algorithm": algorithm, "gamma": gamma},
            source_asset_ids=[asset.id],
        )
