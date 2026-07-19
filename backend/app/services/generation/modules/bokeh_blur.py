from __future__ import annotations

import cv2
import numpy as np
from PIL import Image, ImageEnhance

from app.models.settings import SettingsModel
from app.services.generation.modules.base import GenerationResult
from app.services.generation.modules.common import add_grain, load_rgb, save_png
from app.utils.debug_logger import debug_log


class BokehBlurModule:
    name = "bokeh_blur"
    label = "Bokeh Blur"
    description = "Professional depth of field with face detection."
    default_weight = 3
    default_config = {"blur_strength": 15, "focus_area": "auto"}
    config_schema = [
        {
            "key": "blur_strength",
            "label": "Blur strength",
            "type": "number",
            "description": "Background blur intensity (5 = subtle, 25 = extreme).",
            "min": 5,
            "max": 25,
            "step": 2,
            "default": 15,
        },
        {
            "key": "focus_area",
            "label": "Focus area",
            "type": "select",
            "description": "Where to keep sharp focus.",
            "options": [
                {"value": "auto", "label": "Auto (face detection)"},
                {"value": "center", "label": "Center"},
                {"value": "top", "label": "Top third"},
                {"value": "bottom", "label": "Bottom third"},
            ],
            "default": "auto",
        },
    ]

    async def run(self, page_items: list, config: dict, client, settings: SettingsModel) -> GenerationResult:
        asset = page_items[0]
        debug_log("Bokeh: Loading asset", asset_id=asset.id)

        image_bytes = await client.get_asset_data(asset.id)
        debug_log("Bokeh: Loaded image", size_bytes=len(image_bytes))

        source = load_rgb(image_bytes)
        debug_log("Bokeh: Image dimensions", width=source.width, height=source.height)

        blur_strength = max(5, min(25, int(config.get("blur_strength", 15) or 15)))
        focus_area = config.get("focus_area", "auto")
        if focus_area not in ("auto", "center", "top", "bottom"):
            focus_area = "auto"

        debug_log("Bokeh: Config", blur_strength=blur_strength, focus_area=focus_area)

        result = _apply_bokeh_opencv(source, blur_strength, focus_area)
        debug_log("Bokeh: Effect applied", result_size=f"{result.width}x{result.height}")

        return GenerationResult(
            title=f"Bokeh: {asset.original_file_name or asset.id}",
            summary="Professional depth of field with intelligent focus detection.",
            image_bytes=save_png(result),
            generation_type="bokeh_blur",
            provider="local",
            model="opencv+pil",
            config={"blur_strength": blur_strength, "focus_area": focus_area},
            source_asset_ids=[asset.id],
        )


