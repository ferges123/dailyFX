import asyncio
import json
from datetime import date
from io import BytesIO

import httpx
import pytest
from PIL import Image

from app.immich.client import ImmichAssetPage, ImmichClient, ImmichPersonFilter, ImmichSearchFilters
from app.immich.errors import ImmichAuthenticationError
from app.immich.models import ImmichAssetSummary, ImmichPersonSummary, ImmichUploadMetadata


def test_normalizes_api_url() -> None:
    from app.utils.url_utils import normalize_api_url

    assert normalize_api_url("https://photos.example.com") == "https://photos.example.com/api"
    assert normalize_api_url("https://photos.example.com/api") == "https://photos.example.com/api"


def test_get_json_sends_api_key_header() -> None:
    seen_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers["x-api-key"] = request.headers["x-api-key"]
        return httpx.Response(200, json={"id": "user-1", "email": "a@example.com"})

    async def run() -> dict[str, object]:
        client = ImmichClient("https://photos.example.com", "secret-key")
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(base_url=client.api_base_url, transport=transport) as http_client:
            return await client._get_json("/users/me", http_client)

    payload = asyncio.run(run())

    assert seen_headers["x-api-key"] == "secret-key"
    assert payload["email"] == "a@example.com"


def test_get_json_maps_unauthorized_to_auth_error() -> None:
    async def run() -> None:
        client = ImmichClient("https://photos.example.com", "bad-key")
        transport = httpx.MockTransport(lambda request: httpx.Response(401, json={}))
        async with httpx.AsyncClient(base_url=client.api_base_url, transport=transport) as http_client:
            await client._get_json("/users/me", http_client)

    try:
        asyncio.run(run())
    except ImmichAuthenticationError as exc:
        assert "API key" in str(exc)
    else:
        raise AssertionError("Expected ImmichAuthenticationError")


def test_connection_accepts_album_probe_when_user_probe_is_rejected(monkeypatch) -> None:
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        if request.url.path.endswith("/users/me"):
            return httpx.Response(401, json={})
        if request.url.path.endswith("/albums"):
            return httpx.Response(200, json=[])
        return httpx.Response(200, json={"major": 1, "minor": 2, "patch": 3})

    original_async_client = httpx.AsyncClient

    def mock_async_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return original_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", mock_async_client)

    result = asyncio.run(ImmichClient("https://photos.example.com", "secret-key").test_connection())

    assert result.ok is True
    assert result.server_version == "1.2.3"
    assert any(path.endswith("/albums") for path in requests)


def test_get_assets_uses_default_search_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    seen_filters: dict[str, object] = {}

    async def fake_search_assets(self, filters: ImmichSearchFilters):
        seen_filters["album_ids"] = filters.album_ids
        seen_filters["person_filters"] = filters.person_filters
        return ImmichAssetPage(items=[], total=0, count=0, next_page=None)

    monkeypatch.setattr(ImmichClient, "search_assets", fake_search_assets)
    asyncio.run(ImmichClient("https://photos.example.com", "secret-key").get_assets(page=3, size=12))

    assert seen_filters == {
        "album_ids": None,
        "person_filters": [],
    }


