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


def test_album_page_response_schema():
    from app.schemas.immich import ImmichAlbumPageResponse
    from app.immich.models import ImmichAlbumSummary

    data = {
        "items": [
            ImmichAlbumSummary(
                id="album-1",
                album_name="Trips",
                asset_count=8,
                thumbnail_asset_id="asset-1",
            )
        ],
        "total": 1,
        "count": 1,
        "pages": 1,
        "current_page": 1,
    }
    response = ImmichAlbumPageResponse.model_validate(data)
    assert response.total == 1
    assert response.pages == 1
    assert response.current_page == 1


def test_immich_albums_endpoint(monkeypatch):
    from app.api.routes_immich import list_albums
    from app.schemas.immich import ImmichAlbumPageResponse

    monkeypatch.setattr("app.api.routes_immich._get_or_create_settings", lambda db: FakeSettingsRow())

    class TestAlbum:
        def __init__(self, id: str, name: str):
            self.id = id
            self.album_name = name
            self.asset_count = 8
            self.thumbnail_asset_id = "asset-1"

    class MockClient:
        async def list_albums(self):
            return [
                TestAlbum(id="album-1", name="Trips"),
                TestAlbum(id="album-2", name="Animals"),
                TestAlbum(id="album-3", name="Family"),
            ]

    monkeypatch.setattr("app.api.routes_immich._build_immich_client", lambda row: MockClient())

    # We call list_albums with db=None, page=1, size=2
    response = asyncio.run(list_albums(page=1, size=2, db=None))

    assert isinstance(response, ImmichAlbumPageResponse)
    # Total albums is 3, but count is 2 (page size is 2), sorted alphabetically: Animals, Family, Trips
    # So page 1 should contain Animals and Family.
    assert response.total == 3
    assert response.count == 2
    assert response.pages == 2
    assert response.current_page == 1
    assert response.items[0].album_name == "Animals"
    assert response.items[1].album_name == "Family"

    # Test page 2
    response_p2 = asyncio.run(list_albums(page=2, size=2, db=None))
    assert response_p2.total == 3
    assert response_p2.count == 1
    assert response_p2.items[0].album_name == "Trips"



