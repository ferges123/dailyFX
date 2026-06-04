import random

from app.immich.models import ImmichExifInfo
from app.models.settings import SettingsModel
from app.services.generation.ai_image import AIImageError, generate_ai_image
from app.services.generation.modules.ai_common import get_image_bytes
from app.services.generation.modules.base import GenerationResult
from app.services.generation.people_context import load_people_context
from app.utils.debug_logger import debug_log


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

    def _album_name_for_settings(self, settings: SettingsModel) -> str | None:
        album_name = getattr(settings, "_generation_album_name", None)
        if isinstance(album_name, str):
            cleaned = album_name.strip()
            return cleaned or None
        return None

    @staticmethod
    def _format_exif_context(exif_info: ImmichExifInfo | None) -> str | None:
        if not exif_info:
            return None

        parts: list[str] = []
        make = (exif_info.get("make") or "").strip()
        model = (exif_info.get("model") or "").strip()
        lens = (exif_info.get("lensModel") or "").strip()
        if make or model:
            camera = " ".join(part for part in [make, model] if part)
            parts.append(f"Camera: {camera}")
        if lens:
            parts.append(f"Lens: {lens}")

        exposure = []
        f_number = exif_info.get("fNumber")
        if f_number not in (None, ""):
            exposure.append(f"f/{f_number}")
        exposure_time = exif_info.get("exposureTime")
        if exposure_time not in (None, ""):
            exposure.append(str(exposure_time))
        iso = exif_info.get("iso")
        if iso not in (None, ""):
            exposure.append(f"ISO {iso}")
        focal_length = exif_info.get("focalLength")
        if focal_length not in (None, ""):
            exposure.append(f"{focal_length}mm")
        if exposure:
            parts.append(f"Exposure: {', '.join(exposure)}")

        taken = (exif_info.get("dateTimeOriginal") or "").strip()
        if taken:
            parts.append(f"Taken: {taken}")

        latitude = exif_info.get("latitude")
        longitude = exif_info.get("longitude")
        if latitude not in (None, "") and longitude not in (None, ""):
            parts.append(f"Location: {latitude}, {longitude}")

        return "; ".join(parts) or None

    def _build_prompt_context_hint(
        self,
        *,
        album_name: str | None,
        people_context,
        exif_info: ImmichExifInfo | None,
    ) -> dict[str, str | list[str]] | None:
        parts: list[str] = []
        people_names: list[str] = []
        if album_name:
            parts.append(f"Album: {album_name}")
        if people_context:
            if getattr(people_context, "names", None):
                people_names = [name for name in people_context.names if isinstance(name, str) and name.strip()]
                names = ", ".join(people_names)
                if names:
                    parts.append(f"Detected people: {names}")
            if getattr(people_context, "prompt_hint", ""):
                parts.append(people_context.prompt_hint)
        exif_hint = self._format_exif_context(exif_info)
        if exif_hint:
            parts.append(f"EXIF: {exif_hint}")
        context_hint = "\n".join(parts).strip()
        if not context_hint:
            return None
        return {
            "album_name": album_name or "",
            "people_names": people_names,
            "people_prompt_hint": getattr(people_context, "prompt_hint", "") if people_context else "",
            "exif_summary": exif_hint or "",
            "context_hint": context_hint,
        }

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
            album_name = self._album_name_for_settings(settings)
            enrichment_context_hint = None
            enrichment_context = None
            if getattr(settings, "ai_prompt_enrichment", False) is True:
                try:
                    exif_info = await client.get_asset_exif(asset.id)
                except Exception:
                    exif_info = None
                enrichment_context = self._build_prompt_context_hint(
                    album_name=album_name,
                    people_context=people_context,
                    exif_info=exif_info,
                )
                if enrichment_context:
                    enrichment_context_hint = enrichment_context["context_hint"]
                    debug_log(
                        "AI prompt enrichment context assembled",
                        album_name=enrichment_context["album_name"],
                        people_names=enrichment_context["people_names"],
                        exif_summary=enrichment_context["exif_summary"],
                        context_hint=enrichment_context_hint,
                    )
            try:
                result = await generate_ai_image(
                    settings,
                    image_bytes,
                    prompt,
                    negative_prompt=self.default_negative_prompt,
                    context_hint=people_context.prompt_hint if people_context else None,
                    prompt_enrichment_context_hint=enrichment_context_hint,
                )
            except AIImageError as exc:
                raise RuntimeError(f"{self.label} generation failed: {exc}") from exc

            result_config = {}
            if people_context:
                result_config["people_context"] = people_context.to_dict()
            if enrichment_context:
                result_config["prompt_enrichment_context"] = enrichment_context

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
