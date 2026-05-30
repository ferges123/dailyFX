from app.services.generation.modules.ai_style_base import AIStyleBaseModule


class AIYellowCartoonSitcomModule(AIStyleBaseModule):
    name = "ai_yellow_cartoon_sitcom"
    label = "AI Yellow Cartoon Sitcom"
    description = "Uses the default AI provider to turn a photo into a bright cartoon family-comedy portrait."
    default_weight = 1
    default_config = {}
    default_prompt = (
        "Transform the input photo into a bright animated sitcom portrait in a visual style similar to The Simpsons. "
        "Preserve the number of people, recognizable identity, key facial characteristics, "
        "pose, camera angle, framing, main composition, outfit colors, and scene context. "
        "Use yellow skin, bold outlines, flat cel-style coloring, simplified cartoon shapes, "
        "expressive faces, playful suburban comedy energy, and a clean TV-animation look similar to The Simpsons."
    )
    default_negative_prompt = (
        "text, captions, logos, watermarks, signatures, extra people, changed identity, "
        "distorted faces, malformed hands, extra fingers, missing fingers, duplicate limbs, "
        "duplicate face, unrelated objects, low quality, blurry, uncanny, over-smoothed skin"
    )
