# InstaWeather Safe Area Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Redesign the InstaWeather overlay into a full-screen, photography-style "Safe Area" watermark layout with custom vector icons and face protection shifting.

**Architecture:** We will extend the weather API data query to fetch advanced hourly/daily metrics. We will draw custom minimal icons and text elements dynamically with PIL inside a 7% margin boundary, incorporating a dynamic collision detection routine that shifts overlapping blocks away from faces.

**Tech Stack:** Python, Pillow (PIL), Open-Meteo API.

---

### Task 1: Update API Parameters and Weather Parsing

**Files:**
- Modify: `backend/app/services/generation/modules/instaweather.py`
- Test: `backend/tests/test_instaweather.py`

**Step 1: Write the failing test**
Update the weather data mapping/fetching test in `backend/tests/test_instaweather.py` to expect feels-like temperature, cloudiness, humidity, wind, and sunrise/sunset.

```python
# Add to backend/tests/test_instaweather.py
def test_fetch_weather_structure():
    # Test that fallback geocode/weather provides all required fields
    from app.services.generation.modules.instaweather import get_fallback_weather
    data = get_fallback_weather(52.23, 6)
    assert "apparent_temp_c" in data
    assert "cloud_cover" in data
    assert "humidity" in data
    assert "wind_speed" in data
    assert "wind_dir" in data
    assert "sunrise" in data
    assert "sunset" in data
```

**Step 2: Run test to verify it fails**
Run: `python3 -m pytest backend/tests/test_instaweather.py::test_fetch_weather_structure -v`
Expected: FAIL with `AssertionError: assert 'apparent_temp_c' in data`

**Step 3: Write minimal implementation**
1. Modify `fetch_weather` in `backend/app/services/generation/modules/instaweather.py` to request:
   - hourly: `apparent_temperature,cloud_cover,relative_humidity_2m,wind_speed_10m,wind_direction_10m`
   - daily: `sunrise,sunset`
2. Parse hourly variables corresponding to the closest hour, and daily sunrise/sunset corresponding to the day.
3. Modify `get_fallback_weather` to populate all these new keys with realistic defaults:
   - `apparent_temp_c`: close to `temp_c`.
   - `cloud_cover`: depends on weather code (0 = 10, 3 = 70, etc.).
   - `humidity`: random/fallback around 50-80%.
   - `wind_speed`: 5-20 km/h.
   - `wind_dir`: "NE" or other directions based on wind degrees.
   - `sunrise`: "05:12".
   - `sunset`: "20:45".

**Step 4: Run test to verify it passes**
Run: `python3 -m pytest backend/tests/test_instaweather.py::test_fetch_weather_structure -v`
Expected: PASS

**Step 5: Commit**
```bash
git add backend/app/services/generation/modules/instaweather.py backend/tests/test_instaweather.py
git commit -m "feat(instaweather): extend weather API querying with metrics and fallbacks"
```

---

### Task 2: Implement Vector Icon Draw Functions

**Files:**
- Modify: `backend/app/services/generation/modules/instaweather.py`
- Test: `backend/tests/test_instaweather.py`

**Step 1: Write the failing test**
Create a test to verify icon-drawing helper functions exist and return success without errors.

```python
# Add to backend/tests/test_instaweather.py
def test_vector_icons():
    from PIL import Image, ImageDraw
    from app.services.generation.modules.instaweather import (
        draw_pin_icon,
        draw_humidity_icon,
        draw_wind_icon,
        draw_sunrise_icon,
        draw_sunset_icon,
    )
    img = Image.new("RGBA", (100, 100))
    draw = ImageDraw.Draw(img)
    draw_pin_icon(draw, 10, 10, 20, (255, 255, 255))
    draw_humidity_icon(draw, 10, 10, 20, (255, 255, 255))
    draw_wind_icon(draw, 10, 10, 20, (255, 255, 255))
    draw_sunrise_icon(draw, 10, 10, 20, (255, 255, 255))
    draw_sunset_icon(draw, 10, 10, 20, (255, 255, 255))
```

**Step 2: Run test to verify it fails**
Run: `python3 -m pytest backend/tests/test_instaweather.py::test_vector_icons -v`
Expected: FAIL with `ImportError`

**Step 3: Write minimal implementation**
Write the following helper functions in `backend/app/services/generation/modules/instaweather.py` using `ImageDraw` paths/shapes:
- `draw_pin_icon`: teardrop outline + inner center circle.
- `draw_humidity_icon`: droplet shape (pointy top, rounded bottom).
- `draw_wind_icon`: two parallel horizontal lines with loops/waves.
- `draw_sunrise_icon` & `draw_sunset_icon`: horizon line + half sun + rays pointing up/down.
- Add drawing for main weather states: `draw_main_weather_icon(draw, x, y, size, code, scale)`:
  - Sun (Clear): Circle with radial rays.
  - Clouds (Cloudy): Multiple overlapping white ellipses.
  - Rain: Cloud with falling blue streaks.
  - Snow: Cloud with white dots.
  - Thunderstorm: Cloud with a yellow zig-zag bolt.

**Step 4: Run test to verify it passes**
Run: `python3 -m pytest backend/tests/test_instaweather.py::test_vector_icons -v`
Expected: PASS

**Step 5: Commit**
```bash
git add backend/app/services/generation/modules/instaweather.py backend/tests/test_instaweather.py
git commit -m "feat(instaweather): add dynamic vector icon drawing helpers using PIL"
```

---

### Task 3: Implement Layout Rendering with Collision Avoidance

**Files:**
- Modify: `backend/app/services/generation/modules/instaweather.py`
- Test: `backend/tests/test_instaweather.py`

**Step 1: Write the failing test**
Update the rendering flow test to verify the new safe-area boundaries, bounding boxes, and collision shifting mechanism.

```python
# Add to backend/tests/test_instaweather.py
def test_collision_avoidance():
    # Mock face positions and check if resolved positions shift away from them
    pass
```

**Step 2: Run test to verify it fails**
Run: `python3 -m pytest backend/tests/test_instaweather.py -v`
Expected: FAIL or mismatch with new schema

**Step 3: Write minimal implementation**
1. Re-implement `_draw_graphics_overlay` in `instaweather.py` to:
   - Position the 5 blocks (Top-Left, Left-Middle, Top-Right, Bottom-Left, Bottom-Right) within the 7% safe-area margin.
   - Use `Inter-Regular.ttf` for text rendering.
   - Implement shadow offset drawing for readability on bright backgrounds.
   - Implement "fake bold" for the City Name.
   - Check if any block overlaps with face coordinates.
   - Implement the shift-inward (corner blocks), shift-vertical/horizontal (Left-Middle), and hide-fallback logic for collision resolution.
2. Render the custom vector icons inline using the helpers from Task 2.

**Step 4: Run test to verify it passes**
Run: `python3 -m pytest backend/tests/test_instaweather.py -v`
Expected: PASS (All tests pass)

**Step 5: Commit**
```bash
git add backend/app/services/generation/modules/instaweather.py backend/tests/test_instaweather.py
git commit -m "feat(instaweather): implement safe-area layout rendering and face protection"
```
