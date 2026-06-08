from __future__ import annotations

import asyncio
import hashlib
import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
OUT_ROOT = REPO_ROOT / "tests" / "filter-showcase"
MODULE_OUT = OUT_ROOT / "modules"
STYLE_OUT = OUT_ROOT / "instafilters"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.generation.instafilter import AVAILABLE_FILTERS, apply_instafilter
from app.services.generation.modules import MODULES
from app.database import _ensure_engine


@dataclass(frozen=True)
class FakeAsset:
    id: str
    original_file_name: str
    created_at: str


class FakeClient:
    def __init__(self, image_bytes: bytes):
        self._image_bytes = image_bytes

    async def get_asset_thumbnail(self, asset_id: str, size: str = "preview"):
        return self._image_bytes, "image/png"

    async def get_asset_data(self, asset_id: str) -> bytes:
        return self._image_bytes

    async def get_asset_exif(self, asset_id: str) -> dict:
        return {
            "latitude": 52.0725,
            "longitude": 21.02,
            "dateTimeOriginal": "2025-06-04T12:34:56Z",
        }

    async def get_asset_info(self, asset_id: str) -> dict:
        return {
            "people": [
                {
                    "faces": [
                        {
                            "boundingBoxX1": 0.1,
                            "boundingBoxY1": 0.1,
                            "boundingBoxX2": 0.3,
                            "boundingBoxY2": 0.3,
                        }
                    ]
                }
            ]
        }

    def _coerce_face_summary(self, payload):
        from app.immich.client import ImmichClient
        return ImmichClient._coerce_face_summary(payload)


def _seed_for(label: str) -> int:
    return int(hashlib.sha1(label.encode("utf-8")).hexdigest()[:8], 16)


def _make_base_image(size: tuple[int, int] = (1600, 1200)) -> bytes:
    width, height = size
    image = Image.new("RGB", size, "#111827")
    draw = ImageDraw.Draw(image)

    for y in range(height):
        ratio = y / max(1, height - 1)
        r = int(20 + 180 * ratio)
        g = int(40 + 130 * ratio)
        b = int(90 + 40 * (1 - ratio))
        draw.line((0, y, width, y), fill=(r, g, b))

    # sun / sky accents
    draw.ellipse((1030, 120, 1360, 450), fill=(255, 210, 120))
    for i in range(6):
        x0 = 920 + i * 90
        draw.ellipse((x0, 180 + i * 8, x0 + 220, 330 + i * 10), fill=(255, 240, 220, 180))

    # distant mountains
    draw.polygon([(0, 640), (180, 520), (340, 590), (520, 450), (760, 620), (980, 500), (1200, 610), (1600, 540), (1600, 760), (0, 760)], fill=(64, 74, 104))
    draw.polygon([(0, 720), (260, 600), (470, 700), (730, 560), (980, 700), (1240, 580), (1600, 690), (1600, 900), (0, 900)], fill=(34, 44, 68))

    # foreground hills and road
    draw.polygon([(0, 880), (260, 820), (520, 900), (820, 830), (1120, 910), (1350, 860), (1600, 940), (1600, 1200), (0, 1200)], fill=(26, 82, 58))
    draw.polygon([(640, 1200), (760, 930), (840, 920), (940, 1200)], fill=(64, 64, 70))
    draw.polygon([(710, 1200), (795, 930), (805, 930), (890, 1200)], fill=(230, 230, 230))
    draw.rectangle((772, 920, 828, 1200), fill=(210, 170, 85))

    # stylized house
    draw.rectangle((180, 770, 420, 980), fill=(235, 220, 205))
    draw.polygon([(150, 780), (300, 670), (450, 780)], fill=(140, 60, 45))
    draw.rectangle((260, 860, 340, 980), fill=(95, 70, 50))
    draw.rectangle((215, 820, 255, 860), fill=(120, 180, 220))
    draw.rectangle((345, 820, 385, 860), fill=(120, 180, 220))

    # tree
    draw.rectangle((1250, 760, 1300, 1030), fill=(92, 58, 34))
    draw.ellipse((1160, 620, 1410, 860), fill=(40, 115, 70))
    draw.ellipse((1210, 560, 1380, 760), fill=(55, 145, 84))

    # rail / path details
    draw.line((0, 1080, 1600, 980), fill=(245, 228, 200), width=10)
    draw.line((0, 1110, 1600, 1010), fill=(180, 160, 130), width=3)

    # subtle grain and contrast
    image = ImageEnhance.Contrast(image).enhance(1.05)
    image = ImageEnhance.Sharpness(image).enhance(1.1)

    out = Path("/tmp/dailyfx_base.png")
    image.save(out, format="PNG", optimize=True)
    return out.read_bytes()


