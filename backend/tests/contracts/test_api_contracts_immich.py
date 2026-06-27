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
                "created_at": None,
                "last_modified_asset_timestamp": None,
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
    from app.immich.models import ImmichAlbumSummary
    from app.schemas.immich import ImmichAlbumPageResponse

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
        def __init__(self, id: str, name: str, count: int, created_at: str, modified: str):
            self.id = id
            self.album_name = name
            self.asset_count = count
            self.thumbnail_asset_id = "asset-1"
            self.created_at = created_at
            self.last_modified_asset_timestamp = modified

    class MockClient:
        async def list_albums(self):
            return [
                TestAlbum(
                    id="album-1",
                    name="Trips",
                    count=10,
                    created_at="2026-06-01T12:00:00Z",
                    modified="2026-06-25T12:00:00Z",
                ),
                TestAlbum(
                    id="album-2",
                    name="Animals",
                    count=5,
                    created_at="2026-06-10T12:00:00Z",
                    modified="2026-06-20T12:00:00Z",
                ),
                TestAlbum(
                    id="album-3",
                    name="Family",
                    count=20,
                    created_at="2026-05-20T12:00:00Z",
                    modified="2026-06-26T12:00:00Z",
                ),
            ]

    monkeypatch.setattr("app.api.routes_immich._build_immich_client", lambda row: MockClient())

    # We call list_albums with db=None, page=1, size=2, sort_by="name"
    response = asyncio.run(list_albums(page=1, size=2, sort_by="name", sort_order="asc", db=None))

    assert isinstance(response, ImmichAlbumPageResponse)
    assert response.total == 3
    assert response.count == 2
    assert response.pages == 2
    assert response.current_page == 1
    # Sorted: Animals, Family, Trips
    assert response.items[0].album_name == "Animals"
    assert response.items[1].album_name == "Family"

    # Test count desc
    response_count = asyncio.run(list_albums(page=1, size=3, sort_by="count", sort_order="desc", db=None))
    # Sorted by count desc: Family (20), Trips (10), Animals (5)
    assert response_count.items[0].album_name == "Family"
    assert response_count.items[1].album_name == "Trips"
    assert response_count.items[2].album_name == "Animals"

    # Test created desc
    response_created = asyncio.run(list_albums(page=1, size=3, sort_by="created", sort_order="desc", db=None))
    # Sorted by created desc: Animals (06-10), Trips (06-01), Family (05-20)
    assert response_created.items[0].album_name == "Animals"
    assert response_created.items[1].album_name == "Trips"
    assert response_created.items[2].album_name == "Family"

    # Test modified desc
    response_modified = asyncio.run(list_albums(page=1, size=3, sort_by="modified", sort_order="desc", db=None))
    # Sorted by modified desc: Family (06-26), Trips (06-25), Animals (06-20)
    assert response_modified.items[0].album_name == "Family"
    assert response_modified.items[1].album_name == "Trips"
    assert response_modified.items[2].album_name == "Animals"
