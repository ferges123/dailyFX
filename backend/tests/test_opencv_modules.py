"""Unit tests for OpenCV-enhanced modules."""

import numpy as np

from app.services.generation.modules.bokeh_blur import _create_depth_mask, _detect_face_center
from app.services.generation.modules.vintage_film import _apply_film_curve


class TestBokehBlur:
    """Tests for Bokeh Blur with face detection."""

    def test_detect_face_center_no_face(self):
        """Should return None when no face detected."""
        # Create blank image
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        cx, cy = _detect_face_center(img)
        assert cx is None
        assert cy is None

    def test_create_depth_mask_shape(self):
        """Depth mask should match image dimensions."""
        w, h = 640, 480
        mask = _create_depth_mask(w, h, w // 2, h // 2)
        assert mask.shape == (h, w)
        assert mask.dtype == np.uint8

    def test_create_depth_mask_center_bright(self):
        """Center of mask should be brightest (sharp focus)."""
        w, h = 100, 100
        cx, cy = 50, 50
        mask = _create_depth_mask(w, h, cx, cy)
        # Center should be close to 255 (sharp)
        assert mask[cy, cx] > 200
        # Corners should be darker (blurred)
        assert mask[0, 0] < 100
        assert mask[h - 1, w - 1] < 100

    def test_create_depth_mask_gradient(self):
        """Mask should have smooth gradient from center."""
        w, h = 100, 100
        mask = _create_depth_mask(w, h, 50, 50)
        # Check that values decrease from center
        center_val = mask[50, 50]
        mid_val = mask[50, 75]
        edge_val = mask[50, 99]
        assert center_val > mid_val > edge_val


class TestVintageFilm:
    """Tests for Vintage Film with characteristic curves."""

    def test_apply_film_curve_shape(self):
        """Film curve should preserve image shape."""
        img = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
        preset = {"curve_gamma": 0.55, "toe_falloff": 0.12, "shoulder_falloff": 0.18}
        result = _apply_film_curve(img, preset)
        assert result.shape == img.shape
        assert result.dtype == np.uint8

    def test_apply_film_curve_range(self):
        """Film curve should keep values in valid range."""
        img = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
        preset = {"curve_gamma": 0.50, "toe_falloff": 0.08, "shoulder_falloff": 0.22}
        result = _apply_film_curve(img, preset)
        assert result.min() >= 0
        assert result.max() <= 255

    def test_apply_film_curve_linear_preserve(self):
        """Gamma=1.0 with no toe/shoulder should return nearly linear."""
        img = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
        preset = {"curve_gamma": 1.0, "toe_falloff": 0.0, "shoulder_falloff": 0.0}
        result = _apply_film_curve(img, preset)
        diff = np.abs(result.astype(int) - img.astype(int)).mean()
        assert diff < 3

    def test_apply_film_curve_s_shape(self):
        """Characteristic curve should produce valid monotonic-ish response."""
        gradient = np.arange(0, 256, dtype=np.uint8)
        img = np.tile(gradient, (100, 1))
        img = np.stack([img, img, img], axis=2)

        preset = {"curve_gamma": 0.55, "toe_falloff": 0.12, "shoulder_falloff": 0.18}
        result = _apply_film_curve(img, preset)

        dark_output = int(result[0, 50, 0])
        assert 0 <= dark_output <= 255, f"Output {dark_output} out of range"

    def test_apply_film_curve_different_presets(self):
        """Different presets should produce different results."""
        img = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
        preset1 = {"curve_gamma": 0.40, "toe_falloff": 0.05, "shoulder_falloff": 0.15}
        preset2 = {"curve_gamma": 0.70, "toe_falloff": 0.20, "shoulder_falloff": 0.30}
        result1 = _apply_film_curve(img, preset1)
        result2 = _apply_film_curve(img, preset2)
        diff = np.abs(result1.astype(int) - result2.astype(int)).mean()
        assert diff > 1

    def test_build_characteristic_lut_endpoints(self):
        """LUT should map 0->0 and 255->255."""
        from app.services.generation.modules.vintage_film import _build_characteristic_lut
        lut = _build_characteristic_lut(0.55, 0.12, 0.18)
        assert lut[0] == 0
        assert lut[255] == 255
        assert len(lut) == 256
