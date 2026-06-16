# OpenAI DALL-E Smart Crop Design Document

## Goal
Implement smart cropping for OpenAI (and Local AI) image generation flows. Because OpenAI's image edits API strictly requires square (`1:1`) images, sending vertical or horizontal photos causes errors or stretching. This design crops the input image to a square centered around the largest detected face (or falls back to center-cropping) before sending it to OpenAI.

## Proposed Architecture
- Introduce a helper function `_crop_to_largest_face(image_bytes: bytes, faces: list[dict] | None) -> bytes` in `backend/app/services/generation/ai_image.py`.
- If `faces` are provided, compute the center of the face with the largest bounding box area, and crop the image to a square centered on that point, clamping to the image boundaries.
- If no faces are provided, perform a center crop.
- Update `generate_ai_image()` to accept a `faces` parameter and apply the crop pre-processing when the provider is `openai` or `local`.
- Update `AIStyleBaseModule.run()` to pass detected faces from `people_context` to `generate_ai_image()`.

## Data Flow Diagram
```
[Input Asset]
      │
      ├─► Load people_context (Immich Faces)
      │
      ▼
[generate_ai_image]
      │
      ├─► If provider is "openai" or "local":
      │     └─► _crop_to_largest_face(image_bytes, faces)
      │           ├─► Find largest face bounding box
      │           ├─► Center crop square on that face
      │           └─► Output square image bytes
      │
      ▼
[encode_image_for_provider] (already resized to 1024x1024)
      │
      ▼
[OpenAI API Call]
```