def test_search_assets_applies_filters_and_sampling(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/search/random"
        requests.append(json.loads(request.content.decode()))
        return httpx.Response(
            200,
            json=[
                {
                    "id": "asset-2",
                    "originalFileName": "b.jpg",
                    "type": "VIDEO",
                    "people": [{"id": "person-1", "name": "Alice", "isHidden": False}],
                }
            ],
        )

    original_async_client = httpx.AsyncClient

    def mock_async_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return original_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", mock_async_client)
    result = asyncio.run(
        ImmichClient("https://photos.example.com", "secret-key").search_assets(
            ImmichSearchFilters(
                album_ids=["album-1"],
                person_filters=[ImmichPersonFilter(person_id="person-1", mode="optional")],
                taken_after=date(2026, 5, 1),
                taken_before=date(2026, 5, 31),
                media_type="video",
            )
        )
    )

    assert len(requests) == 1
    assert requests[0]["size"] == 1
    assert requests[0]["withDeleted"] is False
    assert requests[0]["withExif"] is False
    assert requests[0]["withPeople"] is True
    assert requests[0]["withStacked"] is False
    assert requests[0]["albumIds"] == ["album-1"]
    assert requests[0]["personIds"] == ["person-1"]
    assert requests[0]["type"] == "VIDEO"
    assert requests[0]["takenAfter"] == "2026-05-01T00:00:00Z"
    assert requests[0]["takenBefore"] == "2026-05-31T23:59:59.999999Z"
    assert "shuffleSeed" not in requests[0]
    assert "randomize" not in requests[0]
    assert result.count == 1
    assert result.total == 1
    assert [item.id for item in result.items] == ["asset-2"]


def test_search_assets_uses_requested_random_size_and_returns_all_assets(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content.decode()))
        return httpx.Response(
            200,
            json=[
                {"id": "asset-1", "originalFileName": "a.jpg", "type": "IMAGE", "people": []},
                {"id": "asset-2", "originalFileName": "b.jpg", "type": "IMAGE", "people": []},
                {"id": "asset-3", "originalFileName": "c.jpg", "type": "IMAGE", "people": []},
                {"id": "asset-4", "originalFileName": "d.jpg", "type": "IMAGE", "people": []},
            ],
        )

    original_async_client = httpx.AsyncClient

    def mock_async_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return original_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", mock_async_client)

    result = asyncio.run(
        ImmichClient("https://photos.example.com", "secret-key").search_assets(
            ImmichSearchFilters(random_size=4, media_type="photo")
        )
    )

    assert requests[0]["size"] == 4
    assert [item.id for item in result.items] == ["asset-1", "asset-2", "asset-3", "asset-4"]
    assert result.count == 4


def test_search_assets_parses_people_faces() -> None:
    payload = {
        "id": "asset-1",
        "originalFileName": "photo.jpg",
        "people": [
            {
                "id": "person-1",
                "name": "Alice",
                "isHidden": False,
                "faces": [
                    {
                        "id": "face-1",
                        "imageWidth": 400,
                        "imageHeight": 300,
                        "boundingBoxX1": 10,
                        "boundingBoxY1": 20,
                        "boundingBoxX2": 110,
                        "boundingBoxY2": 140,
                    }
                ],
            }
        ],
    }

    asset = ImmichClient._coerce_asset_summary(payload)

    assert asset is not None
    assert len(asset.people) == 1
    assert asset.people[0].name == "Alice"
    assert len(asset.people[0].faces) == 1
    face = asset.people[0].faces[0]
    assert face.person_name == "Alice"
    assert face.image_width == 400
    assert face.bounding_box_x1 == 10.0


