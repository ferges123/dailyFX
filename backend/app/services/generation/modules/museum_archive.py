from __future__ import annotations

import logging
import random

logger = logging.getLogger(__name__)

from PIL import Image, ImageDraw, ImageEnhance, ImageOps

from app.models.settings import SettingsModel
from app.services.generation.ai_budget import AIUsageLimitExceededError
from app.services.generation.ai_vision import analyze_image
from app.services.generation.modules.base import GenerationResult
from app.services.generation.modules.common import apply_vignette, get_font, load_rgb, save_png
from app.services.generation.people_context import load_people_context


class MuseumArchiveModule:
    name = "museum_archive"
    label = "Museum Archive"
    description = "Fine-art gallery framing with elegant serif typography and passe-partout."
    default_weight = 3
    default_config = {"frame_style": "classic"}
    config_schema = [
        {
            "key": "frame_style",
            "label": "Frame style",
            "type": "select",
            "description": "Gallery frame style (classic/modern/minimal).",
            "options": [
                {"value": "classic", "label": "Classic"},
                {"value": "modern", "label": "Modern"},
                {"value": "minimal", "label": "Minimal"},
            ],
            "default": "classic",
        },
    ]

    async def run(self, page_items: list, config: dict, client, settings: SettingsModel) -> GenerationResult:
        asset = random.choice(page_items)
        image_bytes = await client.get_asset_data(asset.id)
        source = load_rgb(image_bytes)

        exif = await client.get_asset_exif(asset.id)
        location = exif.get("city") or exif.get("state") or exif.get("country") or "Unknown Location"
        date_str = _format_date(asset.created_at)

        frame_style = config.get("frame_style", "classic")
        if frame_style not in ("classic", "modern", "minimal"):
            frame_style = "classic"

        people_context = await load_people_context(client, asset)
        name_hint = ", ideally referencing the people" if people_context and people_context.names else ""
        vision_prompt = (
            "Analyze this image. Return a JSON object with two fields: "
            f"'title' (a short, creative 3-5 word title{name_hint}) and "
            "'summary' (a brief 1-2 sentence description of what is in the photo). "
            "Do not use markdown formatting like ```json, just return the raw JSON object."
        )

        try:
            vision = await analyze_image(
                settings,
                image_bytes,
                prompt=vision_prompt,
                context_hint=people_context.anonymized_prompt_hint() if people_context else None,
            )
            display_title = vision.title
            summary = vision.summary
        except AIUsageLimitExceededError:
            raise
        except Exception as exc:
            logger.warning("museum_archive: AI Vision failed, using filename fallback: %s", exc)
            display_title = (
                (asset.original_file_name or asset.id).split(".")[0].replace("_", " ").replace("-", " ").title()
            )
            summary = f"Art gallery presentation of a photo from {location}."

        framed = _build_museum_frame(source, f"{location} — {date_str}", display_title, frame_style)

        return GenerationResult(
            title=f"Archive: {display_title}",
            summary=summary,
            image_bytes=framed,
            generation_type="museum_archive",
            provider="local",
            model="pil+museum_layout",
            config={
                "frame_style": frame_style,
                **({"people_context": people_context.to_dict()} if people_context else {}),
            },
            source_asset_ids=[asset.id],
        )


def _build_museum_frame(source: Image.Image, info_line: str, filename: str, frame_style: str) -> bytes:
    # 1. Enhance photo for gallery look
    target_size = (1400, 1000)
    photo = ImageOps.fit(source, target_size, centering=(0.5, 0.5))
    photo = ImageEnhance.Color(photo).enhance(1.05)
    photo = ImageEnhance.Contrast(photo).enhance(1.1)
    photo = apply_vignette(photo, strength=0.2)

    # Style-dependent border
    if frame_style == "minimal":
        border_width = 1
        border_color = (200, 200, 200)
    elif frame_style == "modern":
        border_width = max(4, int(target_size[0] * 0.003))
        border_color = (20, 20, 20)
    else:  # classic
        border_width = max(2, int(target_size[0] * 0.002))
        border_color = (40, 40, 40)

    photo_with_border = ImageOps.expand(photo, border=border_width, fill=border_color)
    pw, ph = photo_with_border.size

    # 2. Canvas (Passe-partout) - Style-dependent margins
    if frame_style == "minimal":
        margin_top = int(ph * 0.10)
        margin_side = int(pw * 0.08)
        margin_bottom = int(ph * 0.25)
        canvas_color = (252, 252, 250)
    elif frame_style == "modern":
        margin_top = int(ph * 0.15)
        margin_side = int(pw * 0.10)
        margin_bottom = int(ph * 0.30)
        canvas_color = (240, 240, 238)
    else:  # classic
        margin_top = int(ph * 0.18)
        margin_side = int(pw * 0.12)
        margin_bottom = int(ph * 0.35)
        canvas_color = (245, 243, 235)

    canvas_w = pw + (margin_side * 2)
    canvas_h = ph + margin_top + margin_bottom

    canvas = Image.new("RGB", (canvas_w, canvas_h), canvas_color)
    draw = ImageDraw.Draw(canvas)

    # 3. Placement
    canvas.paste(photo_with_border, (margin_side, margin_top))

    # 4. Typography - Style-dependent
    if frame_style == "minimal":
        size_title = int(canvas_h * 0.020)
        size_info = int(canvas_h * 0.008)
    elif frame_style == "modern":
        size_title = int(canvas_h * 0.023)
        size_info = int(canvas_h * 0.009)
    else:  # classic
        size_title = int(canvas_h * 0.025)
        size_info = int(canvas_h * 0.010)

    font_title = get_font("PlayfairDisplay-Medium", size_title)
    font_info = get_font("Inter-Regular", size_info)

    # Draw Title - mt anchor (Middle Top)
    title_text = filename
    title_y = ph + margin_top + int(margin_bottom * 0.25)
    draw.text((canvas_w // 2, title_y), title_text, fill=(30, 30, 30), font=font_title, anchor="mt")

    # Measure Title Bounding Box to safely place info line below it
    t_bbox = draw.textbbox((canvas_w // 2, title_y), title_text, font=font_title, anchor="mt")
    actual_title_bottom = t_bbox[3]

    # Draw Info Line - Position relative to the actual bottom of the title
    info_y = actual_title_bottom + int(canvas_h * 0.04)  # 4% height gap
    draw.text((canvas_w // 2, info_y), info_line, fill=(100, 100, 95), font=font_info, anchor="mt")

    # 5. Fine details - style-dependent
    if frame_style != "minimal":
        bevel = max(1, int(canvas_w * 0.005))
        bevel_color = (220, 218, 210) if frame_style == "classic" else (200, 200, 200)
        draw.rectangle(
            (margin_side - bevel, margin_top - bevel, canvas_w - margin_side + bevel, ph + margin_top + bevel),
            outline=bevel_color,
            width=1,
        )

    return save_png(canvas)


def _format_date(created_at: str | None) -> str:
    if not isinstance(created_at, str):
        return "N/A"
    try:
        from datetime import datetime

        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        return dt.strftime("%Y")
    except Exception:
        return "N/A"
