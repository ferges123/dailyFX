from app.services.generation.modules.ai_style_base import AIStyleBaseModule


class AIAnimeModule(AIStyleBaseModule):
    name = "ai_anime"
    label = "AI Anime"
    description = "Uses the default AI provider to turn a photo into anime-style art."
    default_weight = 1
    default_config = {}
    custom_prompt_placeholder = "e.g. Studio Ghibli style, soft watercolor..."
    default_prompt = (
        "Transform the input photo into a polished anime illustration. "
        "Preserve the number of people, recognizable identity, key facial features, "
        "pose, camera angle, framing, main composition, outfit colors, and scene context. "
        "Use clean linework, expressive stylized eyes, cel shading, refined details, "
        "soft cinematic lighting, and a polished anime look."
    )
    default_negative_prompt = (
        "text, captions, logos, watermarks, signatures, extra people, changed identity, "
        "distorted faces, malformed hands, extra fingers, missing fingers, duplicate limbs, "
        "duplicate face, unrelated objects, low quality, blurry, uncanny, over-smoothed skin"
    )
