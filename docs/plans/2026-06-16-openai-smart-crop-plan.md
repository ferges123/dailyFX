# OpenAI DALL-E Smart Crop Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Implement face-aware smart cropping (Option B) for OpenAI and Local AI image generation workflows, so that vertical or horizontal images are cropped to a square centered around the largest detected face instead of stretching.

**Architecture:** We will implement a helper `_crop_to_largest_face` in `ai_image.py` that parses the bounding boxes from Immich via `people_context` to center the crop box on the largest face, falling back to center-cropping. We will integrate this in the pre-processing step of `generate_ai_image()` for `openai` and `local` providers.

**Tech Stack:** Python, FastAPI, Pytest, Pillow

---

### Task 1: Smart Crop Helper Function

**Files:**
- Modify: `backend/app/services/generation/ai_image.py`
- Test: `backend/tests/test_ai_budget.py`

**Step 1: Write the failing test**

Add a unit test in `backend/tests/test_ai_budget.py` that verifies the behavior of `_crop_to_largest_face`.

```python
def test_crop_to_largest_face():
    from PIL import Image
    from io import BytesIO
    from app.services.generation.ai_image import _crop_to_largest_face

    # Create a 200x400 vertical red image
    img = Image.new("RGB", (200, 400), (255, 0, 0))
    # Draw a green face box at (50, 50) to (150, 150)
    for x in range(50, 150):
        for y in range(50, 150):
            img.putpixel((x, y), (0, 255, 0))
            
    out = BytesIO()
    img.save(out, format="PNG")
    img_bytes = out.getvalue()
    
    # Large face near the top (bounding box in pixels)
    faces = [
        {
            "bounding_box_x1": 50.0,
            "bounding_box_y1": 50.0,
            "bounding_box_x2": 150.0,
            "bounding_box_y2": 150.0,
        }
    ]
    
    cropped_bytes = _crop_to_largest_face(img_bytes, faces)
    cropped_img = Image.open(BytesIO(cropped_bytes))
    
    assert cropped_img.size == (200, 200)
    # The crop box should center on cy = 100, which means top = 100 - 100 = 0.
    # So the green square should be fully contained at the top of the cropped image.
    assert cropped_img.getpixel((50, 50)) == (0, 255, 0)
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest backend/tests/test_ai_budget.py -k test_crop_to_largest_face -v`
Expected: FAIL (ImportError / Attribute`KeyError`)

**Step 3: Write minimal implementation**

Add `_crop_to_largest_face` in `backend/app/services/generation/ai_image.py`.

```python
def _crop_to_largest_face(image_bytes: bytes, faces: list[dict] | None) -> bytes:
    from PIL import Image
    from io import BytesIO
    
    img = Image.open(BytesIO(image_bytes))
    w, h = img.size
    target_dim = min(w, h)
    
    cx, cy = w / 2.0, h / 2.0
    
    if faces:
        largest_face = None
        max_area = -1.0
        for face in faces:
            x1 = face.get("bounding_box_x1")
            y1 = face.get("bounding_box_y1")
            x2 = face.get("bounding_box_x2")
            y2 = face.get("bounding_box_y2")
            if None not in (x1, y1, x2, y2):
                area = (x2 - x1) * (y2 - y1)
                if area > max_area:
                    max_area = area
                    largest_face = face
        if largest_face:
            cx = (largest_face["bounding_box_x1"] + largest_face["bounding_box_x2"]) / 2.0
            cy = (largest_face["bounding_box_y1"] + largest_face["bounding_box_y2"]) / 2.0

    left = int(cx - target_dim / 2.0)
    top = int(cy - target_dim / 2.0)
    
    left = max(0, min(w - target_dim, left))
    top = max(0, min(h - target_dim, top))
    
    cropped = img.crop((left, top, left + target_dim, top + target_dim))
    out = BytesIO()
    cropped.save(out, format="PNG")
    return out.getvalue()
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest backend/tests/test_ai_budget.py -k test_crop_to_largest_face -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/services/generation/ai_image.py backend/tests/test_ai_budget.py
git commit -m "backend: implement smart crop helper for OpenAI"
```

---

### Task 2: Integrate in generate_ai_image

**Files:**
- Modify: `backend/app/services/generation/ai_image.py`
- Test: `backend/tests/test_ai_budget.py`

