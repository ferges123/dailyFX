from __future__ import annotations

from app.models.ai_effect import AIEffectModel
from app.services.generation.modules.ai_style_base import AIStyleBaseModule


class AIEffectModule(AIStyleBaseModule):
    def __init__(self, row: AIEffectModel):
        self.name = row.id
        self.label = row.title
        self.description = row.description or row.title
        self.default_weight = 1
        self.default_config = {}
        self.custom_prompt_placeholder = row.custom_prompt_placeholder or "e.g. polished portrait, studio lighting..."
        self.default_prompt = row.positive_prompt
        self.default_negative_prompt = row.negative_prompt
        self.enabled = row.enabled
        self.source = row.source
        self.show_example = row.source == "builtin" and row.enabled
        self.config_schema = [
            {
                "key": "custom_prompt",
                "label": "Custom prompt",
                "type": "text",
                "description": "Override the default prompt. Leave empty to use default.",
                "placeholder": self.custom_prompt_placeholder,
                "default": "",
            },
        ]


def build_ai_module(row: AIEffectModel) -> AIEffectModule:
    return AIEffectModule(row)
