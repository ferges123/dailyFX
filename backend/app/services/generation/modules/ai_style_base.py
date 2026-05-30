import random

from app.models.settings import SettingsModel
from app.services.generation.ai_image import AIImageError, generate_ai_image
from app.services.generation.modules.ai_common import get_image_bytes
from app.services.generation.modules.base import GenerationResult
from app.services.generation.people_context import load_people_context


class AIStyleBaseModule:
    name = ""
    label = ""
    description = ""
    default_weight = 1
    default_config = {}
    default_prompt = ""
    default_negative_prompt: str | None = None
    custom_prompt_label = "Custom prompt"
    custom_prompt_description = "Override the default prompt. Leave empty to use default."
    custom_prompt_placeholder = "e.g. polished portrait, studio lighting..."

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.config_schema = [
            {
                "key": "custom_prompt",
                "label": getattr(cls, "custom_prompt_label", "Custom prompt"),
                "type": "text",
                "description": getattr(
                    cls,
                    "custom_prompt_description",
                    "Override the default prompt. Leave empty to use default.",
                ),
                "placeholder": getattr(cls, "custom_prompt_placeholder", "e.g. polished portrait, studio lighting..."),
                "default": "",
            },
        ]

    def _style_name(self) -> str:
        return self.label[3:] if self.label.startswith("AI ") else self.label

    def _prompt_for_config(self, config: dict, settings: SettingsModel) -> str:
        return (config.get("custom_prompt") or "").strip() or (settings.ai_custom_prompt or "").strip() or self.default_prompt

    def _summary_for_result(self, provider: str) -> str:
        style_name = self._style_name().lower()
        return f"Reimagined the photo as {style_name} with {provider}."

    async def run(self, page_items: list, config: dict, client, settings: SettingsModel) -> GenerationResult:
        candidates = list(page_items)
        random.shuffle(candidates)
        last_exc: Exception | None = None
        for asset in candidates:
            try:
                image_bytes = await get_image_bytes(client, asset)
            except Exception as exc:
                last_exc = exc
                continue

            prompt = self._prompt_for_config(config, settings)
            people_context = await load_people_context(client, asset)
            try:
                result = await generate_ai_image(
                    settings,
                    image_bytes,
                    prompt,
                    negative_prompt=self.default_negative_prompt,
                    context_hint=people_context.prompt_hint if people_context else None,
                )
            except AIImageError as exc:
                raise RuntimeError(f"{self.label} generation failed: {exc}") from exc

            result_config = {}
            if people_context:
                result_config["people_context"] = people_context.to_dict()

            return GenerationResult(
                title=f"{self.label}: {asset.original_file_name or asset.id}",
                summary=self._summary_for_result(result.provider),
                image_bytes=result.image_bytes,
                generation_type=self.name,
                provider=result.provider,
                model=result.model,
                config=result_config,
                source_asset_ids=[asset.id],
            )

        raise RuntimeError(f"No accessible asset found for {self.label}: {last_exc}")
