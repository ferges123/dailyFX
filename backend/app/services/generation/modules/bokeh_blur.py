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
        debug_log(f"Bokeh: Loading asset", asset_id=asset.id)
        
        image_bytes = await client.get_asset_data(asset.id)
        debug_log(f"Bokeh: Loaded image", size_bytes=len(image_bytes))
        
        source = load_rgb(image_bytes)
        debug_log(f"Bokeh: Image dimensions", width=source.width, height=source.height)
        
        blur_strength = max(5, min(25, int(config.get("blur_strength", 15) or 15)))
        focus_area = config.get("focus_area", "auto")
        if focus_area not in ("auto", "center", "top", "bottom"):
            focus_area = "auto"
        
        debug_log(f"Bokeh: Config", blur_strength=blur_strength, focus_area=focus_area)
        
        result = _apply_bokeh_opencv(source, blur_strength, focus_area)
        debug_log(f"Bokeh: Effect applied", result_size=f"{result.width}x{result.height}")

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
    debug_log(f"Bokeh: Starting OpenCV processing", blur_strength=blur_strength, focus_area=focus_area)
    
    # Convert PIL to OpenCV
    img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    h, w = img_cv.shape[:2]
    debug_log(f"Bokeh: Converted to OpenCV", height=h, width=w)
    
    # Detect focus point
    if focus_area == "auto":
        cx, cy = _detect_face_center(img_cv)
        if cx is None:  # No face found, use center
            cx, cy = w // 2, h // 2
            debug_log(f"Bokeh: No face detected, using center", cx=cx, cy=cy)
        else:
            debug_log(f"Bokeh: Face detected", cx=cx, cy=cy)
    elif focus_area == "top":
        cx, cy = w // 2, h // 3
        debug_log(f"Bokeh: Using top focus", cx=cx, cy=cy)
    elif focus_area == "bottom":
        cx, cy = w // 2, int(h * 0.67)
        debug_log(f"Bokeh: Using bottom focus", cx=cx, cy=cy)
    else:  # center
        cx, cy = w // 2, h // 2
        debug_log(f"Bokeh: Using center focus", cx=cx, cy=cy)
    
    # Create depth mask (gradient from focus point)
    debug_log(f"Bokeh: Creating depth mask")
    mask = _create_depth_mask(w, h, cx, cy)
    
    # Apply edge-preserving blur (better than Gaussian)
    debug_log(f"Bokeh: Applying bilateral filter")
    blurred = cv2.bilateralFilter(img_cv, d=9, sigmaColor=75, sigmaSpace=75)
    debug_log(f"Bokeh: Applying Gaussian blur", kernel_size=blur_strength*2+1)
    blurred = cv2.GaussianBlur(blurred, (blur_strength*2+1, blur_strength*2+1), 0)
    
    # Blend sharp and blurred based on mask (vectorized)
    debug_log(f"Bokeh: Blending sharp and blurred")
    mask_3ch = cv2.merge([mask, mask, mask]).astype(np.float32) / 255.0
    result = (img_cv.astype(np.float32) * mask_3ch + blurred.astype(np.float32) * (1 - mask_3ch)).astype(np.uint8)
    
    # Convert back to PIL
    debug_log(f"Bokeh: Converting back to PIL")
    result_rgb = cv2.cvtColor(result, cv2.COLOR_BGR2RGB)
    result_pil = Image.fromarray(result_rgb)
    
    # Final enhancements
    debug_log(f"Bokeh: Applying final enhancements")
    result_pil = ImageEnhance.Color(result_pil).enhance(1.1)
    result_pil = ImageEnhance.Contrast(result_pil).enhance(1.05)
    result_pil = add_grain(result_pil, strength=0.015, blur=0.0)
    
    debug_log(f"Bokeh: Processing complete")
    return result_pil


def _detect_face_center(img_cv: np.ndarray) -> tuple[int | None, int | None]:
    """Detect face using Haar Cascade and return center point."""
    try:
        # Convert to grayscale for detection
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        # Load Haar Cascade (built into OpenCV)
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        
        # Detect faces
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
        
        if len(faces) > 0:
            # Use largest face
            largest_face = max(faces, key=lambda f: f[2] * f[3])
            x, y, w, h = largest_face
            return x + w // 2, y + h // 2
    except Exception:
        pass
    
    return None, None


def _create_depth_mask(w: int, h: int, cx: int, cy: int) -> np.ndarray:
    """Create radial gradient mask for depth of field."""
    y, x = np.ogrid[:h, :w]
    
    # Distance from center
    dx = (x - cx) / w
    dy = (y - cy) / h
    dist = np.sqrt(dx*dx + dy*dy)
    
    # Normalize and invert (1 = sharp, 0 = blur)
    mask = 1.0 - np.clip(dist * 2.5, 0, 1)
    
    # Smooth transition
    mask = np.power(mask, 0.7)
    
    return (mask * 255).astype(np.uint8)
