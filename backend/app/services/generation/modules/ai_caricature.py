from app.services.generation.modules.ai_style_base import AIStyleBaseModule


class AICaricatureModule(AIStyleBaseModule):
    name = "ai_caricature"
    label = "AI Caricature"
    description = "Uses the default AI provider to turn a photo into a caricature."
    default_weight = 1
    default_config = {}
    custom_prompt_placeholder = "e.g. Pixar style, bold colors..."
    default_prompt = (
        "Transform the input photo into a playful caricature illustration. "
        "Preserve the number of people, recognizable identity, key facial characteristics, "
        "pose, camera angle, framing, main composition, outfit colors, and scene context. "
        "Exaggerate distinctive facial features, expressions, head shape, and body proportions "
        "in a fun, friendly illustrative style while keeping every subject clearly identifiable."
    )
    default_negative_prompt = (
        "text, captions, logos, watermarks, signatures, extra people, changed identity, "
        "offensive distortion, grotesque distortion, insulting exaggeration, malformed hands, "
        "extra fingers, missing fingers, duplicate limbs, duplicate face, unrelated objects, "
        "low quality, blurry, uncanny, over-smoothed skin"
    )
