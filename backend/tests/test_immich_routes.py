import asyncio

from _contract_helpers import (
    FakeAlbum,
    FakeImmichClient,
    FakePerson,
    FakeRequest,
    FakeSettingsRow,
    configure_contract_test_db,
)

from app.api.routes_immich import get_asset_exif, get_asset_thumbnail, list_assets, list_filter_options

configure_contract_test_db("immich_routes")


class ExtendedFakeImmichClient(FakeImmichClient):
    async def get_asset_thumbnail(self, asset_id: str, size: str = "preview"):
        return b"thumb-bytes", "image/webp"

    async def get_asset_exif(self, asset_id: str):
        return {
            "make": "Canon",
            "model": "EOS R5",
            "lensModel": "RF 24-70mm F2.8",
            "fNumber": 2.8,
            "exposureTime": 0.004,
            "focalLength": 50.0,
            "iso": 400,
            "latitude": 52.2297,
            "longitude": 21.0122,
            "dateTimeOriginal": "2026-05-12T10:00:00Z",
        }


def test_list_assets_forwards_filters(monkeypatch):
    fake_client = ExtendedFakeImmichClient()
    monkeypatch.setattr("app.api.routes_immich._get_or_create_settings", lambda db: FakeSettingsRow())
    monkeypatch.setattr("app.api.routes_immich._build_immich_client", lambda row: fake_client)

    response = asyncio.run(
        list_assets(
            request=FakeRequest(
                "page=2&size=15&media_type=video&album_ids=album-1&person_ids=person-1&person_modes=obligatory&"
                "person_ids=person-2&person_modes=exclude&start_date=2026-05-01&end_date=2026-05-31"
            ),
            db=None,
        )
    )

    payload = response.model_dump(mode="json")
    assert payload["count"] == 1
    assert payload["items"][0]["id"] == "asset-1"
    assert fake_client.page == 2
    assert fake_client.size == 15
    assert fake_client.filters.media_type == "video"
    assert fake_client.filters.album_ids == ["album-1"]
    assert [item.person_id for item in fake_client.filters.person_filters] == ["person-1", "person-2"]
    assert [item.mode for item in fake_client.filters.person_filters] == ["obligatory", "exclude"]
    assert str(fake_client.filters.taken_after) == "2026-05-01"
    assert str(fake_client.filters.taken_before) == "2026-05-31"


def test_list_filter_options_returns_albums_and_people(monkeypatch):
    monkeypatch.setattr("app.api.routes_immich._get_or_create_settings", lambda db: FakeSettingsRow())
    monkeypatch.setattr(
        "app.api.routes_immich._list_filter_options",
        lambda row: asyncio.sleep(0, result=([FakeAlbum()], [FakePerson()])),
    )

    response = asyncio.run(list_filter_options(db=None))

    assert len(response.albums) == 1
    assert response.albums[0].album_name == "Trips"
    assert len(response.people) == 1
    assert response.people[0].name == "Alice"
    assert response.people[0].asset_count == 12


def test_thumbnail_proxy_returns_bytes(monkeypatch):
    from app.services.immich_thumbnail_cache import CachedThumbnail

    monkeypatch.setattr("app.api.routes_immich._get_or_create_settings", lambda db: FakeSettingsRow())

    async def mock_get_cached_immich_thumbnail(settings, asset_id, size):
        return CachedThumbnail(
            path=None,
            content=b"thumb-bytes",
            content_type="image/webp",
            etag='"mock-etag"',
            cache_hit=False,
        )

    monkeypatch.setattr(
        "app.api.routes_immich.get_cached_immich_thumbnail",
        mock_get_cached_immich_thumbnail,
    )

    response = asyncio.run(get_asset_thumbnail("asset-1", db=None))

    assert response.body == b"thumb-bytes"
    assert response.media_type == "image/webp"
    assert response.headers["ETag"] == '"mock-etag"'
    assert response.headers["Cache-Control"] == "private, max-age=86400, stale-while-revalidate=604800"


def test_get_asset_exif_returns_typed_payload(monkeypatch):
    fake_client = ExtendedFakeImmichClient()
    monkeypatch.setattr("app.api.routes_immich._get_or_create_settings", lambda db: FakeSettingsRow())
    monkeypatch.setattr("app.api.routes_immich._build_immich_client", lambda row: fake_client)

    response = asyncio.run(get_asset_exif("asset-1", db=None))

    payload = response.model_dump(mode="json")
    assert payload["make"] == "Canon"
    assert payload["model"] == "EOS R5"
    assert payload["lensModel"] == "RF 24-70mm F2.8"
    assert payload["iso"] == 400
    assert payload["dateTimeOriginal"] == "2026-05-12T10:00:00Z"


def test_thumbnail_proxy_returns_304_on_etag_match(monkeypatch):
    from app.services.immich_thumbnail_cache import CachedThumbnail

    monkeypatch.setattr("app.api.routes_immich._get_or_create_settings", lambda db: FakeSettingsRow())

    async def mock_get_cached_immich_thumbnail(settings, asset_id, size):
        return CachedThumbnail(
            path=None,
            content=b"thumb-bytes",
            content_type="image/webp",
            etag='"mock-etag"',
            cache_hit=True,
        )

    monkeypatch.setattr(
        "app.api.routes_immich.get_cached_immich_thumbnail",
        mock_get_cached_immich_thumbnail,
    )

    fake_request = FakeRequest()
    fake_request.headers = {"if-none-match": '"mock-etag"'}

    response = asyncio.run(get_asset_thumbnail("asset-1", request=fake_request, db=None))

    assert response.status_code == 304
    assert response.body == b""
    assert response.headers["ETag"] == '"mock-etag"'


def test_thumbnail_proxy_validates_asset_id_format(monkeypatch):
    import pytest
    from fastapi import HTTPException

    monkeypatch.setattr("app.api.routes_immich._get_or_create_settings", lambda db: FakeSettingsRow())

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(get_asset_thumbnail("../invalid-id", db=None))

    assert exc_info.value.status_code == 400
    assert "Invalid asset_id format" in exc_info.value.detail
