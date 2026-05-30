from app.services.generation.modules.ai_style_base import AIStyleBaseModule


class AIFantasyHeroModule(AIStyleBaseModule):
    name = "ai_fantasy_hero"
    label = "AI Fantasy Hero"
    description = "Uses the default AI provider to turn a photo into an epic fantasy portrait."
    default_weight = 1
    default_config = {}
    default_prompt = (
        "Transform the input photo into an epic fantasy hero portrait. "
        "Preserve the number of people, recognizable identity, key facial features, "
        "pose, camera angle, framing, main composition, outfit colors, and scene context. "
        "Add dramatic armor or robes, cinematic lighting, mythic atmosphere, subtle magical energy, "
        "rich painterly detail, heroic styling, and an elegant fantasy-art finish."
    )
    default_negative_prompt = (
        "text, captions, logos, watermarks, signatures, extra people, changed identity, "
        "distorted faces, malformed hands, extra fingers, missing fingers, duplicate limbs, "
        "duplicate face, unrelated objects, low quality, blurry, uncanny, over-smoothed skin"
    )
