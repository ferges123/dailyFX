import asyncio
import logging
from datetime import date, datetime, time, timezone
from hashlib import sha1
from itertools import combinations
from random import Random
from dataclasses import replace
from typing import Any

import httpx
from pillow_heif import register_heif_opener

register_heif_opener()

from app.immich.errors import (
    ImmichAuthenticationError,
    ImmichConnectionError,
    ImmichPermissionError,
    ImmichUnexpectedResponseError,
)
from app.immich.models import (
    ImmichAlbumSummary,
    ImmichAssetPage,
    ImmichAssetSummary,
    ImmichConnectionResult,
    ImmichExifInfo,
    ImmichFaceSummary,
    ImmichPersonFilter,
    ImmichPersonSummary,
    ImmichSearchFilters,
    ImmichTagSummary,
    ImmichUploadMetadata,
    ImmichUploadResult,
)
from app.utils.url_utils import normalize_api_url

logger = logging.getLogger(__name__)

_client_cache: dict[tuple[str, float], httpx.AsyncClient] = {}


class ImmichClient:
    def __init__(self, server_url: str, api_key: str, timeout: float = 30.0) -> None:
        self.server_url = server_url.rstrip("/")
        self.api_base_url = normalize_api_url(server_url)
        self.api_key = api_key
        self.timeout = timeout

    def _get_client(self, timeout: float | None = None) -> httpx.AsyncClient:
        t = timeout if timeout is not None else self.timeout
        key = (self.api_base_url, t)
        client = _client_cache.get(key)
        if client is None or client.is_closed:
            client = httpx.AsyncClient(
                base_url=self.api_base_url,
                timeout=t,
                limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            )
            _client_cache[key] = client
        return client

    def _headers(self, json_type: bool = True) -> dict[str, str]:
        h = {"x-api-key": self.api_key}
        if json_type:
            h["Accept"] = "application/json"
        return h

    @staticmethod
    def _checksum(content: bytes) -> str:
        return sha1(content).hexdigest()

    def _handle_response_errors(self, response: httpx.Response, not_found_message: str) -> None:
        if response.status_code == 401:
            raise ImmichAuthenticationError("Immich rejected the API key")
        if response.status_code == 403:
            raise ImmichPermissionError("Immich API key is missing required permissions")
        if response.status_code == 404:
            raise ImmichUnexpectedResponseError(not_found_message)
        if response.status_code >= 400:
            raise ImmichUnexpectedResponseError(f"Immich returned HTTP {response.status_code}")

    async def _request_json(
        self,
        method: str,
        path: str,
        client: httpx.AsyncClient,
        *,
        json_payload: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        not_found_message: str = "Immich endpoint was not found",
    ) -> dict[str, Any]:
        try:
            response = await client.request(
                method,
                path,
                headers={**self._headers(json_type=True), **(headers or {})},
                json=json_payload,
                data=data,
                files=files,
                follow_redirects=True,
            )
        except httpx.TimeoutException as exc:
            raise ImmichConnectionError("Timed out while connecting to Immich") from exc
        except httpx.RequestError as exc:
            raise ImmichConnectionError("Could not reach Immich") from exc

        self._handle_response_errors(response, not_found_message)

        try:
            payload = response.json()
        except ValueError as exc:
            raise ImmichUnexpectedResponseError("Immich returned non-JSON response") from exc
        if not isinstance(payload, dict):
            raise ImmichUnexpectedResponseError("Immich returned unexpected response shape")
        return payload

    async def _request(
        self,
        method: str,
        path: str,
        client: httpx.AsyncClient,
        *,
        json_payload: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        not_found_message: str = "Immich endpoint was not found",
    ) -> httpx.Response:
        try:
            response = await client.request(
                method,
                path,
                headers={**self._headers(json_type=True), **(headers or {})},
                json=json_payload,
                data=data,
                files=files,
                follow_redirects=True,
            )
        except httpx.TimeoutException as exc:
            raise ImmichConnectionError("Timed out while connecting to Immich") from exc
        except httpx.RequestError as exc:
            raise ImmichConnectionError("Could not reach Immich") from exc

        self._handle_response_errors(response, not_found_message)
        return response

    async def _get_any_json(
        self,
        path: str,
        client: httpx.AsyncClient,
        params: dict[str, Any] | None = None,
    ) -> Any:
        try:
            response = await client.get(
                path, headers=self._headers(json_type=True), params=params, follow_redirects=True
            )
        except httpx.TimeoutException as exc:
            raise ImmichConnectionError("Timed out while connecting to Immich") from exc
        except httpx.RequestError as exc:
            raise ImmichConnectionError("Could not reach Immich") from exc

        self._handle_response_errors(response, "Immich endpoint was not found")

        try:
            return response.json()
        except ValueError as exc:
            raise ImmichUnexpectedResponseError("Immich returned non-JSON response") from exc

    async def _get_json(
        self,
        path: str,
        client: httpx.AsyncClient,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = await self._get_any_json(path, client, params=params)
        if not isinstance(payload, dict):
            raise ImmichUnexpectedResponseError("Immich returned unexpected response shape")
        return payload

    async def _post_json(
        self,
        path: str,
        client: httpx.AsyncClient,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            response = await client.post(
                path, headers=self._headers(json_type=True), json=payload, follow_redirects=True
            )
        except httpx.TimeoutException as exc:
            raise ImmichConnectionError("Timed out while connecting to Immich") from exc
        except httpx.RequestError as exc:
            raise ImmichConnectionError("Could not reach Immich") from exc

        self._handle_response_errors(response, "Immich endpoint was not found")

        try:
            response_payload = response.json()
        except ValueError as exc:
            raise ImmichUnexpectedResponseError("Immich returned non-JSON response") from exc
        if not isinstance(response_payload, dict):
            raise ImmichUnexpectedResponseError("Immich returned unexpected response shape")
        return response_payload

    async def _request_any_json(
        self,
        method: str,
        path: str,
        client: httpx.AsyncClient,
        *,
        json_payload: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        not_found_message: str = "Immich endpoint was not found",
    ) -> Any:
        response = await self._request(
            method,
            path,
            client,
            json_payload=json_payload,
            data=data,
            files=files,
            headers=headers,
            not_found_message=not_found_message,
        )
        try:
            return response.json()
        except ValueError as exc:
            raise ImmichUnexpectedResponseError("Immich returned non-JSON response") from exc

    @staticmethod
    def _coerce_asset_summary(payload: dict[str, Any]) -> ImmichAssetSummary | None:
        asset_id = payload.get("id")
        if not isinstance(asset_id, str) or not asset_id.strip():
            return None
        original_file_name = payload.get("originalFileName") or payload.get("original_file_name")
        created_at = payload.get("fileCreatedAt") or payload.get("createdAt") or payload.get("created_at")
        updated_at = payload.get("fileModifiedAt") or payload.get("updatedAt") or payload.get("updated_at")
        mime_type = payload.get("mimeType") or payload.get("mime_type")
        asset_type = payload.get("type") or payload.get("assetType") or payload.get("asset_type")
        raw_people = payload.get("people", [])
        people = (
            [
                person
                for item in raw_people
                if isinstance(item, dict) and (person := ImmichClient._coerce_person_summary(item)) is not None
            ]
            if isinstance(raw_people, list)
            else []
        )
        return ImmichAssetSummary(
            id=asset_id,
            original_file_name=original_file_name if isinstance(original_file_name, str) else None,
            created_at=created_at if isinstance(created_at, str) else None,
            updated_at=updated_at if isinstance(updated_at, str) else None,
            mime_type=mime_type if isinstance(mime_type, str) else None,
            asset_type=asset_type if isinstance(asset_type, str) else None,
            people=people,
        )

    @staticmethod
    def _coerce_album_summary(payload: dict[str, Any]) -> ImmichAlbumSummary | None:
        album_id = payload.get("id")
        album_name = payload.get("albumName")
        if not isinstance(album_id, str) or not isinstance(album_name, str):
            return None
        asset_count = payload.get("assetCount")
        thumbnail_asset_id = payload.get("albumThumbnailAssetId")
        return ImmichAlbumSummary(
            id=album_id,
            album_name=album_name,
            asset_count=asset_count if isinstance(asset_count, int) else 0,
            thumbnail_asset_id=thumbnail_asset_id if isinstance(thumbnail_asset_id, str) else None,
        )

    @staticmethod
    def _coerce_tag_summary(payload: dict[str, Any]) -> ImmichTagSummary | None:
        tag_id = payload.get("id")
        name = payload.get("name")
        if not isinstance(tag_id, str) or not isinstance(name, str):
            return None
        value = payload.get("value")
        parent_id = payload.get("parentId")
        return ImmichTagSummary(
            id=tag_id,
            name=name,
            value=value if isinstance(value, str) else None,
            parent_id=parent_id if isinstance(parent_id, str) else None,
        )

    @staticmethod
    def _coerce_person_summary(payload: dict[str, Any]) -> ImmichPersonSummary | None:
        person_id = payload.get("id")
        name = payload.get("name")
        if not isinstance(person_id, str) or not isinstance(name, str):
            return None
        raw_faces = payload.get("faces") or payload.get("faceList") or payload.get("face")
        faces = []
        if isinstance(raw_faces, list):
            faces = [
                face
                for item in raw_faces
                if isinstance(item, dict)
                and (face := ImmichClient._coerce_face_summary(item, person_id=person_id, person_name=name)) is not None
            ]
        elif isinstance(raw_faces, dict):
            face = ImmichClient._coerce_face_summary(raw_faces, person_id=person_id, person_name=name)
            if face is not None:
                faces = [face]
        count = payload.get("count", 0)
        return ImmichPersonSummary(
            id=person_id,
            name=name,
            is_hidden=bool(payload.get("isHidden", False)),
            asset_count=count if isinstance(count, int) else 0,
            faces=faces,
        )

    @staticmethod
    def _coerce_face_summary(
        payload: dict[str, Any],
        *,
        person_id: str | None = None,
        person_name: str | None = None,
    ) -> ImmichFaceSummary | None:
        face_id = payload.get("id") if isinstance(payload.get("id"), str) else payload.get("faceId")
        image_width = payload.get("imageWidth")
        if image_width is None:
            image_width = payload.get("image_width")
        image_height = payload.get("imageHeight")
        if image_height is None:
            image_height = payload.get("image_height")
        source_type = payload.get("sourceType")
        if source_type is None:
            source_type = payload.get("source_type")

        x1 = payload.get("boundingBoxX1")
        if x1 is None:
            x1 = payload.get("bounding_box_x1")
        y1 = payload.get("boundingBoxY1")
        if y1 is None:
            y1 = payload.get("bounding_box_y1")
        x2 = payload.get("boundingBoxX2")
        if x2 is None:
            x2 = payload.get("bounding_box_x2")
        y2 = payload.get("boundingBoxY2")
        if y2 is None:
            y2 = payload.get("bounding_box_y2")

        if x1 is None or y1 is None or x2 is None or y2 is None:
            x = payload.get("x")
            y = payload.get("y")
            width = payload.get("width")
            height = payload.get("height")
            if None not in (x, y, width, height):
                x1 = x
                y1 = y
                x2 = x + width
                y2 = y + height

        if x1 is None or y1 is None or x2 is None or y2 is None:
            return None

        return ImmichFaceSummary(
            id=face_id if isinstance(face_id, str) else None,
            person_id=person_id,
            person_name=person_name,
            image_width=image_width if isinstance(image_width, int) else None,
            image_height=image_height if isinstance(image_height, int) else None,
            bounding_box_x1=float(x1) if isinstance(x1, (int, float)) else None,
            bounding_box_y1=float(y1) if isinstance(y1, (int, float)) else None,
            bounding_box_x2=float(x2) if isinstance(x2, (int, float)) else None,
            bounding_box_y2=float(y2) if isinstance(y2, (int, float)) else None,
            source_type=source_type if isinstance(source_type, str) else None,
        )

    @staticmethod
    def _to_iso_utc_start(value: date) -> str:
        return datetime.combine(value, time.min, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _to_iso_utc_end(value: date) -> str:
        return datetime.combine(value, time.max, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")

    async def test_connection(self) -> ImmichConnectionResult:
        client = self._get_client()
        version = await self._get_server_version(client)
        user_payload = await self._get_authenticated_probe(client)

        return ImmichConnectionResult(
            ok=True,
            server_url=self.server_url,
            user_email=user_payload.get("email"),
            user_id=user_payload.get("id"),
            server_version=version,
        )

    async def _get_authenticated_probe(self, client: httpx.AsyncClient) -> dict[str, Any]:
        auth_error: ImmichAuthenticationError | None = None
        permission_error: ImmichPermissionError | None = None

        try:
            return await self._get_json("/users/me", client)
        except ImmichAuthenticationError as exc:
            auth_error = exc
        except ImmichPermissionError as exc:
            permission_error = exc
        except ImmichUnexpectedResponseError:
            pass

        try:
            albums_payload = await self._get_any_json("/albums", client)
            if isinstance(albums_payload, list):
                return {}
            if isinstance(albums_payload, dict):
                return albums_payload
        except ImmichAuthenticationError as exc:
            auth_error = exc
        except ImmichPermissionError as exc:
            permission_error = exc

        if permission_error is not None:
            raise permission_error
        if auth_error is not None:
            raise auth_error
        raise ImmichUnexpectedResponseError("Could not validate Immich API key")

    async def _get_server_version(self, client: httpx.AsyncClient) -> str | None:
        try:
            payload = await self._get_json("/server-info/version", client)
        except (ImmichUnexpectedResponseError, ImmichAuthenticationError, ImmichPermissionError):
            return None
        major = payload.get("major")
        minor = payload.get("minor")
        patch = payload.get("patch")
        if major is None or minor is None or patch is None:
            return None
        return f"{major}.{minor}.{patch}"

    async def get_assets(self, page: int = 1, size: int = 24) -> ImmichAssetPage:
        _ = size
        _ = page
        return await self.search_assets(ImmichSearchFilters())

    async def list_albums(self) -> list[ImmichAlbumSummary]:
        client = self._get_client()
        payload = await self._get_any_json("/albums", client)

        if not isinstance(payload, list):
            raise ImmichUnexpectedResponseError("Immich returned unexpected album list")
        return [
            summary
            for item in payload
            if isinstance(item, dict) and (summary := self._coerce_album_summary(item)) is not None
        ]

    async def create_album(
        self,
        album_name: str,
        asset_ids: list[str] | None = None,
        user_id: str | None = None,
    ) -> ImmichAlbumSummary | None:
        payload: dict[str, Any] = {"albumName": album_name}
        if asset_ids:
            payload["assetIds"] = asset_ids
        if user_id:
            payload["userId"] = user_id
            payload["role"] = "editor"
            payload["albumUsers"] = []

        client = self._get_client()
        response = await self._request(
            "POST",
            "/albums",
            client,
            json_payload=payload,
            not_found_message="Immich album creation endpoint was not found",
        )
        if response.headers.get("content-type", "").startswith("application/json"):
            try:
                response_payload = response.json()
            except ValueError:
                response_payload = None
        else:
            response_payload = None
        if not isinstance(response_payload, dict):
            return None
        summary = self._coerce_album_summary(response_payload)
        if summary is not None:
            return summary
        album_id = response_payload.get("id") or response_payload.get("albumId")
        if isinstance(album_id, str) and album_id.strip():
            return ImmichAlbumSummary(id=album_id, album_name=album_name, asset_count=len(asset_ids or []))
        return None

    async def upsert_tags(self, tag_names: list[str]) -> list[ImmichTagSummary]:
        normalized_names = [tag_name.strip() for tag_name in dict.fromkeys(tag_names) if tag_name.strip()]
        if not normalized_names:
            return []

        client = self._get_client()
        payload = await self._request_any_json(
            "PUT",
            "/tags",
            client,
            json_payload={"tags": normalized_names},
            not_found_message="Immich tag upsert endpoint was not found",
        )

        raw_tags: Any
        if isinstance(payload, list):
            raw_tags = payload
        elif isinstance(payload, dict):
            raw_tags = payload.get("tags") or payload.get("items") or payload.get("data")
        else:
            raw_tags = None

        if not isinstance(raw_tags, list):
            raise ImmichUnexpectedResponseError("Immich returned unexpected tag response")

        return [
            summary
            for item in raw_tags
            if isinstance(item, dict) and (summary := self._coerce_tag_summary(item)) is not None
        ]

    async def ensure_tag(self, tag_name: str) -> ImmichTagSummary:
        tags = await self.upsert_tags([tag_name])
        normalized = tag_name.strip().lower()
        for tag in tags:
            if tag.name.strip().lower() == normalized or (tag.value or "").strip().lower() == normalized:
                return tag
        if tags:
            return tags[0]
        raise ImmichUnexpectedResponseError("Immich did not return a tag")

    async def tag_assets(self, tag_id: str, asset_ids: list[str]) -> None:
        if not asset_ids:
            return

        client = self._get_client()
        await self._request_any_json(
            "PUT",
            f"/tags/{tag_id}/assets",
            client,
            json_payload={"ids": asset_ids},
            not_found_message="Immich tag-assets endpoint was not found",
        )

    async def add_assets_to_album(self, album_id: str, asset_ids: list[str]) -> None:
        if not asset_ids:
            return

        client = self._get_client()
        last_error: Exception | None = None
        # Try multiple HTTP method + path patterns.
        # 1. PUT /albums/{album_id}/assets (Standard v3 and v2)
        # 2. PATCH /albums/{album_id}/assets (Some v3 release candidates / variants)
        # 3. PUT /albums/{album_id}/asset (Legacy v2 fallback)
        endpoints = [
            ("PUT", f"/albums/{album_id}/assets"),
            ("PATCH", f"/albums/{album_id}/assets"),
            ("PUT", f"/albums/{album_id}/asset"),
        ]
        for method, path in endpoints:
            try:
                logger.info("Attempting to add assets to album %s via %s %s", album_id, method, path)
                await self._request(
                    method,
                    path,
                    client,
                    json_payload={"ids": asset_ids},
                    not_found_message=f"Immich add-assets-to-album endpoint ({path}) was not found",
                )
                logger.info("Successfully added assets to album %s via %s %s", album_id, method, path)
                return
            except ImmichUnexpectedResponseError as exc:
                last_error = exc
                # Only catch and retry on 404 (endpoint not found) or 405 (method not allowed/HTTP 405)
                exc_str = str(exc).lower()
                is_not_found = "not found" in exc_str
                is_method_not_allowed = "http 405" in exc_str or "method not allowed" in exc_str
                if not (is_not_found or is_method_not_allowed):
                    raise
        if last_error is not None:
            raise last_error

    async def upload_asset(
        self,
        content: bytes,
        filename: str | None = None,
        device_asset_id: str | None = None,
        device_id: str | None = None,
        file_created_at: str | None = None,
        file_modified_at: str | None = None,
        checksum: str | None = None,
        metadata: ImmichUploadMetadata | None = None,
    ) -> ImmichUploadResult:
        if metadata is not None:
            filename = metadata.filename
            device_asset_id = metadata.device_asset_id
            device_id = metadata.device_id
            file_created_at = metadata.file_created_at
            file_modified_at = metadata.file_modified_at
            checksum = checksum or metadata.checksum

        if not filename or not file_created_at or not file_modified_at:
            raise ImmichUnexpectedResponseError("Immich upload metadata is incomplete")

        client = self._get_client()
        response_payload = await self._request_json(
            "POST",
            "/assets",
            client,
            data=ImmichUploadMetadata(
                filename=filename,
                device_asset_id=device_asset_id or "",
                device_id=device_id or "",
                file_created_at=file_created_at,
                file_modified_at=file_modified_at,
            ).as_request_data(),
            files={
                "assetData": (
                    filename,
                    content,
                    metadata.content_type if metadata is not None else "image/png",
                )
            },
            headers={"x-immich-checksum": checksum or self._checksum(content)},
            not_found_message="Immich upload endpoint was not found",
        )
        asset_id = response_payload.get("id")
        if not isinstance(asset_id, str) or not asset_id.strip():
            raise ImmichUnexpectedResponseError("Immich returned unexpected upload response")
        status = response_payload.get("status")
        return ImmichUploadResult(id=asset_id, status=status if isinstance(status, str) else None)

    async def list_people(self) -> list[ImmichPersonSummary]:
        client = self._get_client()
        people: list[ImmichPersonSummary] = []
        page = 1
        while True:
            payload = await self._get_any_json(
                "/people",
                client,
                params={"page": page, "size": 1000, "withHidden": False},
            )
            if not isinstance(payload, dict):
                raise ImmichUnexpectedResponseError("Immich returned unexpected people response")
            raw_people = payload.get("people", [])
            if not isinstance(raw_people, list):
                raise ImmichUnexpectedResponseError("Immich returned unexpected people list")
            page_people = [
                summary
                for item in raw_people
                if isinstance(item, dict) and (summary := self._coerce_person_summary(item)) is not None
            ]
            if not page_people:
                break
            people.extend(page_people)
            if not payload.get("hasNextPage"):
                break
            page += 1

        if not people:
            return []

        named = [p for p in people if p.name.strip()]
        stats = await asyncio.gather(
            *(self._get_person_asset_count(client, p.id) for p in named)
        )
        enriched = []
        for p, count in zip(named, stats, strict=True):
            p_new = replace(p, asset_count=count)
            if count > 0 or not p_new.is_hidden:
                enriched.append(p_new)
        enriched.sort(key=lambda p: (-p.asset_count, p.name.lower()))
        return enriched[:33]

    async def _get_person_asset_count(self, client: httpx.AsyncClient, person_id: str) -> int:
        payload = await self._get_json(f"/people/{person_id}/statistics", client)
        assets = payload.get("assets")
        if isinstance(assets, int):
            return max(assets, 0)
        return 0

    async def search_assets(self, filters: ImmichSearchFilters) -> ImmichAssetPage:
        try:
            return await asyncio.wait_for(
                self._search_assets_inner(filters),
                timeout=60.0,
            )
        except asyncio.TimeoutError as exc:
            raise ImmichConnectionError("Asset search timed out after 60 s — try fewer person filters") from exc

    async def _search_assets_inner(self, filters: ImmichSearchFilters) -> ImmichAssetPage:
        selected = await self._search_random_asset(filters)
        return ImmichAssetPage(
            items=selected,
            total=len(selected),
            count=len(selected),
            next_page=None,
        )

    async def _search_random_asset(
        self,
        filters: ImmichSearchFilters,
    ) -> list[ImmichAssetSummary]:
        exclude_ids = {f.person_id for f in filters.person_filters if f.mode == "exclude"}
        request_sets = self._build_person_request_sets(filters)
        Random().shuffle(request_sets)

        client = self._get_client()
        for person_ids in request_sets:
            attempts = 3 if exclude_ids else 1
            for _ in range(attempts):
                assets = await self._post_random_assets(client, filters, person_ids)
                if not assets:
                    break
                if exclude_ids:
                    assets = [asset for asset in assets if not any(person.id in exclude_ids for person in asset.people)]
                if not assets:
                    continue
                return assets
        return []

    @staticmethod
    def _build_person_request_sets(filters: ImmichSearchFilters) -> list[list[str]]:
        if filters.person_ids:
            return [list(dict.fromkeys(filters.person_ids))]

        obligatory_ids = list(dict.fromkeys(f.person_id for f in filters.person_filters if f.mode == "obligatory"))
        optional_ids = list(dict.fromkeys(f.person_id for f in filters.person_filters if f.mode == "optional"))

        request_sets: list[list[str]] = []
        if obligatory_ids:
            for count in range(0, len(optional_ids) + 1):
                for optional_combo in combinations(optional_ids, count):
                    request_sets.append([*obligatory_ids, *optional_combo])
        else:
            for count in range(1, len(optional_ids) + 1):
                for optional_combo in combinations(optional_ids, count):
                    request_sets.append(list(optional_combo))

        return request_sets or [[]]

    async def _post_random_assets(
        self,
        client: httpx.AsyncClient,
        filters: ImmichSearchFilters,
        person_ids: list[str],
    ) -> list[ImmichAssetSummary]:
        body = self._build_random_search_body(filters, person_ids)
        payload = await self._request_any_json("POST", "/search/random", client, json_payload=body)
        if not isinstance(payload, list):
            raise ImmichUnexpectedResponseError("Immich returned unexpected random asset search response")
        return [
            summary
            for item in payload
            if isinstance(item, dict) and (summary := self._coerce_asset_summary(item)) is not None
        ]

    def _build_random_search_body(
        self,
        filters: ImmichSearchFilters,
        person_ids: list[str],
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "size": max(1, min(4, int(getattr(filters, "random_size", 1) or 1))),
            "withDeleted": False,
            "withExif": False,
            "withPeople": True,
            "withStacked": False,
        }
        if filters.album_ids:
            body["albumIds"] = filters.album_ids
        if person_ids:
            body["personIds"] = person_ids
        if filters.taken_after is not None:
            body["takenAfter"] = self._to_iso_utc_start(filters.taken_after)
        if filters.taken_before is not None:
            body["takenBefore"] = self._to_iso_utc_end(filters.taken_before)
        if filters.media_type == "photo":
            body["type"] = "IMAGE"
        elif filters.media_type == "video":
            body["type"] = "VIDEO"
        return body

    @staticmethod
    def _filter_assets_by_people(
        items: list[ImmichAssetSummary],
        person_filters: list[ImmichPersonFilter] | None,
    ) -> list[ImmichAssetSummary]:
        if not person_filters:
            return items
        excluded_ids = {item.person_id for item in person_filters if item.mode == "exclude"}
        obligatory_ids = {item.person_id for item in person_filters if item.mode == "obligatory"}
        optional_ids = {item.person_id for item in person_filters if item.mode == "optional"}

        filtered_items = [item for item in items if not any(person.id in excluded_ids for person in item.people)]
        if obligatory_ids:
            filtered_items = [
                item for item in filtered_items if obligatory_ids.issubset({person.id for person in item.people})
            ]
            if optional_ids:
                return [item for item in filtered_items if any(person.id in optional_ids for person in item.people)]
            return filtered_items
        if optional_ids:
            return [item for item in filtered_items if any(person.id in optional_ids for person in item.people)]
        return filtered_items

    @staticmethod
    def _dedupe_assets(items: list[ImmichAssetSummary]) -> list[ImmichAssetSummary]:
        deduped: dict[str, ImmichAssetSummary] = {}
        for item in items:
            deduped.setdefault(item.id, item)
        return list(deduped.values())

    async def get_asset_data(self, asset_id: str) -> bytes:
        """Download the original asset content."""
        # Use a longer timeout for full file downloads
        client = self._get_client(timeout=60.0)
        # Try multiple download endpoints. Immich has used different paths across versions.
        # 1. /assets/{id}/original (Standard stable endpoint for v2 & v3)
        # 2. /assets/{id}/file (Alternate endpoint)
        # 3. /asset/download/{id} (Legacy endpoint 1)
        # 4. /download/asset/{id} (Legacy endpoint 2)
        endpoints = [
            f"/assets/{asset_id}/original",
            f"/assets/{asset_id}/file",
            f"/asset/download/{asset_id}",
            f"/download/asset/{asset_id}",
        ]
        for endpoint in endpoints:
            for attempt in range(3):
                try:
                    logger.info("Attempting download: %s (attempt %d/3)", endpoint, attempt + 1)
                    # Use binary headers (no Accept: application/json)
                    response = await client.get(endpoint, headers=self._headers(json_type=False))

                    if response.status_code == 200:
                        if response.content:
                            logger.info(
                                "Success: downloaded %d bytes for %s via %s",
                                len(response.content),
                                asset_id,
                                endpoint,
                            )
                            return response.content
                        logger.warning(
                            "Immich returned 200 OK but empty content for asset %s at %s (attempt %d/3)",
                            asset_id,
                            endpoint,
                            attempt + 1,
                        )
                        if attempt < 2:
                            await asyncio.sleep(0.5 * (attempt + 1))
                            continue
                    elif response.status_code == 404:
                        logger.debug("Endpoint %s not found for asset %s", endpoint, asset_id)
                        break
                    else:
                        logger.warning(
                            "Immich returned %d for asset %s at %s", response.status_code, asset_id, endpoint
                        )
                        break
                except Exception as exc:
                    logger.warning("Error downloading from %s: %s", endpoint, exc)
                    if attempt < 2:
                        await asyncio.sleep(0.5 * (attempt + 1))
                        continue
                    break

        try:
            logger.info("Falling back to thumbnail for asset %s", asset_id)
            thumbnail_bytes, _ = await self.get_asset_thumbnail(asset_id, size="preview", allow_original_fallback=False)
            if thumbnail_bytes:
                logger.info("Thumbnail fallback succeeded: %d bytes for %s", len(thumbnail_bytes), asset_id)
                return thumbnail_bytes
        except Exception as exc:
            logger.warning("Thumbnail fallback failed for asset %s: %s", asset_id, exc)

        raise ImmichUnexpectedResponseError(
            f"Could not download original asset data for {asset_id} after trying multiple endpoints and thumbnail fallback"
        )

    async def update_asset(
        self, asset_id: str, description: str | None = None, is_favorite: bool | None = None
    ) -> None:
        """Update asset metadata (description, favorite status)."""
        payload: dict[str, Any] = {}
        if description is not None:
            payload["description"] = description
        if is_favorite is not None:
            payload["isFavorite"] = is_favorite

        if not payload:
            return

        client = self._get_client()
        await self._request(
            "PATCH",
            f"/assets/{asset_id}",
            client,
            json_payload=payload,
            not_found_message="Immich asset update endpoint was not found",
        )

    async def get_asset_thumbnail(
        self,
        asset_id: str,
        size: str = "preview",
        *,
        allow_original_fallback: bool = True,
    ) -> tuple[bytes, str | None]:
        client = self._get_client()
        last_error: Exception | None = None
        thumbnail_format = "WEBP" if size == "preview" else "JPEG"
        path = f"/assets/{asset_id}/thumbnail"
        try:
            url = f"{self.api_base_url}{path}"
            logger.debug("Trying Immich thumbnail: %s (size=%s)", url, size)
            response = await client.get(
                path,
                params={"format": thumbnail_format},
                headers=self._headers(json_type=False),
            )
            self._handle_response_errors(response, f"Immich thumbnail endpoint ({path}) failed")
            return response.content, response.headers.get("content-type")
        except Exception as exc:
            logger.debug("Immich thumbnail error for %s: %s", path, exc)
            last_error = exc

        if not allow_original_fallback:
            if last_error:
                raise last_error
            raise ImmichUnexpectedResponseError("Immich thumbnail endpoint failed")

        # If the thumbnail endpoint fails, try to download original and resize it as a last resort
        logger.warning("All thumbnail endpoints failed for asset %s, falling back to original data", asset_id)
        try:
            original_bytes = await self.get_asset_data(asset_id)
            if not original_bytes:
                raise ValueError("Downloaded original asset data is empty")

            # Quick resize using PIL to mimic a thumbnail
            from io import BytesIO

            from PIL import Image

            img = Image.open(BytesIO(original_bytes))
            img.thumbnail((1024, 1024))
            if img.mode != "RGB":
                img = img.convert("RGB")
            out = BytesIO()
            img.save(out, format="JPEG", quality=80)
            return out.getvalue(), "image/jpeg"
        except Exception as fallback_exc:
            logger.error("Thumbnail fallback to original failed for %s: %s", asset_id, fallback_exc)
            if last_error:
                raise last_error
            raise ImmichUnexpectedResponseError(f"Immich thumbnail not found and fallback failed: {fallback_exc}")

    async def get_asset_exif(self, asset_id: str) -> ImmichExifInfo:
        """Return the exifInfo dict from GET /assets/{id}, or {} on failure."""
        try:
            payload = await self.get_asset_info(asset_id)
            return payload.get("exifInfo") or {}
        except (
            ImmichAuthenticationError,
            ImmichConnectionError,
            ImmichPermissionError,
            ImmichUnexpectedResponseError,
        ):
            return {}

    async def get_asset_info(self, asset_id: str) -> dict[str, Any]:
        """Return the full asset payload from GET /assets/{id}."""
        client = self._get_client()
        return await self._get_json(f"/assets/{asset_id}", client)
