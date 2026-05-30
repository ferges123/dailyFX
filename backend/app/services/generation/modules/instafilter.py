import random

from app.models.settings import SettingsModel
from app.services.generation.instafilter import AVAILABLE_FILTER_OPTIONS, apply_instafilter
from app.services.generation.modules.base import GenerationResult


class InstafilterModule:
    name = "instafilter"
    label = "Instafilter"
    description = "Single-photo Instagram-style filter."
    default_weight = 2
    default_config = {"styles": ["random"]}
    config_schema = [
        {
            "key": "styles",
            "label": "Allowed filters",
            "type": "multiselect",
            "description": "Choose the filters that can be picked at run time.",
            "options": AVAILABLE_FILTER_OPTIONS,
            "default": ["random"],
        },
    ]

    async def run(self, page_items: list, config: dict, client, settings: SettingsModel) -> GenerationResult:
        asset = random.choice(page_items)
        image_bytes = await client.get_asset_data(asset.id)

        styles = config.get("styles", ["random"])
        style = random.choice(styles)
        filtered_bytes, style = apply_instafilter(image_bytes, filter_name=style)

        return GenerationResult(
            title=f"Instafilter: {style}",
            summary=f"Applied {style} filter to an image.",
            image_bytes=filtered_bytes,
            generation_type="instafilter",
            provider="local",
            model="pilgram",
            config={"style": style},
            source_asset_ids=[asset.id],
        )
