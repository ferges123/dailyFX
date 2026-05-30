import random
from io import BytesIO

from PIL import Image, ImageDraw, ImageOps

from app.models.settings import SettingsModel
from app.services.generation.modules.base import GenerationResult
from app.services.generation.modules.common import get_font

FILM_W = 1000
PHOTO_W = 700
PHOTO_H = 520
GAP = 40
TOP_MARGIN = 40
FRAMES = 3
SIDE_MARGIN = (FILM_W - PHOTO_W) // 2   # 150px each side
SIDE_W = SIDE_MARGIN
ACCENT = (255, 140, 140)
BG = (30, 31, 36)

# Zones within each side strip (offsets from frame top y):
TICK_TOP = 12
TICK_STEP = 11
TICK_COUNT = 3
TICK_W = 24
TRI_TOP = 56
TRI_H = 22
TEXT_ZONE_TOP_OFFSET = TRI_TOP + TRI_H + 16   # text starts here
TEXT_BOTTOM_MARGIN = 10
FONT_SIZE = 14

# frame 0 (top): show bottom 55% — crop top 45%
# frame 1 (middle): full
# frame 2 (bottom): show top 62% — crop bottom 38%
FRAME_CROP: dict[int, tuple[float, float]] = {
    0: (0.45, 1.0),   # (crop_from, crop_to) as fractions of PHOTO_H
    2: (0.0,  0.62),
}


class FilmstripModule:
    name = "filmstrip"
    label = "Filmstrip"
    description = "Retro filmstrip layout with date and time labels."
    default_weight = 1
    default_config = {"frame_style": "classic"}
    config_schema = [
        {
            "key": "frame_style",
            "label": "Frame style",
            "type": "select",
            "description": "Film frame style (classic/modern).",
            "options": [
                {"value": "classic", "label": "Classic"},
                {"value": "modern", "label": "Modern"},
            ],
            "default": "classic",
        },
    ]

    async def run(self, page_items: list, config: dict, client, settings: SettingsModel) -> GenerationResult:
        asset = random.choice(page_items)
        image_bytes = await client.get_asset_data(asset.id)

        date_label, time_label = _parse_datetime(asset.created_at)
        frame_style = config.get("frame_style", "classic")
        if frame_style not in ("classic", "modern"):
            frame_style = "classic"
        result_bytes = _build_filmstrip(image_bytes, date_label, time_label, frame_style)

        return GenerationResult(
            title=f"Filmstrip: {asset.original_file_name or asset.id}",
            summary="Film strip effect applied to an image.",
            image_bytes=result_bytes,
            generation_type="filmstrip",
            provider="local",
            model="pil",
            config={"frame_style": frame_style},
            source_asset_ids=[asset.id],
        )


def _parse_datetime(created_at: str | None) -> tuple[str, str]:
    if not isinstance(created_at, str):
        return ("", "")
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        return dt.strftime("%d %b %Y").upper(), dt.strftime("%H:%M")
    except ValueError:
        return ("", "")


def _frame_height(i: int) -> int:
    if i in FRAME_CROP:
        f, t = FRAME_CROP[i]
        return int(PHOTO_H * (t - f))
    return PHOTO_H


def _build_filmstrip(image_bytes: bytes, date_label: str, time_label: str, frame_style: str) -> bytes:
    src = Image.open(BytesIO(image_bytes)).convert("RGB")
    full = ImageOps.fit(src, (PHOTO_W, PHOTO_H))

    # total height accounts for variable frame heights
    heights = [_frame_height(i) for i in range(FRAMES)]
    film_h = TOP_MARGIN * 2 + sum(heights) + GAP * (FRAMES - 1)

    # Style-dependent background
    bg_color = (30, 31, 36) if frame_style == "classic" else (20, 22, 28)
    accent_color = (255, 140, 140) if frame_style == "classic" else (100, 180, 255)
    
    film = Image.new("RGB", (FILM_W, film_h), bg_color)
    draw = ImageDraw.Draw(film)

    try:
        font = get_font("DejaVuSans", FONT_SIZE)
        font_small = font
    except Exception:
        from PIL import ImageFont
        font = font_small = ImageFont.load_default()

    y = TOP_MARGIN
    for i in range(FRAMES):
        fh = heights[i]

        # crop vertically for side frames
        if i in FRAME_CROP:
            f, t = FRAME_CROP[i]
            y0, y1 = int(PHOTO_H * f), int(PHOTO_H * t)
            frame_img = full.crop((0, y0, PHOTO_W, y1))
        else:
            frame_img = full

        film.paste(frame_img, (SIDE_MARGIN, y))

        # side decorations on left and right strips
        for x_base, right in [(0, False), (SIDE_MARGIN + PHOTO_W, True)]:
            _draw_side(draw, font, font_small, x_base, y, fh, right, date_label, time_label, accent_color)

        y += fh + GAP

    out = BytesIO()
    film.save(out, format="PNG", optimize=True)
    return out.getvalue()


def _draw_side(draw, font, font_small, x_base: int, y: int, fh: int, right: bool, date_label: str, time_label: str, accent_color: tuple):
    cx = x_base + SIDE_W // 2

    # tick marks
    for k in range(TICK_COUNT):
        ty = y + TICK_TOP + k * TICK_STEP
        draw.rectangle((cx - TICK_W // 2, ty, cx + TICK_W // 2, ty + 4), fill=accent_color)

    # triangle
    ty = y + TRI_TOP
    draw.polygon([(cx - 14, ty), (cx + 14, ty), (cx, ty + TRI_H)], fill=accent_color)

    # vertical text — date and time as two separate rotated labels
    if not (date_label or time_label):
        return

    text_zone_top = y + TEXT_ZONE_TOP_OFFSET
    text_zone_bottom = y + fh - TEXT_BOTTOM_MARGIN

    def _rotated_label(text: str) -> Image.Image | None:
        # measure exact text size
        probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        try:
            tb = probe.textbbox((0, 0), text, font=font)
            tw, th = tb[2] - tb[0], tb[3] - tb[1]
        except AttributeError:
            tw, th = len(text) * FONT_SIZE, FONT_SIZE
        if tw <= 0:
            return None
        tmp = Image.new("RGB", (tw + 4, th + 6), BG)
        ImageDraw.Draw(tmp).text((2, 3), text, fill=accent_color, font=font)
        return tmp.rotate(90, expand=True)

    parts = [p for p in [date_label, time_label] if p]
    imgs = [r for p in parts if (r := _rotated_label(p)) is not None]
    if not imgs:
        return

    gap = 8
    total_h = sum(i.height for i in imgs) + gap * (len(imgs) - 1)
    available = text_zone_bottom - text_zone_top
    if available <= 0:
        return

    cy = text_zone_top + max(0, (available - total_h) // 2)
    for rot in imgs:
        h = min(rot.height, text_zone_bottom - cy)
        if h <= 0:
            break
        clipped = rot.crop((0, 0, rot.width, h))
        tx = x_base + (SIDE_W - clipped.width) // 2
        draw._image.paste(clipped, (tx, cy))
        cy += h + gap
