from app.services.generation.modules.ai_style_base import AIStyleBaseModule


class AIBrickBuiltFigureModule(AIStyleBaseModule):
    name = "ai_brick_built_figure"
    label = "AI Brick-Built Figure"
    description = "Uses the default AI provider to turn a photo into a playful brick-built character scene."
    default_weight = 1
    default_config = {}
    default_prompt = (
        "Transform the input photo into a playful LEGO-style brick-built scene. "
        "Preserve the number of people, recognizable identity, key facial features, "
        "pose, camera angle, framing, main composition, outfit colors, and scene context. "
        "Recreate each subject as a LEGO-style minifigure or brick-built character with blocky toy "
        "proportions, glossy plastic surfaces, visible brick seams, bright colors, and a polished toy-photography look."
    )
    default_negative_prompt = (
        "text, captions, logos, watermarks, signatures, extra people, changed identity, "
        "distorted faces, malformed hands, extra fingers, missing fingers, duplicate limbs, "
        "duplicate face, unrelated objects, low quality, blurry, uncanny, over-smoothed skin"
    )