def test_search_assets_sends_obligatory_people_to_request(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[dict[str, object]] = []

    class NoShuffleRandom:
        def shuffle(self, items):
            return None

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/search/random"
        requests.append(json.loads(request.content.decode()))
        return httpx.Response(
            200,
            json=[
                {
                    "id": "asset-1",
                    "originalFileName": "a.jpg",
                    "type": "IMAGE",
                    "people": [{"id": "person-1", "name": "Alice", "isHidden": False}],
                }
            ],
        )

    original_async_client = httpx.AsyncClient

    def mock_async_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return original_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", mock_async_client)
    monkeypatch.setattr("app.immich.client.Random", NoShuffleRandom)
    asyncio.run(
        ImmichClient("https://photos.example.com", "secret-key").search_assets(
            ImmichSearchFilters(
                person_filters=[
                    ImmichPersonFilter(person_id="person-1", mode="obligatory"),
                    ImmichPersonFilter(person_id="person-2", mode="optional"),
                ],
            )
        )
    )

    assert requests[0]["personIds"] == ["person-1"]


def test_search_assets_tries_optional_person_combinations(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[dict[str, object]] = []

    class NoShuffleRandom:
        def shuffle(self, items):
            return None

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/search/random"
        body = json.loads(request.content.decode())
        requests.append(body)
        person_ids = body.get("personIds", [])
        if person_ids != ["person-1", "person-2"]:
            return httpx.Response(200, json=[])
        return httpx.Response(
            200,
            json=[
                {
                    "id": "asset-2",
                    "originalFileName": "b.jpg",
                    "type": "IMAGE",
                    "people": [
                        {"id": "person-1", "name": "Alice", "isHidden": False},
                        {"id": "person-2", "name": "Bob", "isHidden": False},
                    ],
                },
            ],
        )

    original_async_client = httpx.AsyncClient

    def mock_async_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return original_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", mock_async_client)
    monkeypatch.setattr("app.immich.client.Random", NoShuffleRandom)
    result = asyncio.run(
        ImmichClient("https://photos.example.com", "secret-key").search_assets(
            ImmichSearchFilters(
                person_filters=[
                    ImmichPersonFilter(person_id="person-1", mode="optional"),
                    ImmichPersonFilter(person_id="person-2", mode="optional"),
                ],
            )
        )
    )

    assert len(requests) == 3
    assert requests[0]["personIds"] == ["person-1"]
    assert requests[1]["personIds"] == ["person-2"]
    assert requests[2]["personIds"] == ["person-1", "person-2"]
    assert result.total == 1
    assert [item.id for item in result.items] == ["asset-2"]


def test_search_assets_obligatory_optional_falls_back_after_empty_response(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[dict[str, object]] = []

    class NoShuffleRandom:
        def shuffle(self, items):
            return None

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/search/random"
        body = json.loads(request.content.decode())
        requests.append(body)
        if body.get("personIds") == ["person-1"]:
            return httpx.Response(200, json=[])
        return httpx.Response(
            200,
            json=[
                {
                    "id": "asset-10",
                    "originalFileName": "combo.jpg",
                    "type": "IMAGE",
                    "people": [
                        {"id": "person-1", "name": "Alice", "isHidden": False},
                        {"id": "person-2", "name": "Bob", "isHidden": False},
                    ],
                }
            ],
        )

    original_async_client = httpx.AsyncClient

    def mock_async_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return original_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", mock_async_client)
    monkeypatch.setattr("app.immich.client.Random", NoShuffleRandom)
    result = asyncio.run(
        ImmichClient("https://photos.example.com", "secret-key").search_assets(
            ImmichSearchFilters(
                person_filters=[
                    ImmichPersonFilter(person_id="person-1", mode="obligatory"),
                    ImmichPersonFilter(person_id="person-2", mode="optional"),
                    ImmichPersonFilter(person_id="person-3", mode="optional"),
                ],
            )
        )
    )

    assert len(requests) == 2
    assert requests[0]["personIds"] == ["person-1"]
    assert requests[1]["personIds"] == ["person-1", "person-2"]
    assert result.total == 1
    assert [item.id for item in result.items] == ["asset-10"]


def test_search_assets_exclude_retries_same_variant(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[dict[str, object]] = []
    responses = iter(
        [
            [
                {
                    "id": "asset-excluded",
                    "originalFileName": "excluded.jpg",
                    "type": "IMAGE",
                    "people": [
                        {"id": "person-1", "name": "Alice", "isHidden": False},
                        {"id": "person-2", "name": "Bob", "isHidden": False},
                    ],
                }
            ],
            [
                {
                    "id": "asset-allowed",
                    "originalFileName": "allowed.jpg",
                    "type": "IMAGE",
                    "people": [{"id": "person-1", "name": "Alice", "isHidden": False}],
                }
            ],
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/search/random"
        requests.append(json.loads(request.content.decode()))
        return httpx.Response(200, json=next(responses))

    original_async_client = httpx.AsyncClient

    def mock_async_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return original_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", mock_async_client)
    result = asyncio.run(
        ImmichClient("https://photos.example.com", "secret-key").search_assets(
            ImmichSearchFilters(
                person_filters=[
                    ImmichPersonFilter(person_id="person-1", mode="optional"),
                    ImmichPersonFilter(person_id="person-2", mode="exclude"),
                ],
            )
        )
    )

    assert len(requests) == 2
    assert requests[0]["personIds"] == ["person-1"]
    assert requests[1]["personIds"] == ["person-1"]
    assert [item.id for item in result.items] == ["asset-allowed"]


def test_filter_assets_by_people_supports_modes() -> None:
    items = [
        ImmichAssetSummary(id="asset-1", people=[ImmichPersonSummary(id="p1", name="Alice")]),
        ImmichAssetSummary(id="asset-2", people=[ImmichPersonSummary(id="p2", name="Bob")]),
        ImmichAssetSummary(
            id="asset-3",
            people=[
                ImmichPersonSummary(id="p1", name="Alice"),
                ImmichPersonSummary(id="p2", name="Bob"),
            ],
        ),
        ImmichAssetSummary(id="asset-4", people=[]),
    ]

    optional = ImmichClient._filter_assets_by_people(
        items,
        [ImmichPersonFilter(person_id="p1", mode="optional")],
    )
    obligatory = ImmichClient._filter_assets_by_people(
        items,
        [
            ImmichPersonFilter(person_id="p1", mode="obligatory"),
            ImmichPersonFilter(person_id="p2", mode="obligatory"),
        ],
    )
    excluded = ImmichClient._filter_assets_by_people(
        items,
        [ImmichPersonFilter(person_id="p1", mode="exclude")],
    )
    mixed = ImmichClient._filter_assets_by_people(
        items,
        [
            ImmichPersonFilter(person_id="p1", mode="obligatory"),
            ImmichPersonFilter(person_id="p2", mode="optional"),
        ],
    )
    obligatory_with_optional = ImmichClient._filter_assets_by_people(
        items,
        [
            ImmichPersonFilter(person_id="p1", mode="obligatory"),
            ImmichPersonFilter(person_id="p2", mode="optional"),
            ImmichPersonFilter(person_id="p3", mode="optional"),
        ],
    )
    optional_union = ImmichClient._filter_assets_by_people(
        items,
        [
            ImmichPersonFilter(person_id="p1", mode="optional"),
            ImmichPersonFilter(person_id="p2", mode="optional"),
        ],
    )

    assert [item.id for item in optional] == ["asset-1", "asset-3"]
    assert [item.id for item in obligatory] == ["asset-3"]
    assert [item.id for item in excluded] == ["asset-2", "asset-4"]
    assert [item.id for item in mixed] == ["asset-3"]
    assert [item.id for item in obligatory_with_optional] == ["asset-3"]
    assert [item.id for item in optional_union] == ["asset-1", "asset-2", "asset-3"]


def test_list_people_orders_by_asset_count(monkeypatch: pytest.MonkeyPatch) -> None:
    payloads = iter(
        [
            {
                "people": [
                    {"id": "person-1", "name": "Alice", "isHidden": False},
                    {"id": "person-2", "name": "Bob", "isHidden": False},
                ],
                "hasNextPage": False,
            },
        ]
    )
    stats = {
        "/api/people/person-1/statistics": {"assets": 12},
        "/api/people/person-2/statistics": {"assets": 34},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/people":
            return httpx.Response(200, json=next(payloads))
        return httpx.Response(200, json=stats[request.url.path])

    original_async_client = httpx.AsyncClient

    def mock_async_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return original_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", mock_async_client)
    people = asyncio.run(ImmichClient("https://photos.example.com", "secret-key").list_people())

    assert [person.id for person in people] == ["person-2", "person-1"]
    assert [person.asset_count for person in people] == [34, 12]


def test_get_asset_thumbnail_returns_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    seen_request: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_request["path"] = request.url.path
        seen_request["query"] = dict(request.url.params)
        return httpx.Response(200, content=b"thumb-bytes", headers={"content-type": "image/webp"})

    original_async_client = httpx.AsyncClient

    def mock_async_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return original_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", mock_async_client)
    content, content_type = asyncio.run(
        ImmichClient("https://photos.example.com", "secret-key").get_asset_thumbnail("asset-1")
    )

    assert seen_request["path"] == "/api/assets/asset-1/thumbnail"
    assert seen_request["query"] == {"format": "WEBP"}
    assert content == b"thumb-bytes"
    assert content_type == "image/webp"


def test_get_asset_thumbnail_falls_back_to_original_download(monkeypatch: pytest.MonkeyPatch) -> None:
    seen_paths: list[str] = []

    buffer = BytesIO()
    Image.new("RGB", (8, 8), color=(12, 34, 56)).save(buffer, format="PNG")
    original_image_bytes = buffer.getvalue()

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        if request.url.path.endswith("/thumbnail"):
            return httpx.Response(404, json={})
        if request.url.path.endswith("/assets/asset-1/file"):
            return httpx.Response(200, content=original_image_bytes, headers={"content-type": "image/png"})
        return httpx.Response(404, json={})

    original_async_client = httpx.AsyncClient

    def mock_async_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return original_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", mock_async_client)
    content, content_type = asyncio.run(
        ImmichClient("https://photos.example.com", "secret-key").get_asset_thumbnail("asset-1")
    )

    assert "/api/assets/asset-1/file" in seen_paths
    assert content.startswith(b"\xff\xd8")
    assert content_type == "image/jpeg"


def test_upload_asset_sends_v3_metadata_without_device_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    async def fake_request_json(self, method, path, client, **kwargs):
        seen["method"] = method
        seen["path"] = path
        seen["data"] = kwargs.get("data")
        seen["headers"] = kwargs.get("headers")
        seen["files"] = kwargs.get("files")
        return {"id": "asset-123", "status": "created"}

    monkeypatch.setattr(ImmichClient, "_request_json", fake_request_json)

    result = asyncio.run(
        ImmichClient("https://photos.example.com", "secret-key").upload_asset(
            content=b"png-bytes",
            metadata=ImmichUploadMetadata(
                filename="collage.png",
                device_asset_id="device-asset-1",
                device_id="device-1",
                file_created_at="2026-05-13T10:00:00Z",
                file_modified_at="2026-05-13T10:00:00Z",
            ),
        )
    )

    assert seen["method"] == "POST"
    assert seen["path"] == "/assets"
    assert seen["data"]["filename"] == "collage.png"
    assert "deviceAssetId" not in seen["data"]
    assert "deviceId" not in seen["data"]
    assert seen["headers"]["x-immich-checksum"] is not None
    assert "assetData" in seen["files"]
    assert result.id == "asset-123"
    assert result.status == "created"


def test_add_assets_to_album_uses_v3_put_album_assets_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    async def fake_request(self, method, path, client, **kwargs):
        seen["method"] = method
        seen["path"] = path
        seen["json"] = kwargs.get("json_payload")
        return httpx.Response(200, json=[{"id": "asset-1", "success": True}])

    monkeypatch.setattr(ImmichClient, "_request", fake_request)

    asyncio.run(ImmichClient("https://photos.example.com", "secret-key").add_assets_to_album("album-1", ["asset-1"]))

    assert seen == {
        "method": "PUT",
        "path": "/albums/album-1/assets",
        "json": {"ids": ["asset-1"]},
    }


def test_add_assets_to_album_falls_back_to_patch_on_404_or_405(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.immich.errors import ImmichUnexpectedResponseError

    calls = []

    async def fake_request(self, method, path, client, **kwargs):
        calls.append((method, path))
        if len(calls) == 1:
            # First call (PUT /albums/album-1/assets) fails with 404
            raise ImmichUnexpectedResponseError("Immich add-assets-to-album endpoint was not found")
        # Second call (PATCH /albums/album-1/assets) succeeds
        return httpx.Response(200, json=[{"id": "asset-1", "success": True}])

    monkeypatch.setattr(ImmichClient, "_request", fake_request)

    asyncio.run(ImmichClient("https://photos.example.com", "secret-key").add_assets_to_album("album-1", ["asset-1"]))

    assert calls == [
        ("PUT", "/albums/album-1/assets"),
        ("PATCH", "/albums/album-1/assets"),
    ]


def test_add_assets_to_album_falls_back_to_legacy_put_on_repeated_404_or_405(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.immich.errors import ImmichUnexpectedResponseError

    calls = []

    async def fake_request(self, method, path, client, **kwargs):
        calls.append((method, path))
        if len(calls) < 3:
            raise ImmichUnexpectedResponseError("Immich endpoint was not found")
        # Third call (PUT /albums/album-1/asset) succeeds
        return httpx.Response(200, json=[{"id": "asset-1", "success": True}])

    monkeypatch.setattr(ImmichClient, "_request", fake_request)

    asyncio.run(ImmichClient("https://photos.example.com", "secret-key").add_assets_to_album("album-1", ["asset-1"]))

    assert calls == [
        ("PUT", "/albums/album-1/assets"),
        ("PATCH", "/albums/album-1/assets"),
        ("PUT", "/albums/album-1/asset"),
    ]


def test_add_assets_to_album_raises_last_error_when_all_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.immich.errors import ImmichUnexpectedResponseError

    calls = []

    async def fake_request(self, method, path, client, **kwargs):
        calls.append((method, path))
        raise ImmichUnexpectedResponseError(f"Failed method {method} path {path} - not found")

    monkeypatch.setattr(ImmichClient, "_request", fake_request)

    with pytest.raises(ImmichUnexpectedResponseError, match="Failed method PUT path /albums/album-1/asset - not found"):
        asyncio.run(
            ImmichClient("https://photos.example.com", "secret-key").add_assets_to_album("album-1", ["asset-1"])
        )

    assert calls == [
        ("PUT", "/albums/album-1/assets"),
        ("PATCH", "/albums/album-1/assets"),
        ("PUT", "/albums/album-1/asset"),
    ]


def test_add_assets_to_album_does_not_retry_on_auth_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    async def fake_request(self, method, path, client, **kwargs):
        calls.append((method, path))
        raise ImmichAuthenticationError("Immich rejected the API key")

    monkeypatch.setattr(ImmichClient, "_request", fake_request)

    with pytest.raises(ImmichAuthenticationError):
        asyncio.run(
            ImmichClient("https://photos.example.com", "secret-key").add_assets_to_album("album-1", ["asset-1"])
        )

    assert calls == [
        ("PUT", "/albums/album-1/assets"),
    ]


def test_get_asset_data_uses_v3_asset_original_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    seen_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        return httpx.Response(200, content=b"image-bytes", headers={"content-type": "image/jpeg"})

    original_async_client = httpx.AsyncClient

    def mock_async_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return original_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", mock_async_client)
    content = asyncio.run(ImmichClient("https://photos.example.com", "secret-key").get_asset_data("asset-1"))

    assert seen_paths == ["/api/assets/asset-1/original"]
    assert content == b"image-bytes"


def test_get_asset_data_falls_back_to_alternate_and_legacy_endpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    seen_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        seen_paths.append(path)
        if path == "/api/download/asset/asset-1":
            return httpx.Response(200, content=b"image-bytes-legacy", headers={"content-type": "image/jpeg"})
        return httpx.Response(404)

    original_async_client = httpx.AsyncClient

    def mock_async_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return original_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", mock_async_client)
    content = asyncio.run(ImmichClient("https://photos.example.com", "secret-key").get_asset_data("asset-1"))

    assert seen_paths == [
        "/api/assets/asset-1/original",
        "/api/assets/asset-1/file",
        "/api/asset/download/asset-1",
        "/api/download/asset/asset-1",
    ]
    assert content == b"image-bytes-legacy"


def test_update_asset_uses_v3_patch_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    async def fake_request(self, method, path, client, **kwargs):
        seen["method"] = method
        seen["path"] = path
        seen["json"] = kwargs.get("json_payload")
        return httpx.Response(200, json={})

    monkeypatch.setattr(ImmichClient, "_request", fake_request)

    asyncio.run(
        ImmichClient("https://photos.example.com", "secret-key").update_asset(
            "asset-1",
            description="DailyFX result",
            is_favorite=True,
        )
    )

    assert seen == {
        "method": "PATCH",
        "path": "/assets/asset-1",
        "json": {"description": "DailyFX result", "isFavorite": True},
    }


def test_upsert_tags_uses_put_tags_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    seen_requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(
            {
                "method": request.method,
                "path": request.url.path,
                "body": json.loads(request.content.decode()),
            }
        )
        return httpx.Response(
            200,
            json=[
                {
                    "id": "tag-1",
                    "name": "dailyFX",
                    "value": "dailyFX",
                    "parentId": None,
                }
            ],
        )

    original_async_client = httpx.AsyncClient

    def mock_async_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return original_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", mock_async_client)
    tags = asyncio.run(ImmichClient("https://photos.example.com", "secret-key").upsert_tags(["  dailyFX  "]))

    assert seen_requests == [
        {
            "method": "PUT",
            "path": "/api/tags",
            "body": {"tags": ["dailyFX"]},
        }
    ]
    assert len(tags) == 1
    assert tags[0].id == "tag-1"
    assert tags[0].name == "dailyFX"


def test_tag_assets_uses_put_tag_assets_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    seen_requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(
            {
                "method": request.method,
                "path": request.url.path,
                "body": json.loads(request.content.decode()),
            }
        )
        return httpx.Response(200, json=[{"id": "asset-1", "success": True}])

    original_async_client = httpx.AsyncClient

    def mock_async_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return original_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", mock_async_client)
    asyncio.run(ImmichClient("https://photos.example.com", "secret-key").tag_assets("tag-1", ["asset-1"]))

    assert seen_requests == [
        {
            "method": "PUT",
            "path": "/api/tags/tag-1/assets",
            "body": {"ids": ["asset-1"]},
        }
    ]


def test_immich_client_default_timeout():
    client = ImmichClient("https://photos.example.com", "secret-key")
    assert client.timeout == 30.0


def test_list_people_limits_to_33(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_people = [{"id": f"person-{i}", "name": f"Person {i}", "isHidden": False} for i in range(1, 41)]
    payloads = iter([{"people": mock_people, "hasNextPage": False}])

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/people":
            return httpx.Response(200, json=next(payloads))
        return httpx.Response(200, json={"assets": 1})

    original_async_client = httpx.AsyncClient

    def mock_async_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return original_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", mock_async_client)
    people = asyncio.run(ImmichClient("https://photos.example.com", "secret-key").list_people())

    assert len(people) == 33
