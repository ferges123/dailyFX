"""Tests for new OpenCV effect modules: pencil_sketch, cartoon, hdr."""
import asyncio
import os
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from PIL import Image

os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("APP_SECRET_KEY", "test-secret")
test_db = Path("/tmp/test_new_modules.db")
test_db.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{test_db}"

from app.services.generation.modules.pencil_sketch import PencilSketchModule
from app.services.generation.modules.cartoon import CartoonModule
from app.services.generation.modules.hdr import HDRModule


def _img_bytes(w=120, h=90) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (w, h), (100, 150, 200)).save(buf, format="PNG")
    return buf.getvalue()


def _asset():
    a = MagicMock()
    a.id = "test-asset"
    a.original_file_name = "photo.jpg"
    return a


def _client(img_bytes):
    c = AsyncMock()
    c.get_asset_data = AsyncMock(return_value=img_bytes)
    return c


def _is_png(data: bytes) -> bool:
    return data.startswith(b"\x89PNG\r\n\x1a\n")


def test_pencil_sketch_gray():
    result = asyncio.run(PencilSketchModule().run([_asset()], {"style": "gray"}, _client(_img_bytes()), MagicMock()))
    assert result.generation_type == "pencil_sketch"
    assert _is_png(result.image_bytes)


def test_pencil_sketch_color():
    result = asyncio.run(PencilSketchModule().run([_asset()], {"style": "color"}, _client(_img_bytes()), MagicMock()))
    assert result.generation_type == "pencil_sketch"
    assert _is_png(result.image_bytes)


def test_cartoon_default():
    result = asyncio.run(CartoonModule().run([_asset()], {}, _client(_img_bytes()), MagicMock()))
    assert result.generation_type == "cartoon"
    assert _is_png(result.image_bytes)


def test_cartoon_even_edge_strength_corrected():
    # edge_strength=10 (even) should be bumped to 11
    result = asyncio.run(CartoonModule().run([_asset()], {"edge_strength": 10}, _client(_img_bytes()), MagicMock()))
    assert _is_png(result.image_bytes)


def test_hdr_drago():
    result = asyncio.run(HDRModule().run([_asset()], {"algorithm": "drago"}, _client(_img_bytes()), MagicMock()))
    assert result.generation_type == "hdr"
    assert _is_png(result.image_bytes)


def test_hdr_reinhard():
    result = asyncio.run(HDRModule().run([_asset()], {"algorithm": "reinhard"}, _client(_img_bytes()), MagicMock()))
    assert _is_png(result.image_bytes)


def test_hdr_mantiuk():
    # Mantiuk requires non-uniform image (assertion on dot product)
    buf = BytesIO()
    import numpy as np
    arr = np.random.randint(0, 255, (90, 120, 3), dtype=np.uint8)
    Image.fromarray(arr).save(buf, format="PNG")
    result = asyncio.run(HDRModule().run([_asset()], {"algorithm": "mantiuk"}, _client(buf.getvalue()), MagicMock()))
    assert _is_png(result.image_bytes)


def test_hdr_invalid_algorithm_falls_back():
    result = asyncio.run(HDRModule().run([_asset()], {"algorithm": "unknown"}, _client(_img_bytes()), MagicMock()))
    assert _is_png(result.image_bytes)

