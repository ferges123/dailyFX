# Motion Effects Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use compose:subagent (recommended) or compose:execute to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add animated GIF/WebP motion effects (parallax, cinemagraph, zoom/pan, pulse) to DailyFX as a new category of generation modules.

**Architecture:** New `motion_*` modules in `backend/app/services/generation/modules/` that generate frame sequences and compress them to GIF/WebP via `imageio`. Extended `GenerationResult` with `output_format` field. Frontend auto-detects animated formats in `SecureImage`.

**Tech Stack:** Python 3.13, Pillow, imageio, OpenCV, React 19, TypeScript

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `backend/app/services/generation/modules/motion_parallax.py` | Parallax 3D effect — foreground/background depth layers |
| `backend/app/services/generation/modules/motion_cinemagraph.py` | Cinemagraph — static bg + moving masked region |
| `backend/app/services/generation/modules/motion_zoom_pan.py` | Zoom + Pan — Ken Burns and pan animations |
| `backend/app/services/generation/modules/motion_pulse.py` | Time-based effects — brightness/saturation/hue modulation |
| `backend/tests/test_motion_common.py` | Tests for frames_to_animation helper |
| `backend/tests/test_motion_parallax.py` | Tests for parallax module |
| `backend/tests/test_motion_cinemagraph.py` | Tests for cinemagraph module |
| `backend/tests/test_motion_zoom_pan.py` | Tests for zoom/pan module |
| `backend/tests/test_motion_pulse.py` | Tests for pulse module |

### Modified Files

| File | Changes |
|------|---------|
| `backend/pyproject.toml:6-24` | Add `imageio>=2.35.0` dependency |
| `backend/app/services/generation/modules/base.py:19-28` | Add `output_format` and `frame_count` to `GenerationResult` |
| `backend/app/services/generation/modules/common.py` | Add `frames_to_animation()` helper |
| `backend/app/services/generation/modules/__init__.py:29-53` | Register motion modules in `LOCAL_MODULE_CLASSES` |
| `backend/app/models/generation_history.py:9-44` | Add `output_format` column |
| `backend/app/services/generation/persistence.py:42-95` | Handle dynamic output format and filename |
| `backend/app/services/generation/history.py:32-47` | Pass `output_format` to upsert |
| `frontend/src/api/client.ts:378-404` | Add `output_format` to `GenerationHistoryEntry` |
| `frontend/src/components/SecureImage.tsx:7-73` | Auto-detect animated formats |
| `frontend/src/pages/History/LightboxModal.tsx:75-400` | Play/pause for animated images |
| `frontend/src/pages/History/HistoryPage.tsx` | Badge "Motion" for animated results |

---

## Task 1: Add imageio Dependency

**Covers:** [S2]

**Files:**
- Modify: `backend/pyproject.toml:6-24`

- [ ] **Step 1: Add imageio to dependencies**

```toml
# backend/pyproject.toml
[project]
name = "dailyfx-backend"
version = "0.1.0"
description = "FastAPI backend for DailyFX for immich"
requires-python = ">=3.13"
dependencies = [
    "fastapi>=0.115.0,<0.116.0",
    "uvicorn[standard]>=0.30.0",
    "sqlalchemy>=2.0.0",
    "alembic>=1.13.0",
    "pydantic-settings>=2.4.0",
    "httpx>=0.27.0",
    "cryptography>=43.0.0",
    "pillow>=11.0.0",
    "pillow-heif>=0.20.0",
    "pilgram>=2.0.0",
    "pywebpush>=2.0.0",
    "py-vapid>=1.9.0",
    "opencv-python-headless>=4.8.0",
    "numpy>=1.24.0",
    "slowapi>=0.1.9",
    "apprise>=1.9.0",
    "python-multipart>=0.0.9",
    "imageio>=2.35.0",
]
```

- [ ] **Step 2: Install dependencies**

Run: `cd backend && pip install -e ".[test,lint]"`
Expected: Successfully installed imageio

- [ ] **Step 3: Verify imageio import**

Run: `python -c "import imageio; print(imageio.__version__)"`
Expected: Version number printed

- [ ] **Step 4: Commit**

```bash
git add backend/pyproject.toml backend/pyproject.toml
git commit -m "chore: add imageio dependency for motion effects"
```

---

## Task 2: Extend GenerationResult

**Covers:** [S2]

**Files:**
- Modify: `backend/app/services/generation/modules/base.py:19-28`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_motion_common.py
from app.services.generation.modules.base import GenerationResult


def test_generation_result_has_output_format():
    result = GenerationResult(
        title="Test",
        summary="Test",
        image_bytes=b"fake",
        generation_type="test",
        provider="local",
        model="pil",
        config={},
        source_asset_ids=["abc"],
    )
    assert result.output_format == "png"
    assert result.frame_count is None


def test_generation_result_gif_format():
    result = GenerationResult(
        title="Test GIF",
        summary="Test",
        image_bytes=b"fake",
        generation_type="motion_pulse",
        provider="local",
        model="pil",
        config={},
        source_asset_ids=["abc"],
        output_format="gif",
        frame_count=24,
    )
    assert result.output_format == "gif"
    assert result.frame_count == 24
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_motion_common.py -v`
Expected: FAIL with "unexpected keyword argument 'output_format'"

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/services/generation/modules/base.py
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.models.settings import SettingsModel


@dataclass(frozen=True)
class ModuleDefinition:
    name: str
    label: str
    description: str
    default_weight: int = 1
    source_asset_count: int = 1
    default_enabled: bool = True
    default_config: dict[str, Any] | None = None
    config_schema: list[dict[str, Any]] | None = None


@dataclass
class GenerationResult:
    title: str
    summary: str
    image_bytes: bytes
    generation_type: str
    provider: str
    model: str
    config: dict
    source_asset_ids: list[str]
    output_format: str = "png"
    frame_count: int | None = None


class GenerationModule(Protocol):
    name: str
    label: str
    description: str
    default_weight: int
    source_asset_count: int
    default_config: dict[str, Any] | None
    config_schema: list[dict[str, Any]] | None

    async def run(
        self,
        page_items: list,
        config: dict,
        client,
        settings: SettingsModel,
    ) -> GenerationResult: ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_motion_common.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/generation/modules/base.py backend/tests/test_motion_common.py
git commit -m "feat: extend GenerationResult with output_format and frame_count"
```

