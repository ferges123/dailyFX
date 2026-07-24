import asyncio
import hashlib
import logging
from dataclasses import replace
from datetime import date
from random import Random
from typing import Any

import httpx
from pillow_heif import register_heif_opener

register_heif_opener()

from app.immich import endpoints
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
    ImmichPersonFilter,  # noqa: F401
    ImmichPersonSummary,
    ImmichSearchFilters,
    ImmichTagSummary,
    ImmichUploadMetadata,
    ImmichUploadResult,
)
from app.utils.safe_logging import redact_sensitive
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
        return hashlib.sha1(content, usedforsecurity=False).hexdigest()

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
        return endpoints.coerce_asset_summary(payload)

    @staticmethod
    def _coerce_album_summary(payload: dict[str, Any]) -> ImmichAlbumSummary | None:
        return endpoints.coerce_album_summary(payload)

    @staticmethod
    def _coerce_tag_summary(payload: dict[str, Any]) -> ImmichTagSummary | None:
        return endpoints.coerce_tag_summary(payload)

    @staticmethod
    def _coerce_person_summary(payload: dict[str, Any]) -> ImmichPersonSummary | None:
        return endpoints.coerce_person_summary(payload)

    @staticmethod
    def _coerce_face_summary(
        payload: dict[str, Any],
        *,
        person_id: str | None = None,
        person_name: str | None = None,
    ) -> ImmichFaceSummary | None:
        return endpoints.coerce_face_summary(payload, person_id=person_id, person_name=person_name)

    @staticmethod
    def _to_iso_utc_start(value: date) -> str:
        return endpoints.to_iso_utc_start(value)

    @staticmethod
    def _to_iso_utc_end(value: date) -> str:
        return endpoints.to_iso_utc_end(value)

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

    async def get_assets(
        self,
        page: int = 1,
        size: int = 24,
        filters: ImmichSearchFilters | None = None,
    ) -> ImmichAssetPage:
        client = self._get_client()
        body: dict[str, Any] = {
            "page": page,
            "size": size,
            "type": "IMAGE",
        }
        if filters is not None:
            if filters.media_type == "photo":
                body["type"] = "IMAGE"
            elif filters.media_type == "video":
                body["type"] = "VIDEO"
            elif filters.media_type == "all":
                body.pop("type", None)

            if filters.album_ids:
                body["albumIds"] = filters.album_ids

            if filters.taken_after is not None:
                body["takenAfter"] = self._to_iso_utc_start(filters.taken_after)
            if filters.taken_before is not None:
                body["takenBefore"] = self._to_iso_utc_end(filters.taken_before)

            pids = []
            if filters.person_ids:
                pids.extend(filters.person_ids)
            if filters.person_filters:
                pids.extend([pf.person_id for pf in filters.person_filters if pf.mode != "exclude"])
            if pids:
                body["personIds"] = list(dict.fromkeys(pids))

        logger.info("get_assets: sending request to Immich POST /search/metadata with body=%s", body)
        try:
            payload = await self._post_json("/search/metadata", client, body)
            logger.info("get_assets: Immich returned 200 OK")
        except Exception as e:
            logger.error("get_assets: error during POST /search/metadata: %s", redact_sensitive(e))
            raise e
        if not isinstance(payload, dict):
            raise ImmichUnexpectedResponseError("Immich returned unexpected search metadata response")

        assets_payload = payload.get("assets", {})
        if not isinstance(assets_payload, dict):
            raise ImmichUnexpectedResponseError("Immich returned unexpected assets field in search metadata")

        items_list = assets_payload.get("items", [])
        if not isinstance(items_list, list):
            items_list = []

        coerced_items = []
        for item in items_list:
            if isinstance(item, dict):
                coerced = self._coerce_asset_summary(item)
                if coerced is not None:
                    coerced_items.append(coerced)

        total = assets_payload.get("total", len(coerced_items))
        count = assets_payload.get("count", len(coerced_items))

        return ImmichAssetPage(
            items=coerced_items,
            total=total if isinstance(total, int) else len(coerced_items),
            count=count if isinstance(count, int) else len(coerced_items),
            next_page=str(page + 1) if len(coerced_items) >= size else None,
        )

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
        stats = await asyncio.gather(*(self._get_person_asset_count(client, p.id) for p in named))
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
        return endpoints.build_person_request_sets(filters)

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
        return endpoints.build_random_search_body(filters, person_ids)

    @staticmethod
    def _dedupe_assets(items: list[ImmichAssetSummary]) -> list[ImmichAssetSummary]:
        return endpoints.dedupe_assets(items)

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
                    logger.warning("Error downloading from %s: %s", endpoint, redact_sensitive(exc))
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
            logger.warning("Thumbnail fallback failed for asset %s: %s", asset_id, redact_sensitive(exc))

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
            params = {"format": thumbnail_format}
            if size:
                params["size"] = size
            response = await client.get(
                path,
                params=params,
                headers=self._headers(json_type=False),
            )
            self._handle_response_errors(response, f"Immich thumbnail endpoint ({path}) failed")
            return response.content, response.headers.get("content-type")
        except Exception as exc:
            logger.debug("Immich thumbnail error for %s: %s", path, redact_sensitive(exc))
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
            logger.error("Thumbnail fallback to original failed for %s: %s", asset_id, redact_sensitive(fallback_exc))
            if last_error:
                raise last_error
            raise ImmichUnexpectedResponseError(
                f"Immich thumbnail not found and fallback failed: {redact_sensitive(fallback_exc)}"
            )

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