**Step 1: Write the failing test**

Update `test_generate_ai_image_uses_openai_endpoint` (or similar OpenAI test) to verify that `faces` are cropped and a square image is sent.
If no test exists, write a new test `test_generate_ai_image_openai_crops_image`.

```python
def test_generate_ai_image_openai_crops_image(monkeypatch):
    from unittest.mock import MagicMock
    from app.services.generation.ai_image import generate_ai_image
    
    init_db()
    settings = SimpleNamespace(
        ai_image_provider="openai",
        ai_image_model="dall-e-2",
        ai_image_hourly_limit=4,
        encrypted_openai_api_key="secret",
    )
    
    fake_client = _FakeAsyncClient()
    # Mock Response returning base64
    fake_client.next_post_response = _FakeResponse(json_body={"data": [{"b64_json": "ZmFrZV9wbmdfYnl0ZXM="}]})
    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: fake_client)
    
    # 200x400 source image
    from PIL import Image
    from io import BytesIO
    img = Image.new("RGB", (200, 400), (255, 0, 0))
    out = BytesIO()
    img.save(out, format="PNG")
    raw_image_bytes = out.getvalue()
    
    faces = [{
        "bounding_box_x1": 50.0,
        "bounding_box_y1": 50.0,
        "bounding_box_x2": 150.0,
        "bounding_box_y2": 150.0,
    }]
    
    with (
        patch("app.services.generation.ai_image._decrypt_provider_key", return_value="secret"),
        patch("app.services.generation.ai_image.reserve_ai_usage", return_value=None),
    ):
        result = asyncio.run(generate_ai_image(settings, raw_image_bytes, "make it playful", faces=faces))
        
    assert result.provider == "openai"
    # Verify the image sent in the files parameter is square (200x200)
    sent_file = fake_client.requests[0]["files"][0][1][1]
    sent_img = Image.open(BytesIO(sent_file))
    assert sent_img.size == (200, 200)
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest backend/tests/test_ai_budget.py -k test_generate_ai_image_openai_crops_image -v`
Expected: FAIL (assertion error: `sent_img.size == (200, 400)`)

**Step 3: Write minimal implementation**

Update `generate_ai_image` signature and implementation in `backend/app/services/generation/ai_image.py`.

```python
async def generate_ai_image(
    settings: SettingsModel,
    image_bytes: bytes,
    prompt: str,
    negative_prompt: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    context_hint: str | None = None,
    prompt_enrichment_context_hint: str | None = None,
    faces: list[dict] | None = None,
) -> AIImageResult:
    ...
    # Crop before encoding for OpenAI or Local AI
    if provider in {"openai", "local"}:
        image_bytes = _crop_to_largest_face(image_bytes, faces)
        
    encoded_image_bytes, mime_type = encode_image_for_provider(image_bytes, provider)
    ...
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest backend/tests/test_ai_budget.py -k test_generate_ai_image_openai_crops_image -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/services/generation/ai_image.py backend/tests/test_ai_budget.py
git commit -m "backend: integrate smart crop pre-processing in generate_ai_image"
```

---

### Task 3: Integrate Bounding Boxes in Pipeline Module

**Files:**
- Modify: `backend/app/services/generation/modules/ai_style_base.py`
- Test: `backend/tests/test_generation_modules.py`

**Step 1: Write the failing test**

Run the general module tests: `python3 -m pytest backend/tests/test_generation_modules.py -v`
Ensure everything compiles and works correctly.

**Step 2: Write minimal implementation**

Update `AIStyleBaseModule.run` in `backend/app/services/generation/modules/ai_style_base.py` to pass the faces from the `people_context` object.

```python
            try:
                result = await generate_ai_image(
                    settings,
                    image_bytes,
                    prompt,
                    negative_prompt=self.default_negative_prompt,
                    context_hint=people_context.anonymized_prompt_hint() if people_context else None,
                    prompt_enrichment_context_hint=enrichment_context_hint,
                    faces=people_context.to_dict()["faces"] if people_context else None,
                )
```

**Step 3: Run test to verify it passes**

Run: `make backend-test`
Expected: PASS (All 327+ tests pass)

**Step 4: Commit**

```bash
git add backend/app/services/generation/modules/ai_style_base.py
git commit -m "backend: pass detected faces to generate_ai_image in style base module"
```
