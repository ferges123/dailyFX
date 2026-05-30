from app.services.generation.modules.ai_style_base import AIStyleBaseModule


class AICinematic3DToyModule(AIStyleBaseModule):
    name = "ai_cinematic_3d_toy"
    label = "AI Cinematic 3D Toy"
    description = "Uses the default AI provider to turn a photo into a polished cinematic 3D toy-style portrait."
    default_weight = 1
    default_config = {}
    default_prompt = (
        "Transform the input photo into a polished Pixar-style 3D animated portrait. "
        "Preserve the number of people, recognizable identity, key facial features, "
        "pose, camera angle, framing, main composition, outfit colors, and scene context. "
        "Use stylized toy-like proportions, expressive eyes, smooth materials, soft studio lighting, "
        "premium family-film rendering, and a clean high-end animated 3D finish similar to Pixar."
    )
    default_negative_prompt = (
        "text, captions, logos, watermarks, signatures, extra people, changed identity, "
        "distorted faces, malformed hands, extra fingers, missing fingers, duplicate limbs, "
        "duplicate face, unrelated objects, low quality, blurry, uncanny, over-smoothed skin"
    )