---

## Task 3: Add frames_to_animation Helper

**Covers:** [S2, S5]

**Files:**
- Modify: `backend/app/services/generation/modules/common.py`
- Test: `backend/tests/test_motion_common.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_motion_common.py (append)
from PIL import Image
from app.services.generation.modules.common import frames_to_animation


def _make_test_frames(count=3, size=(100, 100)):
    frames = []
    for i in range(count):
        img = Image.new("RGB", size, color=(i * 80, 100, 200 - i * 30))
        frames.append(img)
    return frames


def test_frames_to_animation_gif():
    frames = _make_test_frames(3)
    result = frames_to_animation(frames, fps=12, format="gif")
    assert isinstance(result, bytes)
    assert len(result) > 0
    assert result[:3] == b"GIF"


def test_frames_to_animation_webp():
    frames = _make_test_frames(3)
    result = frames_to_animation(frames, fps=12, format="webp")
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_frames_to_animation_empty_raises():
    try:
        frames_to_animation([], fps=12, format="gif")
        assert False, "Should raise ValueError"
    except ValueError:
        pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_motion_common.py::test_frames_to_animation_gif -v`
Expected: FAIL with "cannot import name 'frames_to_animation'"

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/services/generation/modules/common.py (append at end)
import io
from PIL import Image


def frames_to_animation(
    frames: list[Image.Image],
    fps: int = 12,
    format: str = "gif",
    loop: int = 0,
) -> bytes:
    """Compress PIL frames to animated GIF or WebP using imageio.

    Args:
        frames: List of PIL Image frames
        fps: Frames per second
        format: Output format ("gif" or "webp")
        loop: Number of loops (0 = infinite)

    Returns:
        Animated image bytes

    Raises:
        ValueError: If frames list is empty
    """
    if not frames:
        raise ValueError("Cannot create animation from empty frame list")

    import imageio.v3 as iio

    import numpy as np

    frame_arrays = []
    for frame in frames:
        if frame.mode != "RGB":
            frame = frame.convert("RGB")
        frame_arrays.append(np.array(frame))

    duration = 1000 / fps  # ms per frame

    kwargs = {"loop": loop}
    if format == "webp":
        kwargs["quality"] = 85

    output = iio.imwrite(
        "<bytes>",
        frame_arrays,
        extension=f".{format}",
        duration=duration,
        **kwargs,
    )
    return output
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_motion_common.py -v`
Expected: PASS (all 4 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/generation/modules/common.py backend/tests/test_motion_common.py
git commit -m "feat: add frames_to_animation helper for motion effects"
```

---

## Task 4: Implement motion_pulse Module

**Covers:** [S2]

**Files:**
- Create: `backend/app/services/generation/modules/motion_pulse.py`
- Test: `backend/tests/test_motion_pulse.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_motion_pulse.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.generation.modules.motion_pulse import MotionPulseModule


@pytest.fixture
def module():
    return MotionPulseModule()


@pytest.fixture
def mock_client():
    client = AsyncMock()
    return client


def _make_fake_asset():
    asset = MagicMock()
    asset.id = "test-asset-123"
    asset.original_file_name = "test.jpg"
    return asset


def test_module_metadata(module):
    assert module.name == "motion_pulse"
    assert module.label == "Motion Pulse"
    assert "brightness" in str(module.config_schema)
    assert module.default_config["effect"] == "brightness"


def test_config_schema_has_all_effects(module):
    effects = [opt["value"] for field in module.config_schema if field["key"] == "effect" for opt in field["options"]]
    assert "brightness" in effects
    assert "saturation" in effects
    assert "hue" in effects
    assert "glitch" in effects


@pytest.mark.asyncio
async def test_run_produces_gif(module, mock_client):
    from io import BytesIO
    from PIL import Image

    img = Image.new("RGB", (200, 200), color=(128, 128, 128))
    buf = BytesIO()
    img.save(buf, format="PNG")
    mock_client.get_asset_data = AsyncMock(return_value=buf.getvalue())

    result = await module.run(
        page_items=[_make_fake_asset()],
        config={"effect": "brightness", "speed": 1.0, "intensity": 0.5},
        client=mock_client,
    )

    assert result.output_format == "gif"
    assert result.frame_count == 24
    assert len(result.image_bytes) > 0
    assert result.image_bytes[:3] == b"GIF"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_motion_pulse.py -v`
Expected: FAIL with "No module named 'app.services.generation.modules.motion_pulse'"

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/services/generation/modules/motion_pulse.py
from __future__ import annotations

import math
import random
from io import BytesIO

from PIL import Image, ImageChops, ImageEnhance

from app.models.settings import SettingsModel
from app.services.generation.modules.base import GenerationResult
from app.services.generation.modules.common import frames_to_animation, load_rgb


