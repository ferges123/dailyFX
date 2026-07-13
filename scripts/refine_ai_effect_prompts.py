#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


SEED_DIR = Path(__file__).resolve().parents[1] / "backend/app/services/generation/ai_effects_data"

RENDERING_CONTRACT = (
    "Rendering contract: Use the input image as visual ground truth. Keep the exact number of subjects and "
    "their left-to-right order, relative scale, pose, gaze, interaction, and key props. For every visible person, "
    "retain recognizable face geometry, age range, skin tone, hairstyle, and distinguishing features in a "
    "style-appropriate form; do not beautify, age, or swap identity unless explicitly requested. Preserve the "
    "source aspect ratio, camera viewpoint, and all important content inside the frame unless this effect explicitly "
    "calls for a different layout. Apply the transformation consistently to the subjects, clothing, props, and "
    "environment. Return one coherent finished image, not a before-and-after comparison, split screen, or unintended "
    "collage; use multiple frames or a decorative border only when this effect explicitly requests them. Include no "
    "readable text, letters, numerals, logos, signatures, watermarks, or interface elements unless explicitly requested."
)

NEGATIVE_CONTRACT = (
    "identity drift, face swap, altered age, altered skin tone, wrong subject count, extra people, missing people, "
    "duplicated subject, merged subjects, inconsistent transformation, partial transformation, before-and-after, "
    "split screen, unintended collage, accidental crop, cut-off face, malformed anatomy, broken hands, fused fingers, "
    "extra fingers, extra limbs, incoherent perspective, floating objects, random text, gibberish letters, numerals, "
    "logo, watermark, signature, interface elements"
)


def merge_negative_prompt(existing: str) -> str:
    values: list[str] = []
    seen: set[str] = set()
    for value in f"{existing}, {NEGATIVE_CONTRACT}".split(","):
        cleaned = value.strip()
        normalized = cleaned.casefold()
        if cleaned and normalized not in seen:
            values.append(cleaned)
            seen.add(normalized)
    return ", ".join(values)


def main() -> None:
    for path in sorted(SEED_DIR.glob("ai_*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        positive_prompt = payload["positive_prompt"].strip()
        if RENDERING_CONTRACT not in positive_prompt:
            payload["positive_prompt"] = f"{positive_prompt} {RENDERING_CONTRACT}"
        payload["negative_prompt"] = merge_negative_prompt(payload.get("negative_prompt") or "")
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
