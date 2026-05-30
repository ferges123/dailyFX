from app.services.generation.modules.ai_style_base import AIStyleBaseModule


class AICyberpunkModule(AIStyleBaseModule):
    name = "ai_cyberpunk"
    label = "AI Cyberpunk"
    description = "Uses the default AI provider to turn a photo into a neon-soaked cyberpunk artwork."
    default_weight = 1
    default_config = {}
    custom_prompt_placeholder = "e.g. Dark gritty neon, rain-soaked streets..."
    default_prompt = (
        "Transform the input photo into a vibrant cyberpunk sci-fi scene. "
        "Preserve the number of people, recognizable identity, key facial features, "
        "pose, camera angle, framing, main composition, outfit colors, and scene context. "
        "Reimagine the original environment with neon pink, cyan, and purple lighting, "
        "futuristic details, subtle cybernetic accents, metallic reflections, high-tech accessories, "
        "wet reflective surfaces where appropriate, and a moody cinematic atmosphere."
    )
    default_negative_prompt = (
        "text, captions, logos, watermarks, signatures, extra people, changed identity, "
        "distorted faces, malformed hands, extra fingers, missing fingers, duplicate limbs, "
        "duplicate face, unrelated objects, low quality, blurry, uncanny, over-smoothed skin"
    )
