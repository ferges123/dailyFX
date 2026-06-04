import random
from io import BytesIO

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from app.models.settings import SettingsModel
from app.services.generation.modules.base import GenerationResult
from app.services.generation.modules.common import add_grain

# Enhanced vivid colour pairs (dark, light)
_PALETTE_POOL = [
    ((255, 40, 80), (255, 240, 100)),  # Red-Yellow
    ((0, 180, 255), (255, 80, 200)),  # Blue-Pink
    ((80, 255, 120), (80, 0, 180)),  # Green-Purple
    ((255, 140, 0), (0, 220, 220)),  # Orange-Cyan
    ((200, 0, 255), (255, 255, 80)),  # Purple-Yellow
    ((0, 240, 180), (255, 30, 100)),  # Cyan-Red
    ((255, 80, 0), (0, 80, 255)),  # Orange-Blue
    ((180, 255, 0), (180, 0, 200)),  # Lime-Purple
    ((255, 20, 180), (20, 255, 200)),  # Magenta-Cyan
    ((0, 60, 255), (255, 200, 0)),  # Blue-Gold
]


class PopArtModule:
    name = "popart"
    label = "Pop Art"
    description = "Bold four-tile pop-art with vivid Warhol-style colors."
    default_weight = 1
    default_config = {"contrast": 2.2, "border": 12}
    config_schema = [
        {
            "key": "contrast",
            "label": "Contrast",
            "type": "number",
            "description": "Contrast intensity (1.5 = soft, 2.8 = extreme).",
            "min": 1.5,
            "max": 2.8,
            "step": 0.1,
            "default": 2.2,
        },
        {
            "key": "border",
            "label": "Border width",
            "type": "number",
            "description": "Border between tiles (0 = none, 24 = wide).",
            "min": 0,
            "max": 24,
            "step": 4,
            "default": 12,
        },
    ]

    async def run(self, page_items: list, config: dict, client, settings: SettingsModel) -> GenerationResult:
        asset = random.choice(page_items)
        image_bytes = await client.get_asset_data(asset.id)
        contrast = max(1.5, min(2.8, float(config.get("contrast", 2.2) or 2.2)))
        border = max(0, min(24, int(config.get("border", 12) or 12)))
        result_bytes = _build_popart(image_bytes, contrast, border)

        return GenerationResult(
            title=f"Pop Art: {asset.original_file_name or asset.id}",
            summary="Bold 4-tile pop art with vivid Warhol-style colors.",
            image_bytes=result_bytes,
            generation_type="popart",
            provider="local",
            model="pil",
            config={"contrast": contrast, "border": border},
            source_asset_ids=[asset.id],
        )


def _build_popart(image_bytes: bytes, base_contrast: float, border: int) -> bytes:
    src = Image.open(BytesIO(image_bytes)).convert("RGB")
    tile_w, tile_h = 600, 600
    src = ImageOps.fit(src, (tile_w, tile_h))

    # Enhanced preprocessing
    src = ImageEnhance.Sharpness(src).enhance(1.3)
    src = src.filter(ImageFilter.UnsharpMask(radius=1, percent=120))

    palettes = random.sample(_PALETTE_POOL, 4)
    tiles = []
    for dark, light in palettes:
        tiles.append(_popart_tile(src, dark, light, base_contrast))

    # Canvas with border
    canvas_w = tile_w * 2 + border
    canvas_h = tile_h * 2 + border
    collage = Image.new("RGB", (canvas_w, canvas_h), "#000000")

    for i, tile in enumerate(tiles):
        x = (i % 2) * (tile_w + border)
        y = (i // 2) * (tile_h + border)
        collage.paste(tile, (x, y))

    out = BytesIO()
    collage.save(out, format="PNG", optimize=True)
    return out.getvalue()


def _popart_tile(img: Image.Image, dark: tuple, light: tuple, contrast: float) -> Image.Image:
    gray = ImageOps.grayscale(img)
    gray = ImageOps.autocontrast(gray, cutoff=3)
    gray = ImageEnhance.Contrast(gray).enhance(contrast)
    gray = ImageEnhance.Sharpness(gray).enhance(2.0)

    # Posterize for bold graphic look
    gray = ImageOps.posterize(gray, 4)

    toned = ImageOps.colorize(gray, black=dark, white=light)
    toned = ImageEnhance.Color(toned).enhance(1.2)
    toned = add_grain(toned, strength=0.03, blur=0.0)

    return toned
