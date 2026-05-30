from app.services.generation.modules.ai_style_base import AIStyleBaseModule


class AICollectibleFigureModule(AIStyleBaseModule):
    name = "ai_collectible_figure"
    label = "AI Collectible Hero Figure"
    description = "Uses the default AI provider to turn a photo into a premium collectible hero figure portrait."
    default_weight = 1
    default_config = {}
    default_prompt = (
        "Transform the input photo into a premium collectible hero figure scene. "
        "Preserve the number of people, recognizable identity, key facial features, "
        "pose, camera angle, framing, main composition, outfit colors, and scene context. "
        "Use articulated figure details, molded plastic textures, heroic display-stand posing, "
        "dramatic studio lighting, premium toy photography, and a polished boxed-collectible presentation."
    )
    default_negative_prompt = (
        "text, captions, logos, watermarks, signatures, extra people, changed identity, "
        "distorted faces, malformed hands, extra fingers, missing fingers, duplicate limbs, "
        "duplicate face, unrelated objects, low quality, blurry, uncanny, over-smoothed skin"
    )
