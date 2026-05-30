from app.services.generation.modules.ai_style_base import AIStyleBaseModule


class AIHighFashionEditorialModule(AIStyleBaseModule):
    name = "ai_high_fashion_editorial"
    label = "AI High-Fashion Editorial"
    description = "Uses the default AI provider to turn a photo into a luxury editorial portrait."
    default_weight = 1
    default_config = {}
    default_prompt = (
        "Transform the input photo into a high-fashion editorial portrait. "
        "Preserve the number of people, recognizable identity, key facial features, "
        "pose, camera angle, framing, main composition, outfit colors, and scene context. "
        "Apply avant-garde styling, luxury magazine lighting, refined textures, clean studio composition, "
        "bold runway-inspired mood, elegant posing, and a polished editorial finish."
    )
    default_negative_prompt = (
        "text, captions, logos, watermarks, signatures, extra people, changed identity, "
        "distorted faces, malformed hands, extra fingers, missing fingers, duplicate limbs, "
        "duplicate face, unrelated objects, low quality, blurry, uncanny, over-smoothed skin"
    )