def _apply_bokeh_opencv(img: Image.Image, blur_strength: int, focus_area: str) -> Image.Image:
    """Professional bokeh using OpenCV with face detection."""
    debug_log("Bokeh: Starting OpenCV processing", blur_strength=blur_strength, focus_area=focus_area)

    # Convert PIL to OpenCV
    img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    h, w = img_cv.shape[:2]
    debug_log("Bokeh: Converted to OpenCV", height=h, width=w)

    # Detect focus point and keep-sharp radius
    if focus_area == "auto":
        cx, cy, focus_radius = _detect_face_center(img_cv)
        if cx is None:  # No face found, use center
            cx, cy = w // 2, h // 2
            focus_radius = min(w, h) * 0.20
            debug_log("Bokeh: No face detected, using center", cx=cx, cy=cy)
        else:
            debug_log("Bokeh: Face detected", cx=cx, cy=cy)
    elif focus_area == "top":
        cx, cy = w // 2, h // 3
        focus_radius = min(w, h) * 0.20
        debug_log("Bokeh: Using top focus", cx=cx, cy=cy)
    elif focus_area == "bottom":
        cx, cy = w // 2, int(h * 0.67)
        focus_radius = min(w, h) * 0.20
        debug_log("Bokeh: Using bottom focus", cx=cx, cy=cy)
    else:  # center
        cx, cy = w // 2, h // 2
        focus_radius = min(w, h) * 0.20
        debug_log("Bokeh: Using center focus", cx=cx, cy=cy)

    # Create depth mask: plateau of 1.0 within focus_radius, smooth falloff beyond
    debug_log("Bokeh: Creating depth mask")
    mask = _create_depth_mask(w, h, cx, cy, focus_radius)

    # Background blur. Previously this called bilateralFilter first, which
    # preserves edges — but the result is then immediately fed to a Gaussian
    # blur, which destroys the edges anyway. The bilateral step was wasted
    # work (it's much slower than Gaussian), so it has been removed.
    debug_log("Bokeh: Applying Gaussian blur", kernel_size=blur_strength * 2 + 1)
    blurred = cv2.GaussianBlur(img_cv, (blur_strength * 2 + 1, blur_strength * 2 + 1), 0)

    # Blend sharp and blurred based on mask (vectorized)
    debug_log("Bokeh: Blending sharp and blurred")
    mask_3ch = cv2.merge([mask, mask, mask]).astype(np.float32) / 255.0
    result = (img_cv.astype(np.float32) * mask_3ch + blurred.astype(np.float32) * (1 - mask_3ch)).astype(np.uint8)

    # Convert back to PIL
    debug_log("Bokeh: Converting back to PIL")
    result_rgb = cv2.cvtColor(result, cv2.COLOR_BGR2RGB)
    result_pil = Image.fromarray(result_rgb)

    # Final enhancements
    debug_log("Bokeh: Applying final enhancements")
    result_pil = ImageEnhance.Color(result_pil).enhance(1.1)
    result_pil = ImageEnhance.Contrast(result_pil).enhance(1.05)
    result_pil = add_grain(result_pil, strength=0.015, blur=0.0)

    debug_log("Bokeh: Processing complete")
    return result_pil


def _detect_face_center(img_cv: np.ndarray) -> tuple[int | None, int | None, float]:
    """Detect face using Haar Cascade and return center + keep-sharp radius.

    The radius ensures the entire face stays sharp, not just the center pixel.
    """
    try:
        # Convert to grayscale for detection
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)

        # Load Haar Cascade (built into OpenCV)
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

        # Detect faces
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

        if len(faces) > 0:
            # Use largest face
            largest_face = max(faces, key=lambda f: f[2] * f[3])
            x, y, fw, fh = largest_face
            # Keep-sharp radius covers the face with some margin so the
            # full head (not just the nose) stays in focus.
            margin = 1.5
            radius = max(fw, fh) * 0.5 * margin
            return x + fw // 2, y + fh // 2, float(radius)
    except Exception:
        pass

    return None, None, 0.0


def _create_depth_mask(w: int, h: int, cx: int, cy: int, focus_radius: float) -> np.ndarray:
    """Create a depth-of-field mask with a sharp plateau and smooth Gaussian falloff.

    - 1.0 (sharp) inside `focus_radius` from (cx, cy)
    - Smooth Gaussian transition to 0.0 (fully blurred) at the edges
    This keeps the entire subject sharp while blurring only the background.
    """
    y, x = np.ogrid[:h, :w]

    # Euclidean distance from focus point (in pixels)
    dx = (x - cx).astype(np.float32)
    dy = (y - cy).astype(np.float32)
    dist = np.sqrt(dx * dx + dy * dy)

    # Plateau (1.0) inside focus_radius, Gaussian falloff beyond it.
    # Sigma controls how gradual the transition is — proportional to focus_radius
    # so larger subjects get a wider transition band.
    sigma = max(focus_radius * 1.2, min(w, h) * 0.08)
    mask = np.exp(-(np.maximum(dist - focus_radius, 0.0) ** 2) / (2.0 * sigma * sigma))

    return (mask * 255.0).clip(0.0, 255.0).astype(np.uint8)
