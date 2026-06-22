"""Smoke tests for all remaining effect modules."""

import asyncio
import os
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from PIL import Image

os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("APP_SECRET_KEY", "test-secret")
test_db = Path("/tmp/test_all_modules.db")
test_db.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{test_db}"


def _img(w=160, h=120, color=(100, 150, 200)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (w, h), color).save(buf, format="PNG")
    return buf.getvalue()


def _asset(aid="a1", fname="photo.jpg", created="2024-06-15T10:30:00.000Z"):
    a = MagicMock()
    a.id = aid
    a.original_file_name = fname
    a.created_at = created
    return a


def _client(*extra_bytes):
    """Client that returns _img() for get_asset_data, and extra_bytes for subsequent calls."""
    calls = [_img()] + list(extra_bytes)
    c = AsyncMock()
    c.get_asset_data = AsyncMock(
        side_effect=calls if len(calls) > 1 else None, return_value=calls[0] if len(calls) == 1 else None
    )
    c.get_asset_exif = AsyncMock(return_value={"city": "Warsaw", "country": "Poland"})
    return c


def _png(data: bytes) -> bool:
    return data.startswith(b"\x89PNG\r\n\x1a\n")


def _run(module, config=None, assets=None, client=None):
    if assets is None:
        assets = [_asset()]
    if client is None:
        client = _client()
    return asyncio.run(module.run(assets, config or {}, client, MagicMock()))


# ── bokeh_blur ────────────────────────────────────────────────────────────────


def test_bokeh_blur_center():
    from app.services.generation.modules.bokeh_blur import BokehBlurModule

    r = _run(BokehBlurModule(), {"blur_strength": 5, "focus_area": "center"})
    assert r.generation_type == "bokeh_blur"
    assert _png(r.image_bytes)


def test_bokeh_blur_auto():
    from app.services.generation.modules.bokeh_blur import BokehBlurModule

    r = _run(BokehBlurModule(), {"blur_strength": 5, "focus_area": "auto"})
    assert _png(r.image_bytes)


# ── vintage_film ──────────────────────────────────────────────────────────────


def test_vintage_film_kodachrome():
    from app.services.generation.modules.vintage_film import VintageFilmModule

    r = _run(VintageFilmModule(), {"film_type": "kodachrome", "fade": 0.5})
    assert r.generation_type == "vintage_film"
    assert _png(r.image_bytes)


def test_vintage_film_fuji():
    from app.services.generation.modules.vintage_film import VintageFilmModule

    r = _run(VintageFilmModule(), {"film_type": "fuji"})
    assert _png(r.image_bytes)


# ── collage ───────────────────────────────────────────────────────────────────


def test_collage_four_tiles():
    from app.services.generation.modules.collage import CollageModule

    # collage calls get_asset_data once then apply_instafilter 4 times internally
    r = _run(CollageModule(), {"styles": ["aden", "moon", "lark", "lofi"], "border": 4})
    assert r.generation_type == "collage"
    assert _png(r.image_bytes)


# ── duotone ───────────────────────────────────────────────────────────────────


def test_duotone_default():
    from app.services.generation.modules.duotone import DuotoneModule

    r = _run(DuotoneModule(), {"contrast": 1.4})
    assert r.generation_type == "duotone"
    assert _png(r.image_bytes)


# ── filmstrip ─────────────────────────────────────────────────────────────────


def test_filmstrip_classic():
    from app.services.generation.modules.filmstrip import FilmstripModule

    r = _run(FilmstripModule(), {"frame_style": "classic"})
    assert r.generation_type == "filmstrip"
    assert _png(r.image_bytes)


def test_filmstrip_modern():
    from app.services.generation.modules.filmstrip import FilmstripModule

    r = _run(FilmstripModule(), {"frame_style": "modern"})
    assert _png(r.image_bytes)


# ── glitch ────────────────────────────────────────────────────────────────────


def test_glitch_default():
    from app.services.generation.modules.glitch import GlitchModule

    r = _run(GlitchModule(), {"shift": 8, "intensity": 0.6})
    assert r.generation_type == "glitch"
    assert _png(r.image_bytes)


# ── halftone ──────────────────────────────────────────────────────────────────


