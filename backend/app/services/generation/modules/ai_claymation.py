from app.services.generation.modules.ai_style_base import AIStyleBaseModule


class AIClaymationModule(AIStyleBaseModule):
    name = "ai_claymation"
    label = "AI Claymation"
    description = "Uses the default AI provider to turn a photo into plasticine stop-motion clay art."
    default_weight = 1
    default_config = {}
    custom_prompt_placeholder = "e.g. Aardman style claymation, colorful plasticine..."
    default_prompt = (
        "Transform the input photo into a claymation stop-motion scene. "
        "Preserve the number of people, recognizable identity, key facial features, "
        "pose, camera angle, framing, main composition, outfit colors, and scene context. "
        "Recreate the people and environment as plasticine clay figures with soft clay texture, "
        "subtle thumbprints, handmade surface imperfections, gentle clay wrinkles, and studio stop-motion lighting."
    )
    default_negative_prompt = (
        "text, captions, logos, watermarks, signatures, extra people, changed identity, "
        "distorted faces, malformed hands, extra fingers, missing fingers, duplicate limbs, "
        "duplicate face, unrelated objects, low quality, blurry, uncanny, over-smoothed skin"
    )
