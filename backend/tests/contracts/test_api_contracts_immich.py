import asyncio

from _contract_helpers import (
    FakeAlbum,
    FakeImmichClient,
    FakePerson,
    FakeRequest,
    FakeSettingsRow,
    configure_contract_test_db,
)

from app.api.routes_immich import list_assets, list_filter_options
from app.schemas.immich import ImmichAssetPageResponse, ImmichFilterOptionsResponse

configure_contract_test_db("api_contracts_immich")


def test_immich_options_contract(monkeypatch):
    monkeypatch.setattr("app.api.routes_immich._get_or_create_settings", lambda db: FakeSettingsRow())
    monkeypatch.setattr(
        "app.api.routes_immich._list_filter_options",
        lambda row: asyncio.sleep(0, result=([FakeAlbum()], [FakePerson()])),
    )

    response = asyncio.run(list_filter_options(db=None))

    assert isinstance(response, ImmichFilterOptionsResponse)
    assert response.model_dump(mode="json") == {
        "albums": [
            {
                "id": "album-1",
                "album_name": "Trips",
                "asset_count": 8,
                "thumbnail_asset_id": "asset-1",
            }
        ],
        "people": [
            {
                "id": "person-1",
                "name": "Alice",
                "is_hidden": False,
                "asset_count": 12,
            }
        ],
    }


def test_immich_assets_contract(monkeypatch):
    fake_client = FakeImmichClient()
    monkeypatch.setattr("app.api.routes_immich._get_or_create_settings", lambda db: FakeSettingsRow())
    monkeypatch.setattr("app.api.routes_immich._build_immich_client", lambda row: fake_client)

    response = asyncio.run(
        list_assets(
            request=FakeRequest(
                "media_type=video&album_ids=album-1&person_ids=person-1&person_modes=obligatory&"
                "person_ids=person-2&person_modes=exclude&start_date=2026-05-01&end_date=2026-05-31"
            ),
            db=None,
        )
    )

    assert isinstance(response, ImmichAssetPageResponse)
    assert response.model_dump(mode="json") == {
        "items": [
            {
                "id": "asset-1",
                "original_file_name": "photo.jpg",
                "created_at": "2026-05-12T10:00:00Z",
                "updated_at": None,
                "mime_type": "image/jpeg",
                "asset_type": "IMAGE",
                "people": [
                    {
                        "id": "person-1",
                        "name": "Alice",
                        "is_hidden": False,
                        "asset_count": 12,
                    }
                ],
            }
        ],
        "total": 1,
        "count": 1,
        "next_page": None,
    }