def test_halftone_varied():
    from app.services.generation.modules.halftone import HalftoneModule

    r = _run(HalftoneModule(), {"cell_size": 14, "style": "varied"})
    assert r.generation_type == "halftone"
    assert _png(r.image_bytes)


def test_halftone_uniform():
    from app.services.generation.modules.halftone import HalftoneModule

    r = _run(HalftoneModule(), {"cell_size": 10, "style": "uniform"})
    assert _png(r.image_bytes)


# ── huji ──────────────────────────────────────────────────────────────────────


def test_huji_with_date_stamp():
    from app.services.generation.modules.huji import HujiModule

    r = _run(HujiModule(), {"date_stamp": True})
    assert r.generation_type == "huji"
    assert r.config.get("date_stamp") is True
    assert _png(r.image_bytes)


def test_huji_no_date_stamp():
    from app.services.generation.modules.huji import HujiModule

    r = _run(HujiModule(), {"date_stamp": False})
    assert r.config.get("date_stamp") is False
    assert _png(r.image_bytes)


# ── instafilter ───────────────────────────────────────────────────────────────


def test_instafilter_random():
    from app.services.generation.modules.instafilter import InstafilterModule

    r = _run(InstafilterModule(), {"styles": ["aden"]})
    assert r.generation_type == "instafilter"
    assert _png(r.image_bytes)


# ── light_leak ────────────────────────────────────────────────────────────────


def test_light_leak_warm():
    from app.services.generation.modules.light_leak import LightLeakModule

    r = _run(LightLeakModule(), {"intensity": 0.35, "color": "warm"})
    assert r.generation_type == "light_leak"
    assert _png(r.image_bytes)


def test_light_leak_cool():
    from app.services.generation.modules.light_leak import LightLeakModule

    r = _run(LightLeakModule(), {"color": "cool"})
    assert _png(r.image_bytes)


# ── museum_archive ────────────────────────────────────────────────────────────


def test_museum_archive_classic():
    from app.services.generation.modules.museum_archive import MuseumArchiveModule

    r = _run(MuseumArchiveModule(), {"frame_style": "classic"})
    assert r.generation_type == "museum_archive"
    assert _png(r.image_bytes)


def test_museum_archive_minimal():
    from app.services.generation.modules.museum_archive import MuseumArchiveModule

    r = _run(MuseumArchiveModule(), {"frame_style": "minimal"})
    assert _png(r.image_bytes)


# ── neon_bloom ────────────────────────────────────────────────────────────────


def test_neon_bloom_default():
    from app.services.generation.modules.neon_bloom import NeonBloomModule

    r = _run(NeonBloomModule(), {"bloom_radius": 10, "intensity": 1.4})
    assert r.generation_type == "neon_bloom"
    assert _png(r.image_bytes)


# ── popart ────────────────────────────────────────────────────────────────────


def test_popart_default():
    from app.services.generation.modules.popart import PopArtModule

    r = _run(PopArtModule(), {"contrast": 2.2, "border": 12})
    assert r.generation_type == "popart"
    assert _png(r.image_bytes)


# ── prism_split ───────────────────────────────────────────────────────────────


def test_prism_split_bold():
    from app.services.generation.modules.prism_split import PrismSplitModule

    r = _run(PrismSplitModule(), {"shift": 18, "style": "bold"})
    assert r.generation_type == "prism_split"
    assert _png(r.image_bytes)


def test_prism_split_subtle():
    from app.services.generation.modules.prism_split import PrismSplitModule

    r = _run(PrismSplitModule(), {"style": "subtle"})
    assert _png(r.image_bytes)


# ── config validation ─────────────────────────────────────────────────────────


def test_bokeh_blur_clamps_out_of_range_config():
    from app.services.generation.modules.bokeh_blur import BokehBlurModule

    r = _run(BokehBlurModule(), {"blur_strength": 999, "focus_area": "invalid"})
    assert _png(r.image_bytes)  # should not crash, clamps to valid range


def test_vintage_film_invalid_type_falls_back():
    from app.services.generation.modules.vintage_film import VintageFilmModule

    r = _run(VintageFilmModule(), {"film_type": "nonexistent"})
    assert _png(r.image_bytes)  # falls back to kodachrome
