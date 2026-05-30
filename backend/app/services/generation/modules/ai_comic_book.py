from app.services.generation.modules.ai_style_base import AIStyleBaseModule


class AIComicBookModule(AIStyleBaseModule):
    name = "ai_comic_book"
    label = "AI Comic Book"
    description = "Uses the default AI provider to turn a photo into a retro comic book illustration."
    default_weight = 1
    default_config = {}
    custom_prompt_placeholder = "e.g. Vintage pulp fiction style, bold ink..."
    default_prompt = (
        "Transform the input photo into a classic 1960s American comic book illustration. "
        "Preserve the number of people, recognizable identity, key facial features, "
        "pose, camera angle, framing, main composition, outfit colors, and scene context. "
        "Use thick black ink outlines, bold colors, dramatic comic shading, "
        "subtle Ben-Day halftone dot patterns, dynamic contrast, and vintage printed-comic texture."
    )
    default_negative_prompt = (
        "text, captions, logos, watermarks, signatures, dialog bubbles, speech bubbles, "
        "comic captions, text boxes, extra people, changed identity, distorted faces, "
        "malformed hands, extra fingers, missing fingers, duplicate limbs, duplicate face, "
        "unrelated objects, low quality, blurry, uncanny, over-smoothed skin"
    )
