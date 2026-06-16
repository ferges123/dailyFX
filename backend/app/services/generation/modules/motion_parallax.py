from __future__ import annotations

import math

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from app.models.settings import SettingsModel
from app.services.generation.modules.base import GenerationResult
from app.services.generation.modules.common import frames_to_animation, load_rgb


class MotionParallaxModule:
    name = "motion_parallax"
    label = "Motion Parallax"
    description = "2.5D parallax separation of foreground and background."
    default_weight = 1
    source_asset_count = 1
    default_config = {"depth": 5, "speed": 1.0, "direction": "left"}
    config_schema = [
        {
            "key": "direction",
            "label": "Direction",
            "type": "select",
            "description": "Background panning direction.",
            "default": "left",
            "options": [
                {"value": "left", "label": "Left"},
                {"value": "right", "label": "Right"},
                {"value": "up", "label": "Up"},
                {"value": "down", "label": "Down"},
            ],
        },
        {
            "key": "depth",
            "label": "Depth",
            "type": "number",
            "description": "Parallax depth amount.",
            "default": 5,
            "min": 2,
            "max": 10,
            "step": 1,
        },
        {
            "key": "speed",
            "label": "Speed",
            "type": "number",
            "description": "Animation speed multiplier.",
            "default": 1.0,
            "min": 0.5,
            "max": 2.0,
            "step": 0.1,
        },
    ]

    def _get_foreground_mask(self, source: Image.Image) -> Image.Image:
        try:
            import cv2
            import numpy as np

            # Convert PIL image to numpy array
            img_np = np.array(source)
            # Ensure 3-channel BGR for GrabCut
            if img_np.ndim == 2:
                img_np = cv2.cvtColor(img_np, cv2.COLOR_GRAY2BGR)
            elif img_np.shape[2] == 4:
                img_np = cv2.cvtColor(img_np, cv2.COLOR_RGBA2BGR)
            else:
                img_np = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

            h, w = img_np.shape[:2]
            margin_x = int(w * 0.1)
            margin_y = int(h * 0.1)
            rect = (margin_x, margin_y, w - 2 * margin_x, h - 2 * margin_y)

            bgdModel = np.zeros((1, 65), np.float64)
            fgdModel = np.zeros((1, 65), np.float64)
            mask_cv = np.zeros((h, w), np.uint8)

            cv2.grabCut(img_np, mask_cv, rect, bgdModel, fgdModel, 3, cv2.GC_INIT_WITH_RECT)
            # GC_FGD = 1, GC_PR_FGD = 3
            fg_mask = np.where((mask_cv == 1) | (mask_cv == 3), 255, 0).astype(np.uint8)

            return Image.fromarray(fg_mask, mode="L")
        except Exception:
            # Fallback to soft center ellipse mask
            width, height = source.size
            mask = Image.new("L", (width, height), 0)
            draw = ImageDraw.Draw(mask)
            cx, cy = width / 2, height / 2
            rx, ry = width * 0.35, height * 0.35
            draw.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=255)
            return mask

    async def run(self, page_items: list, config: dict, client, settings: SettingsModel) -> GenerationResult:
        asset = page_items[0]
        source = load_rgb(await client.get_asset_data(asset.id))
        direction = str(config.get("direction") or "left")
        depth = int(config.get("depth", 5) or 5)
        speed = max(0.5, min(2.0, float(config.get("speed", 1.0) or 1.0)))

        # Obtain foreground mask
        mask = self._get_foreground_mask(source)

        frame_count = 24
        fps = int(12 * speed)
        frames = []

        for index in range(frame_count):
            phase = math.sin((index / frame_count) * 2 * math.pi)

            # Compute offsets
            if direction == "left":
                dx_bg = int(depth * 3.0 * phase)
                dy_bg = 0
                dx_fg = int(-depth * 1.0 * phase)
                dy_fg = 0
            elif direction == "right":
                dx_bg = int(-depth * 3.0 * phase)
                dy_bg = 0
                dx_fg = int(depth * 1.0 * phase)
                dy_fg = 0
            elif direction == "up":
                dx_bg = 0
                dy_bg = int(depth * 3.0 * phase)
                dx_fg = 0
                dy_fg = int(-depth * 1.0 * phase)
            elif direction == "down":
                dx_bg = 0
                dy_bg = int(-depth * 3.0 * phase)
                dx_fg = 0
                dy_fg = int(depth * 1.0 * phase)
            else:
                dx_bg = dy_bg = dx_fg = dy_fg = 0

            bg = ImageChops.offset(source, dx_bg, dy_bg)
            fg = ImageChops.offset(source, dx_fg, dy_fg)
            fg_mask = ImageChops.offset(mask, dx_fg, dy_fg)

            # Smooth mask edge
            fg_mask_blurred = fg_mask.filter(ImageFilter.GaussianBlur(radius=3))

            frame = Image.composite(fg, bg, fg_mask_blurred)
            frames.append(frame)

        output = frames_to_animation(frames, fps=fps, output_format="gif")
        return GenerationResult(
            title=f"Motion Parallax: {asset.original_file_name or asset.id}",
            summary="Animated 2.5D parallax separation.",
            image_bytes=output,
            generation_type=self.name,
            provider="local",
            model="pil+imageio",
            config={"direction": direction, "depth": depth, "speed": speed},
            source_asset_ids=[asset.id],
            output_format="gif",
            frame_count=frame_count,
        )
