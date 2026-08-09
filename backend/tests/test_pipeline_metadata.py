import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.generation.pipeline.metadata import _resolve_generation_source_context


@patch("app.services.generation.pipeline.metadata.load_people_context", new_callable=AsyncMock)
def test_source_context_uses_selected_asset_when_it_is_not_on_last_search_page(mock_people_context):
    selected_asset = MagicMock()
    selected_asset.id = "selected-on-first-page"
    selected_asset.original_file_name = "original.jpg"
    selected_asset.created_at = "2026-05-12T10:00:00Z"
    selected_asset.people = []
    result = MagicMock(source_asset_ids=["selected-on-first-page"])

    source_asset, people_context = asyncio.run(
        _resolve_generation_source_context(
            selected_assets=[selected_asset],
            result=result,
            client=MagicMock(),
            task_id="metadata-selected-source",
        )
    )

    assert source_asset is selected_asset
    assert people_context is mock_people_context.return_value
    mock_people_context.assert_awaited_once()