class MotionPulseModule:
    name = "motion_pulse"
    label = "Motion Pulse"
    description = "Animated pulsing effect — brightness, saturation, hue, or glitch modulation."
    default_weight = 1
    source_asset_count = 1
    default_config = {"effect": "brightness", "speed": 1.0, "intensity": 0.6}
    config_schema = [
        {
            "key": "effect",
            "label": "Effect Type",
            "type": "select",
            "description": "Which parameter to modulate.",
            "options": [
                {"value": "brightness", "label": "Brightness"},
                {"value": "saturation", "label": "Saturation"},
                {"value": "hue", "label": "Hue Shift"},
                {"value": "glitch", "label": "Glitch Pulse"},
            ],
            "default": "brightness",
        },
        {
            "key": "speed",
            "label": "Speed",
            "type": "number",
            "description": "Animation speed multiplier (0.5 = slow, 2.0 = fast).",
            "min": 0.5,
            "max": 2.0,
            "step": 0.1,
            "default": 1.0,
        },
        {
            "key": "intensity",
            "label": "Intensity",
            "type": "number",
            "description": "Effect intensity (0.3 = subtle, 1.0 = extreme).",
            "min": 0.3,
            "max": 1.0,
            "step": 0.1,
            "default": 0.6,
        },
    ]

    async def run(self, page_items: list, config: dict, client, settings: SettingsModel) -> GenerationResult:
        asset = page_items[0]
        image_bytes = await client.get_asset_data(asset.id)
        source = load_rgb(image_bytes)

        effect = config.get("effect", "brightness")
        speed = max(0.5, min(2.0, float(config.get("speed", 1.0) or 1.0)))
        intensity = max(0.3, min(1.0, float(config.get("intensity", 0.6) or 0.6)))

        frame_count = 24
        fps = int(12 * speed)
        frames = []

        for i in range(frame_count):
            t = i / frame_count
            phase = math.sin(t * 2 * math.pi)

            if effect == "brightness":
                factor = 1.0 + phase * intensity * 0.4
                frame = ImageEnhance.Brightness(source).enhance(factor)
            elif effect == "saturation":
                factor = 1.0 + phase * intensity * 0.5
                frame = ImageEnhance.Color(source).enhance(factor)
            elif effect == "hue":
                frame = source.copy()
                r, g, b = frame.split()
                shift = int(phase * intensity * 30)
                r = ImageChops.offset(r, shift, 0)
                b = ImageChops.offset(b, -shift, 0)
                frame = Image.merge("RGB", (r, g, b))
            elif effect == "glitch":
                frame = source.copy()
                if random.random() < 0.3:
                    r, g, b = frame.split()
                    r = ImageChops.offset(r, random.randint(-5, 5), 0)
                    frame = Image.merge("RGB", (r, g, b))
            else:
                frame = source.copy()

            frames.append(frame)

        animation_bytes = frames_to_animation(frames, fps=fps, format="gif")

        return GenerationResult(
            title=f"Motion Pulse: {asset.original_file_name or asset.id}",
            summary=f"Animated {effect} pulse effect.",
            image_bytes=animation_bytes,
            generation_type="motion_pulse",
            provider="local",
            model="pil+imageio",
            config={"effect": effect, "speed": speed, "intensity": intensity},
            source_asset_ids=[asset.id],
            output_format="gif",
            frame_count=frame_count,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_motion_pulse.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/generation/modules/motion_pulse.py backend/tests/test_motion_pulse.py
git commit -m "feat: add motion_pulse module for brightness/saturation/hue/glitch animation"
```

---

## Task 5: Implement motion_parallax Module

**Covers:** [S2]

**Files:**
- Create: `backend/app/services/generation/modules/motion_parallax.py`
- Test: `backend/tests/test_motion_parallax.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_motion_parallax.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.generation.modules.motion_parallax import MotionParallaxModule


@pytest.fixture
def module():
    return MotionParallaxModule()


def test_module_metadata(module):
    assert module.name == "motion_parallax"
    assert module.label == "Motion Parallax"


def test_config_schema(module):
    directions = [opt["value"] for field in module.config_schema if field["key"] == "direction" for opt in field["options"]]
    assert "left" in directions
    assert "right" in directions
    assert "up" in directions
    assert "down" in directions


@pytest.mark.asyncio
async def test_run_produces_gif(module):
    from io import BytesIO
    from PIL import Image

    client = AsyncMock()
    img = Image.new("RGB", (400, 300), color=(100, 150, 200))
    buf = BytesIO()
    img.save(buf, format="PNG")
    client.get_asset_data = AsyncMock(return_value=buf.getvalue())

    asset = MagicMock()
    asset.id = "parallax-test"
    asset.original_file_name = "photo.jpg"

    result = await module.run(
        page_items=[asset],
        config={"depth": 5, "speed": 1.0, "direction": "left"},
        client=client,
    )

    assert result.output_format == "gif"
    assert result.frame_count == 12
    assert len(result.image_bytes) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_motion_parallax.py -v`
Expected: FAIL with "No module named 'app.services.generation.modules.motion_parallax'"

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/services/generation/modules/motion_parallax.py
from __future__ import annotations

import math
from io import BytesIO

import numpy as np
from PIL import Image

from app.models.settings import SettingsModel
from app.services.generation.modules.base import GenerationResult
from app.services.generation.modules.common import frames_to_animation, load_rgb


class MotionParallaxModule:
    name = "motion_parallax"
    label = "Motion Parallax"
    description = "2.5D parallax depth effect — simulates camera movement on a static photo."
    default_weight = 1
    source_asset_count = 1
    default_config = {"depth": 5, "speed": 1.0, "direction": "left"}
    config_schema = [
        {
            "key": "depth",
            "label": "Depth",
            "type": "number",
            "description": "Parallax depth intensity (1 = subtle, 10 = extreme).",
            "min": 1,
            "max": 10,
            "step": 1,
            "default": 5,
        },
        {
            "key": "speed",
            "label": "Speed",
            "type": "number",
            "description": "Animation speed multiplier.",
            "min": 0.5,
            "max": 2.0,
            "step": 0.1,
            "default": 1.0,
        },
        {
            "key": "direction",
            "label": "Direction",
            "type": "select",
            "description": "Camera movement direction.",
            "options": [
                {"value": "left", "label": "Left"},
                {"value": "right", "label": "Right"},
                {"value": "up", "label": "Up"},
                {"value": "down", "label": "Down"},
            ],
            "default": "left",
        },
    ]

    async def run(self, page_items: list, config: dict, client, settings: SettingsModel) -> GenerationResult:
        asset = page_items[0]
        image_bytes = await client.get_asset_data(asset.id)
        source = load_rgb(image_bytes)

        depth = max(1, min(10, int(config.get("depth", 5) or 5)))
        speed = max(0.5, min(2.0, float(config.get("speed", 1.0) or 1.0)))
        direction = config.get("direction", "left")
        if direction not in ("left", "right", "up", "down"):
            direction = "left"

        w, h = source.size
        frame_count = 12
        fps = int(12 * speed)
        max_offset = int(depth * 3)

        source_arr = np.array(source)
        frames = []

        for i in range(frame_count):
            t = math.sin((i / frame_count) * 2 * math.pi)
            offset = int(t * max_offset)

            if direction in ("left", "right"):
                dx = offset if direction == "left" else -offset
                dy = 0
            else:
                dx = 0
                dy = offset if direction == "up" else -offset

            bg_arr = np.roll(source_arr, shift=dx, axis=1)
            bg_arr = np.roll(bg_arr, shift=dy, axis=0)

            fg_mask = _create_simple_foreground_mask(source_arr)

            result_arr = source_arr.copy()
            mask_3d = np.stack([fg_mask] * 3, axis=-1)
            result_arr = np.where(mask_3d, source_arr, bg_arr)

            frame = Image.fromarray(result_arr.astype(np.uint8))
            frames.append(frame)

        animation_bytes = frames_to_animation(frames, fps=fps, format="gif")

        return GenerationResult(
            title=f"Motion Parallax: {asset.original_file_name or asset.id}",
            summary=f"2.5D parallax depth effect ({direction}).",
            image_bytes=animation_bytes,
            generation_type="motion_parallax",
            provider="local",
            model="pil+numpy",
            config={"depth": depth, "speed": speed, "direction": direction},
            source_asset_ids=[asset.id],
            output_format="gif",
            frame_count=frame_count,
        )


def _create_simple_foreground_mask(arr: np.ndarray) -> np.ndarray:
    """Create a simple center-weighted foreground mask."""
    h, w = arr.shape[:2]
    y, x = np.ogrid[:h, :w]
    cy, cx = h / 2, w / 2
    dist = np.sqrt(((x - cx) / (w / 2)) ** 2 + ((y - cy) / (h / 2)) ** 2)
    mask = (dist < 0.7).astype(np.uint8)
    return mask
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_motion_parallax.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/generation/modules/motion_parallax.py backend/tests/test_motion_parallax.py
git commit -m "feat: add motion_parallax module for 2.5D depth effect"
```

---

## Task 6: Implement motion_cinemagraph Module

**Covers:** [S2]

**Files:**
- Create: `backend/app/services/generation/modules/motion_cinemagraph.py`
- Test: `backend/tests/test_motion_cinemagraph.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_motion_cinemagraph.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.generation.modules.motion_cinemagraph import MotionCinemagraphModule


@pytest.fixture
def module():
    return MotionCinemagraphModule()


def test_module_metadata(module):
    assert module.name == "motion_cinemagraph"
    assert module.label == "Motion Cinemagraph"


@pytest.mark.asyncio
async def test_run_produces_gif(module):
    from io import BytesIO
    from PIL import Image

    client = AsyncMock()
    img = Image.new("RGB", (300, 300), color=(80, 120, 180))
    buf = BytesIO()
    img.save(buf, format="PNG")
    client.get_asset_data = AsyncMock(return_value=buf.getvalue())

    asset = MagicMock()
    asset.id = "cinema-test"
    asset.original_file_name = "landscape.jpg"

    result = await module.run(
        page_items=[asset],
        config={"mask_region": "center", "motion_type": "glow", "speed": 1.0},
        client=client,
    )

    assert result.output_format == "gif"
    assert result.frame_count == 24
    assert len(result.image_bytes) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_motion_cinemagraph.py -v`
Expected: FAIL with "No module named 'app.services.generation.modules.motion_cinemagraph'"

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/services/generation/modules/motion_cinemagraph.py
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageEnhance

from app.models.settings import SettingsModel
from app.services.generation.modules.base import GenerationResult
from app.services.generation.modules.common import frames_to_animation, load_rgb


class MotionCinemagraphModule:
    name = "motion_cinemagraph"
    label = "Motion Cinemagraph"
    description = "Cinemagraph — static background with a moving masked region."
    default_weight = 1
    source_asset_count = 1
    default_config = {"mask_region": "center", "motion_type": "glow", "speed": 1.0}
    config_schema = [
        {
            "key": "mask_region",
            "label": "Mask Region",
            "type": "select",
            "description": "Which region of the image animates.",
            "options": [
                {"value": "center", "label": "Center"},
                {"value": "top", "label": "Top"},
                {"value": "bottom", "label": "Bottom"},
            ],
            "default": "center",
        },
        {
            "key": "motion_type",
            "label": "Motion Type",
            "type": "select",
            "description": "Type of animation in the masked region.",
            "options": [
                {"value": "glow", "label": "Glow"},
                {"value": "water", "label": "Water Ripple"},
                {"value": "pulse", "label": "Pulse"},
            ],
            "default": "glow",
        },
        {
            "key": "speed",
            "label": "Speed",
            "type": "number",
            "description": "Animation speed multiplier.",
            "min": 0.5,
            "max": 2.0,
            "step": 0.1,
            "default": 1.0,
        },
    ]

    async def run(self, page_items: list, config: dict, client, settings: SettingsModel) -> GenerationResult:
        asset = page_items[0]
        image_bytes = await client.get_asset_data(asset.id)
        source = load_rgb(image_bytes)

        mask_region = config.get("mask_region", "center")
        motion_type = config.get("motion_type", "glow")
        speed = max(0.5, min(2.0, float(config.get("speed", 1.0) or 1.0)))

        w, h = source.size
        mask = _create_region_mask(w, h, mask_region)

        frame_count = 24
        fps = int(12 * speed)
        frames = []
        source_arr = np.array(source, dtype=np.float32)

        for i in range(frame_count):
            t = i / frame_count
            phase = math.sin(t * 2 * math.pi)

            if motion_type == "glow":
                brightness = 1.0 + phase * 0.2
                frame_arr = source_arr * brightness
            elif motion_type == "water":
                frame_arr = source_arr.copy()
                y_coords, x_coords = np.meshgrid(np.arange(h), np.arange(w), indexing="ij")
                wave = np.sin(x_coords * 0.05 + phase * 4) * 5
                shift_x = (wave * mask).astype(int)
                for c in range(3):
                    frame_arr[:, :, c] = np.roll(source_arr[:, :, c], shift_x, axis=1)
            elif motion_type == "pulse":
                scale = 1.0 + phase * 0.05
                pil_frame = Image.fromarray(source_arr.astype(np.uint8))
                pil_frame = pil_frame.resize((int(w * scale), int(h * scale)), Image.BILINEAR)
                frame_arr = np.array(pil_frame, dtype=np.float32)
            else:
                frame_arr = source_arr.copy()

            frame_arr = np.clip(frame_arr, 0, 255)

            mask_3d = np.stack([mask] * 3, axis=-1)
            result_arr = source_arr * (1 - mask_3d) + frame_arr * mask_3d
            result_arr = np.clip(result_arr, 0, 255).astype(np.uint8)

            frames.append(Image.fromarray(result_arr))

        animation_bytes = frames_to_animation(frames, fps=fps, format="gif")

        return GenerationResult(
            title=f"Motion Cinemagraph: {asset.original_file_name or asset.id}",
            summary=f"Cinemagraph with {motion_type} effect in {mask_region} region.",
            image_bytes=animation_bytes,
            generation_type="motion_cinemagraph",
            provider="local",
            model="pil+numpy",
            config={"mask_region": mask_region, "motion_type": motion_type, "speed": speed},
            source_asset_ids=[asset.id],
            output_format="gif",
            frame_count=frame_count,
        )


def _create_region_mask(w: int, h: int, region: str) -> np.ndarray:
    """Create a soft circular/elliptical mask for the specified region."""
    y, x = np.ogrid[:h, :w]
    if region == "center":
        cy, cx = h / 2, w / 2
        rx, ry = w / 3, h / 3
    elif region == "top":
        cy, cx = h / 3, w / 2
        rx, ry = w / 3, h / 4
    elif region == "bottom":
        cy, cx = 2 * h / 3, w / 2
        rx, ry = w / 3, h / 4
    else:
        cy, cx = h / 2, w / 2
        rx, ry = w / 3, h / 3

    dist = np.sqrt(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2)
    mask = np.clip(1.0 - dist, 0, 1).astype(np.float32)
    return mask
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_motion_cinemagraph.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/generation/modules/motion_cinemagraph.py backend/tests/test_motion_cinemagraph.py
git commit -m "feat: add motion_cinemagraph module for static bg + moving region"
```

---

## Task 7: Implement motion_zoom_pan Module

**Covers:** [S2]

**Files:**
- Create: `backend/app/services/generation/modules/motion_zoom_pan.py`
- Test: `backend/tests/test_motion_zoom_pan.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_motion_zoom_pan.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.generation.modules.motion_zoom_pan import MotionZoomPanModule


@pytest.fixture
def module():
    return MotionZoomPanModule()


def test_module_metadata(module):
    assert module.name == "motion_zoom_pan"
    assert module.label == "Motion Zoom & Pan"


@pytest.mark.asyncio
async def test_run_produces_gif(module):
    from io import BytesIO
    from PIL import Image

    client = AsyncMock()
    img = Image.new("RGB", (400, 300), color=(100, 180, 120))
    buf = BytesIO()
    img.save(buf, format="PNG")
    client.get_asset_data = AsyncMock(return_value=buf.getvalue())

    asset = MagicMock()
    asset.id = "zoom-test"
    asset.original_file_name = "scenery.jpg"

    result = await module.run(
        page_items=[asset],
        config={"style": "ken-burns", "duration": 2, "intensity": 0.2},
        client=client,
    )

    assert result.output_format == "gif"
    assert result.frame_count >= 24
    assert len(result.image_bytes) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_motion_zoom_pan.py -v`
Expected: FAIL with "No module named 'app.services.generation.modules.motion_zoom_pan'"

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/services/generation/modules/motion_zoom_pan.py
from __future__ import annotations

import math

from PIL import Image

from app.models.settings import SettingsModel
from app.services.generation.modules.base import GenerationResult
from app.services.generation.modules.common import frames_to_animation, load_rgb


class MotionZoomPanModule:
    name = "motion_zoom_pan"
    label = "Motion Zoom & Pan"
    description = "Animated zoom and pan — Ken Burns effect and pan animations."
    default_weight = 1
    source_asset_count = 1
    default_config = {"style": "ken-burns", "duration": 2, "intensity": 0.2}
    config_schema = [
        {
            "key": "style",
            "label": "Style",
            "type": "select",
            "description": "Animation style.",
            "options": [
                {"value": "zoom-in", "label": "Zoom In"},
                {"value": "zoom-out", "label": "Zoom Out"},
                {"value": "ken-burns", "label": "Ken Burns"},
                {"value": "pan-left", "label": "Pan Left"},
                {"value": "pan-right", "label": "Pan Right"},
            ],
            "default": "ken-burns",
        },
        {
            "key": "duration",
            "label": "Duration (seconds)",
            "type": "number",
            "description": "Animation duration in seconds.",
            "min": 1,
            "max": 3,
            "step": 0.5,
            "default": 2,
        },
        {
            "key": "intensity",
            "label": "Intensity",
            "type": "number",
            "description": "Zoom/pan intensity (0.1 = subtle, 0.5 = extreme).",
            "min": 0.1,
            "max": 0.5,
            "step": 0.05,
            "default": 0.2,
        },
    ]

    async def run(self, page_items: list, config: dict, client, settings: SettingsModel) -> GenerationResult:
        asset = page_items[0]
        image_bytes = await client.get_asset_data(asset.id)
        source = load_rgb(image_bytes)

        style = config.get("style", "ken-burns")
        if style not in ("zoom-in", "zoom-out", "ken-burns", "pan-left", "pan-right"):
            style = "ken-burns"
        duration = max(1, min(3, float(config.get("duration", 2) or 2)))
        intensity = max(0.1, min(0.5, float(config.get("intensity", 0.2) or 0.2)))

        fps = 12
        frame_count = int(duration * fps)
        w, h = source.size
        frames = []

        for i in range(frame_count):
            t = i / max(frame_count - 1, 1)

            if style == "zoom-in":
                scale = 1.0 + t * intensity
            elif style == "zoom-out":
                scale = 1.0 + intensity - t * intensity
            elif style == "ken-burns":
                scale = 1.0 + intensity * 0.5 + math.sin(t * math.pi) * intensity * 0.5
            elif style == "pan-left":
                scale = 1.0
            elif style == "pan-right":
                scale = 1.0
            else:
                scale = 1.0

            new_w = int(w * scale)
            new_h = int(h * scale)
            zoomed = source.resize((new_w, new_h), Image.BILINEAR)

            if style in ("pan-left", "pan-right"):
                pan_offset = int(t * (new_w - w) * (1 if style == "pan-left" else -1))
                crop_x = max(0, min(new_w - w, (new_w - w) // 2 + pan_offset))
                crop_y = (new_h - h) // 2
            else:
                crop_x = (new_w - w) // 2
                crop_y = (new_h - h) // 2

            crop_x = max(0, min(crop_x, new_w - w))
            crop_y = max(0, min(crop_y, new_h - h))

            frame = zoomed.crop((crop_x, crop_y, crop_x + w, crop_y + h))
            frames.append(frame)

        animation_bytes = frames_to_animation(frames, fps=fps, format="gif")

        return GenerationResult(
            title=f"Motion Zoom: {asset.original_file_name or asset.id}",
            summary=f"Animated {style} effect ({duration}s).",
            image_bytes=animation_bytes,
            generation_type="motion_zoom_pan",
            provider="local",
            model="pil",
            config={"style": style, "duration": duration, "intensity": intensity},
            source_asset_ids=[asset.id],
            output_format="gif",
            frame_count=frame_count,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_motion_zoom_pan.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/generation/modules/motion_zoom_pan.py backend/tests/test_motion_zoom_pan.py
git commit -m "feat: add motion_zoom_pan module for Ken Burns and pan animations"
```

---

## Task 8: Register Motion Modules

**Covers:** [S2]

**Files:**
- Modify: `backend/app/services/generation/modules/__init__.py:1-53`

- [ ] **Step 1: Add imports and register modules**

```python
# backend/app/services/generation/modules/__init__.py
from __future__ import annotations

from app.schemas.generation import GenerationModuleResponse
from app.services.generation.modules.aerochrome import AerochromeModule
from app.services.generation.modules.apple_weather import AppleWeatherModule
from app.services.generation.modules.base import ModuleDefinition
from app.services.generation.modules.bokeh_blur import BokehBlurModule
from app.services.generation.modules.cartoon import CartoonModule
from app.services.generation.modules.collage import CollageModule
from app.services.generation.modules.cyanotype import CyanotypeModule
from app.services.generation.modules.duotone import DuotoneModule
from app.services.generation.modules.filmstrip import FilmstripModule
from app.services.generation.modules.glitch import GlitchModule
from app.services.generation.modules.halftone import HalftoneModule
from app.services.generation.modules.hdr import HDRModule
from app.services.generation.modules.huji import HujiModule
from app.services.generation.modules.instafilter import InstafilterModule
from app.services.generation.modules.light_leak import LightLeakModule
from app.services.generation.modules.museum_archive import MuseumArchiveModule
from app.services.generation.modules.neon_bloom import NeonBloomModule
from app.services.generation.modules.paper_cutout import PaperCutoutModule
from app.services.generation.modules.pencil_sketch import PencilSketchModule
from app.services.generation.modules.polaroid import PolaroidModule
from app.services.generation.modules.popart import PopArtModule
from app.services.generation.modules.prism_split import PrismSplitModule
from app.services.generation.modules.vintage_film import VintageFilmModule
from app.services.generation.modules.instaweather import InstaWeatherModule
from app.services.generation.modules.motion_parallax import MotionParallaxModule
from app.services.generation.modules.motion_cinemagraph import MotionCinemagraphModule
from app.services.generation.modules.motion_zoom_pan import MotionZoomPanModule
from app.services.generation.modules.motion_pulse import MotionPulseModule

LOCAL_MODULE_CLASSES = [
    AppleWeatherModule,
    InstaWeatherModule,
    MuseumArchiveModule,
    BokehBlurModule,
    VintageFilmModule,
    HujiModule,
    CollageModule,
    InstafilterModule,
    FilmstripModule,
    PopArtModule,
    DuotoneModule,
    HalftoneModule,
    GlitchModule,
    LightLeakModule,
    NeonBloomModule,
    CyanotypeModule,
    PolaroidModule,
    PrismSplitModule,
    PaperCutoutModule,
    PencilSketchModule,
    CartoonModule,
    HDRModule,
    AerochromeModule,
    MotionParallaxModule,
    MotionCinemagraphModule,
    MotionZoomPanModule,
    MotionPulseModule,
]
```

- [ ] **Step 2: Verify modules are discoverable**

Run: `cd backend && python -c "from app.services.generation.modules import MODULES; print([k for k in MODULES.keys() if k.startswith('motion')])"`
Expected: `['motion_parallax', 'motion_cinemagraph', 'motion_zoom_pan', 'motion_pulse']`

- [ ] **Step 3: Run existing tests to verify no regression**

Run: `cd backend && python -m pytest tests/test_generation_modules.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/generation/modules/__init__.py
git commit -m "feat: register motion modules in generation registry"
```

---

## Task 9: Add Alembic Migration for output_format

**Covers:** [S3]

**Files:**
- Create: `backend/app/migrations/versions/xxxx_add_output_format.py`

- [ ] **Step 1: Generate migration**

Run: `cd backend && alembic revision --autogenerate -m "add output_format to generation_history"`
Expected: New migration file created

- [ ] **Step 2: Review and edit migration**

```python
# backend/app/migrations/versions/xxxx_add_output_format.py
"""add output_format to generation_history

Revision ID: <auto-generated>
Revises: <previous>
Create Date: 2026-06-12
"""
from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.add_column(
        "generation_history",
        sa.Column("output_format", sa.String(10), nullable=True, server_default="png"),
    )


def downgrade() -> None:
    op.drop_column("generation_history", "output_format")
```

- [ ] **Step 3: Run migration**

Run: `cd backend && alembic upgrade head`
Expected: Migration applied successfully

- [ ] **Step 4: Commit**

```bash
git add backend/app/migrations/versions/
git commit -m "feat: add output_format column to generation_history"
```

---

## Task 10: Update Persistence for Dynamic Format

**Covers:** [S3]

**Files:**
- Modify: `backend/app/services/generation/persistence.py:42-95`
- Modify: `backend/app/models/generation_history.py:9-44`

- [ ] **Step 1: Add output_format to model**

```python
# backend/app/models/generation_history.py
from datetime import datetime

from sqlalchemy import Boolean, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, UTCDateTime


class GenerationHistoryModel(Base):
    __tablename__ = "generation_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    generation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING_REVIEW")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    source_asset_ids: Mapped[str] = mapped_column(Text, nullable=False)
    output_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    total_token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    config_json: Mapped[str] = mapped_column(Text, nullable=False)
    tags_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_step: Mapped[str | None] = mapped_column(String(255), nullable=True)
    output_format: Mapped[str | None] = mapped_column(String(10), nullable=True, default="png")

    uploaded_asset_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    upload_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    album_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    album_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    album_created: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    album_updated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    accept_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    schedule_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )
```

- [ ] **Step 2: Update persistence to handle output_format**

```python
# backend/app/services/generation/persistence.py
from __future__ import annotations

import json
import logging
from pathlib import Path

from app.models.generation_history import GenerationHistoryModel

logger = logging.getLogger(__name__)

VALID_OUTPUT_FORMATS = {"png", "gif", "webp"}


def _load_existing_history_config(existing: GenerationHistoryModel | None) -> dict:
    if not existing or not existing.config_json:
        return {}

    try:
        parsed = json.loads(existing.config_json)
    except Exception:
        return {}

    return parsed if isinstance(parsed, dict) else {}


def _build_generation_history_config(*, existing_config: dict, result, artifacts) -> dict:
    return {
        **existing_config,
        **result.config,
        "metadata_provenance": artifacts.metadata_provenance,
        **(
            {"source_created_at": artifacts.source_asset.created_at}
            if artifacts.source_asset and artifacts.source_asset.created_at
            else {}
        ),
        **(
            {"source_original_file_name": artifacts.source_asset.original_file_name}
            if artifacts.source_asset and artifacts.source_asset.original_file_name
            else {}
        ),
        **({"exif": artifacts.exif_info} if artifacts.exif_info else {}),
    }


def _get_output_extension(output_format: str | None) -> str:
    if output_format and output_format in VALID_OUTPUT_FORMATS:
        return output_format
    return "png"


def _save_generation_output(output_path, final_bytes: bytes) -> None:
    output_path.write_bytes(final_bytes)


def _prime_generation_thumbnail(output_path) -> None:
    from app.services.generation.history import get_or_create_thumbnail

    try:
        get_or_create_thumbnail(output_path)
    except Exception as thumb_err:
        logger.warning(f"Failed to pre-generate thumbnail during generation cycle: {thumb_err}")


def persist_generation_result(
    *,
    db,
    task_id: str,
    result,
    artifacts,
    output_path,
    image_url: str,
    schedule_id: int | None,
    album_name: str | None,
) -> None:
    from app.services.generation.history import upsert_history_entry

    existing = db.query(GenerationHistoryModel).filter(GenerationHistoryModel.task_id == task_id).first()
    existing_config = _load_existing_history_config(existing)

    output_format = getattr(result, "output_format", "png") or "png"
    ext = _get_output_extension(output_format)

    if output_path.suffix != f".{ext}":
        output_path = output_path.with_suffix(f".{ext}")

    _save_generation_output(output_path, artifacts.final_bytes)
    _prime_generation_thumbnail(output_path)
    logger.info(f"💾 Saved result to {output_path} (task_id={task_id}, format={output_format})")

    upsert_history_entry(
        db,
        task_id,
        generation_type=result.generation_type,
        status="PENDING_REVIEW",
        title=artifacts.ai_title,
        summary=artifacts.ai_summary,
        source_asset_ids=json.dumps(result.source_asset_ids),
        output_path=str(output_path),
        image_url=image_url,
        provider=artifacts.ai_provider,
        model=artifacts.ai_model,
        total_token_count=artifacts.ai_token_count,
        tags_json=json.dumps(artifacts.ai_tags) if artifacts.ai_tags else None,
        schedule_id=schedule_id,
        album_name=album_name,
        output_format=output_format,
        config_json=json.dumps(
            _build_generation_history_config(existing_config=existing_config, result=result, artifacts=artifacts)
        ),
        task_step="review_ready",
    )
```

- [ ] **Step 3: Run tests**

Run: `cd backend && python -m pytest tests/ -v --timeout=30`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/generation/persistence.py backend/app/models/generation_history.py
git commit -m "feat: handle dynamic output format in persistence layer"
```

---

## Task 11: Update History Endpoint for Content-Type

**Covers:** [S3]

**Files:**
- Modify: `backend/app/api/routes_generation.py`

- [ ] **Step 1: Update image endpoint to set correct Content-Type**

```python
# In routes_generation.py, find the image endpoint and update:
# Look for the endpoint that serves /api/generation/history/{task_id}/image
# Add Content-Type header based on output_format

# Example change (find the existing endpoint and modify):
from pathlib import Path

CONTENT_TYPE_MAP = {
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
}

# In the image serving endpoint, add:
# content_type = CONTENT_TYPE_MAP.get(entry.output_format or "png", "image/png")
# return FileResponse(path=entry.output_path, media_type=content_type)
```

- [ ] **Step 2: Run tests**

Run: `cd backend && python -m pytest tests/test_generation_routes.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/routes_generation.py
git commit -m "feat: set correct Content-Type for animated images in API"
```

---

## Task 12: Update Frontend API Types

**Covers:** [S4]

**Files:**
- Modify: `frontend/src/api/client.ts:378-404`

- [ ] **Step 1: Add output_format to GenerationHistoryEntry**

```typescript
// frontend/src/api/client.ts
export type GenerationHistoryEntry = {
  id: number;
  task_id: string;
  generation_type: string;
  status: 'QUEUED' | 'RUNNING' | 'PENDING_REVIEW' | 'UPLOADED' | 'REJECTED' | 'FAILED' | string;
  title: string;
  summary: string;
  source_asset_ids: string;
  output_path: string | null;
  image_url: string | null;
  provider: string | null;
  model: string | null;
  total_token_count: number | null;
  config_json: string;
  tags_json: string | null;
  task_step: string | null;
  uploaded_asset_id: string | null;
  upload_status: string | null;
  album_id: string | null;
  album_name: string | null;
  album_created: boolean;
  album_updated: boolean;
  accept_notes: string | null;
  accepted_at: string | null;
  output_format: 'png' | 'gif' | 'webp' | null;
  created_at: string;
  updated_at: string;
};
```

- [ ] **Step 2: Build frontend to verify types**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no type errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat: add output_format to GenerationHistoryEntry type"
```

---

## Task 13: Update SecureImage for Auto-Detection

**Covers:** [S4]

**Files:**
- Modify: `frontend/src/components/SecureImage.tsx:7-73`

- [ ] **Step 1: Update SecureImage to handle animated formats**

```typescript
// frontend/src/components/SecureImage.tsx
import { useEffect, useState } from 'react';

interface SecureImageProps extends React.ImgHTMLAttributes<HTMLImageElement> {
  src: string;
  autoPlay?: boolean;
}

export function SecureImage({ src, autoPlay = true, ...props }: SecureImageProps) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [error, setError] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    if (!src) return;

    let isMounted = true;
    let createdUrl: string | null = null;
    const token = localStorage.getItem('dailyfx_token');

    async function fetchImage() {
      try {
        setLoading(true);
        const headers: Record<string, string> = {};
        if (token) {
          headers['Authorization'] = `Bearer ${token}`;
        }

        const response = await fetch(src, { headers });
        if (!response.ok) throw new Error('Failed to fetch image');

        const blob = await response.blob();
        if (isMounted) {
          const url = URL.createObjectURL(blob);
          createdUrl = url;
          setBlobUrl(url);
          setError(false);
        }
      } catch {
        if (isMounted) {
          setError(true);
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    fetchImage();

    return () => {
      isMounted = false;
      if (createdUrl) {
        URL.revokeObjectURL(createdUrl);
      }
    };
  }, [src]);

  if (error) {
    return (
      <div className={`${props.className} flex items-center justify-center bg-stone-100 text-stone-400`}>
        <span className="text-xs">Failed to load</span>
      </div>
    );
  }

  if (loading || !blobUrl) {
    return (
      <div className={`${props.className} animate-pulse rounded-[inherit] bg-stone-100/90`} />
    );
  }

  // GIF and WebP animations auto-play in browsers via <img> tag
  // No special handling needed — browsers natively animate <img src="*.gif">
  return <img src={blobUrl} {...props} />;
}
```

- [ ] **Step 2: Build frontend**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/SecureImage.tsx
git commit -m "feat: SecureImage auto-detects animated GIF/WebP formats"
```

---

## Task 14: Add Motion Badge in History

**Covers:** [S4]

**Files:**
- Modify: `frontend/src/pages/History/HistoryPage.tsx`

- [ ] **Step 1: Add motion badge to history items**

```typescript
// In HistoryPage.tsx, find where history items are rendered
// Add a badge for animated results:

// Look for the title/summary rendering section and add:
{entry.output_format && entry.output_format !== 'png' && (
  <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-700">
    <svg className="h-2.5 w-2.5" viewBox="0 0 24 24" fill="currentColor">
      <path d="M8 5v14l11-7z"/>
    </svg>
    Motion
  </span>
)}
```

- [ ] **Step 2: Build frontend**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/History/HistoryPage.tsx
git commit -m "feat: add Motion badge for animated results in history"
```

---

## Task 15: Run Full Test Suite

**Covers:** [S5]

**Files:**
- All modified files

- [ ] **Step 1: Run backend tests**

Run: `cd backend && python -m pytest tests/ -v --timeout=60`
Expected: All tests pass

- [ ] **Step 2: Run frontend tests**

Run: `cd frontend && npm test`
Expected: All tests pass

- [ ] **Step 3: Run lint**

Run: `cd backend && python -m ruff check .`
Expected: No errors

- [ ] **Step 4: Run frontend build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: complete motion effects implementation (GIF/WebP animation support)"
```

---

## Execution Summary

| Task | Description | Est. Time |
|------|-------------|-----------|
| T1 | Add imageio dependency | 5 min |
| T2 | Extend GenerationResult | 10 min |
| T3 | Add frames_to_animation helper | 15 min |
| T4 | Implement motion_pulse | 20 min |
| T5 | Implement motion_parallax | 25 min |
| T6 | Implement motion_cinemagraph | 25 min |
| T7 | Implement motion_zoom_pan | 20 min |
| T8 | Register motion modules | 5 min |
| T9 | Add Alembic migration | 10 min |
| T10 | Update persistence layer | 15 min |
| T11 | Update API Content-Type | 10 min |
| T12 | Update frontend types | 5 min |
| T13 | Update SecureImage | 10 min |
| T14 | Add Motion badge | 10 min |
| T15 | Full test suite verification | 15 min |
| **Total** | | **~3.5 hours** |