def _ensure_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in ("DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(candidate, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _save_image(image_bytes: bytes, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(image_bytes)


def _sanitize(name: str) -> str:
    return name.replace("/", "_").replace(" ", "_")


def _make_card(image_path: Path, title: str, subtitle: str | None = None, card_size: tuple[int, int] = (520, 420)) -> Image.Image:
    card_w, card_h = card_size
    canvas = Image.new("RGB", card_size, "#0b1020")
    draw = ImageDraw.Draw(canvas)
    title_font = _ensure_font(22)
    subtitle_font = _ensure_font(16)

    thumb_h = card_h - 78
    img = Image.open(image_path).convert("RGB")
    thumb = ImageOps.contain(img, (card_w - 24, thumb_h - 20), Image.Resampling.LANCZOS)
    thumb_bg = Image.new("RGB", (card_w - 24, thumb_h - 20), "#161b2d")
    offset = ((thumb_bg.width - thumb.width) // 2, (thumb_bg.height - thumb.height) // 2)
    thumb_bg.paste(thumb, offset)
    canvas.paste(thumb_bg, (12, 12))
    draw.rectangle((12, 12, card_w - 12, card_h - 12), outline="#35507a", width=2)
    draw.text((18, card_h - 54), title, fill="#f3f4f6", font=title_font)
    if subtitle:
        draw.text((18, card_h - 30), subtitle, fill="#9ca3af", font=subtitle_font)
    return canvas


def _make_contact_sheet(items: list[tuple[Path, str, str | None]], out_path: Path, columns: int = 3) -> None:
    if not items:
        return
    card_w, card_h = 520, 420
    padding = 18
    rows = (len(items) + columns - 1) // columns
    sheet = Image.new("RGB", (
        columns * card_w + (columns + 1) * padding,
        rows * card_h + (rows + 1) * padding,
    ), "#050814")

    for index, (img_path, title, subtitle) in enumerate(items):
        card = _make_card(img_path, title, subtitle, (card_w, card_h))
        x = padding + (index % columns) * (card_w + padding)
        y = padding + (index // columns) * (card_h + padding)
        sheet.paste(card, (x, y))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path, format="PNG", optimize=True)


async def _run_module(name: str, module, asset: FakeAsset, base_bytes: bytes, out_dir: Path, config: dict | None = None) -> Path:
    random.seed(_seed_for(name))
    client = FakeClient(base_bytes)
    settings = SimpleNamespace(collage_output_size="medium")
    result = await module.run([asset], config or {}, client, settings)
    out_path = out_dir / f"{_sanitize(name)}.png"
    _save_image(result.image_bytes, out_path)
    return out_path


async def main() -> None:
    _ensure_engine()
    base_bytes = _make_base_image()
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    MODULE_OUT.mkdir(parents=True, exist_ok=True)
    STYLE_OUT.mkdir(parents=True, exist_ok=True)

    base_path = OUT_ROOT / "base.png"
    _save_image(base_bytes, base_path)

    asset = FakeAsset(
        id="sample-asset",
        original_file_name="showcase-base.png",
        created_at="2024-06-15T10:30:00+00:00",
    )

    module_specs: list[tuple[str, object, dict | None]] = [
        ("collage", MODULES["collage"], {"styles": ["_1977", "aden", "walden", "xpro2"]}),
        ("instafilter", MODULES["instafilter"], {"styles": ["random"]}),
        ("filmstrip", MODULES["filmstrip"], {}),
        ("popart", MODULES["popart"], {}),
        ("duotone", MODULES["duotone"], {}),
        ("halftone", MODULES["halftone"], {}),
        ("glitch", MODULES["glitch"], {}),
        ("light_leak", MODULES["light_leak"], {}),
        ("neon_bloom", MODULES["neon_bloom"], {}),
        ("cyanotype", MODULES["cyanotype"], {}),
        ("polaroid", MODULES["polaroid"], {}),
        ("prism_split", MODULES["prism_split"], {}),
        ("paper_cutout", MODULES["paper_cutout"], {}),
        ("apple_weather", MODULES["apple_weather"], {}),
        ("instaweather", MODULES["instaweather"], {}),
    ]

    module_cards: list[tuple[Path, str, str | None]] = [(base_path, "Base image", "Synthetic showcase photo")]
    generated_manifest = []
    for name, module, config in module_specs:
        out_path = await _run_module(name, module, asset, base_bytes, MODULE_OUT, config)
        module_cards.append((out_path, name.replace("_", " ").title(), "App generation module"))
        generated_manifest.append(
            {
                "type": "module",
                "name": name,
                "path": str(out_path.relative_to(OUT_ROOT)),
                "config": config or {},
            }
        )

    _make_contact_sheet(module_cards, OUT_ROOT / "modules-contact-sheet.png", columns=3)

    style_cards: list[tuple[Path, str, str | None]] = []
    for style in AVAILABLE_FILTERS:
        random.seed(_seed_for(f"instafilter:{style}"))
        filtered_bytes, actual_style = apply_instafilter(base_bytes, filter_name=style)
        out_path = STYLE_OUT / f"{_sanitize(actual_style)}.png"
        _save_image(filtered_bytes, out_path)
        style_cards.append((out_path, actual_style, "pilgram filter"))
        generated_manifest.append(
            {
                "type": "instafilter",
                "name": actual_style,
                "path": str(out_path.relative_to(OUT_ROOT)),
            }
        )

    _make_contact_sheet(style_cards, OUT_ROOT / "instafilters-contact-sheet.png", columns=4)

    manifest_path = OUT_ROOT / "manifest.json"
    manifest_path.write_text(json.dumps(generated_manifest, indent=2, ensure_ascii=True) + "\n")

    index_md = OUT_ROOT / "README.md"
    index_md.write_text(
        "\n".join(
            [
                "# DailyFX for immich filter showcase",
                "",
                f"- Base image: `{base_path.name}`",
                f"- Module contact sheet: `{(OUT_ROOT / 'modules-contact-sheet.png').name}`",
                f"- Instafilter contact sheet: `{(OUT_ROOT / 'instafilters-contact-sheet.png').name}`",
                f"- Manifest: `{manifest_path.name}`",
                "",
                "## Outputs",
                "",
                "- `modules/` contains one rendered file per app generation module.",
                "- `instafilters/` contains one rendered file per `pilgram` style used by the app.",
            ]
        )
        + "\n"
    )


if __name__ == "__main__":
    asyncio.run(main())
