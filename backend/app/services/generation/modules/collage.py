import random
from io import BytesIO

from PIL import Image, ImageEnhance, ImageOps

from app.services.generation.instafilter import AVAILABLE_FILTER_OPTIONS, AVAILABLE_FILTERS, apply_instafilter
from app.services.generation.modules.base import GenerationResult
from app.services.generation.modules.common import add_grain


class CollageModule:
    name = "collage"
    label = "Collage"
    description = "Four-filter collage with enhanced borders and depth."
    default_weight = 5
    source_asset_count = 4
    default_config = {"styles": ["random"], "border": 8}
    config_schema = [
        {
            "key": "styles",
            "label": "Styles",
            "type": "multiselect",
            "description": "Pick the Instagram-style filters used across collage tiles.",
            "options": AVAILABLE_FILTER_OPTIONS,
            "default": ["random"],
        },
        {
            "key": "border",
            "label": "Border width",
            "type": "number",
            "description": "Border between tiles (0 = none, 16 = wide).",
            "min": 0,
            "max": 16,
            "step": 2,
            "default": 8,
        },
    ]

    async def run(self, page_items: list, config: dict, client, settings=None) -> GenerationResult:
        tile_assets = _select_tile_assets(page_items)
        image_bytes_list = [await client.get_asset_data(asset.id) for asset in tile_assets]
        styles = _pick_styles(config)
        border = max(0, min(16, int(config.get("border", 8) or 8)))
        canvas_size = (1600, 1200)
        collage_bytes = _build_collage(image_bytes_list, styles, canvas_size, border)
        title_asset = tile_assets[0]

        return GenerationResult(
            title=f"Collage: {title_asset.original_file_name or title_asset.id}",
            summary="Four-filter collage with enhanced depth and borders.",
            image_bytes=collage_bytes,
            generation_type="collage",
            provider="local",
            model="pilgram+pil",
            config={"styles": styles, "border": border},
            source_asset_ids=[asset.id for asset in tile_assets],
        )


def _select_tile_assets(page_items: list) -> list:
    unique_assets = []
    seen_ids = set()
    for item in page_items:
        asset_id = getattr(item, "id", None)
        if asset_id in seen_ids:
            continue
        unique_assets.append(item)
        seen_ids.add(asset_id)
        if len(unique_assets) == 4:
            break
    if len(unique_assets) == 4:
        return unique_assets
    fallback = unique_assets[0] if unique_assets else random.choice(page_items)
    return [fallback, fallback, fallback, fallback]


def _pick_styles(config: dict) -> list[str]:
    configured = config.get("styles")
    pool = [s for s in configured if isinstance(s, str)] if isinstance(configured, list) else []
    if not pool:
        pool = AVAILABLE_FILTERS.copy()
    if len(pool) >= 4:
        return random.sample(pool, 4)
    repeated = pool.copy()
    while len(repeated) < 4:
        repeated.append(random.choice(pool))
    random.shuffle(repeated)
    return repeated[:4]


def _build_collage(
    image_bytes_list: list[bytes], styles: list[str], canvas_size: tuple[int, int], border: int
) -> bytes:
    w, h = canvas_size
    tw, th = max(1, (w - border) // 2), max(1, (h - border) // 2)

    # Dark background for borders
    collage = Image.new("RGB", (tw * 2 + border, th * 2 + border), "#0a0a0a")

    for i, style in enumerate(styles[:4]):
        image_bytes = image_bytes_list[i] if i < len(image_bytes_list) else image_bytes_list[0]
        filtered, _ = apply_instafilter(image_bytes, filter_name=style)
        tile = Image.open(BytesIO(filtered)).convert("RGB")
        tile = ImageOps.fit(tile, (tw, th), centering=(0.5, 0.5))

        # Subtle enhancement per tile
        tile = ImageEnhance.Sharpness(tile).enhance(1.1)
        tile = add_grain(tile, strength=0.02, blur=0.0)

        x = (i % 2) * (tw + border)
        y = (i // 2) * (th + border)
        collage.paste(tile, (x, y))

    out = BytesIO()
    collage.save(out, format="PNG", optimize=True)
    return out.getvalue()
