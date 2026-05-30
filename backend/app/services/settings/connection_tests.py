from fastapi import HTTPException

from app.schemas.settings import ConnectionTestResponse
from app.security import decrypt_secret


def build_connection_test_response(
    provider: str,
    *,
    message: str | None = None,
    model: str | None = None,
    server_url: str | None = None,
    user_email: str | None = None,
    user_id: str | None = None,
    server_version: str | None = None,
) -> ConnectionTestResponse:
    return ConnectionTestResponse(
        ok=True,
        message=message or f"{provider} connection succeeded",
        provider=provider,
        model=model,
        server_url=server_url,
        user_email=user_email,
        user_id=user_id,
        server_version=server_version,
    )


def get_setting_api_key(row, encrypted_field: str, provider_name: str) -> str:
    api_key = decrypt_secret(getattr(row, encrypted_field))
    if not api_key:
        raise HTTPException(status_code=400, detail=f"{provider_name} API key is not configured")
    return api_key


def get_optional_setting_api_key(row, encrypted_field: str) -> str | None:
    return decrypt_secret(getattr(row, encrypted_field))


def build_http_headers(api_key: str | None, header_name: str, *, use_bearer: bool = True) -> dict[str, str]:
    if not api_key:
        return {}
    return {header_name: f"Bearer {api_key}" if use_bearer else api_key}


async def test_http_provider(
    url: str,
    headers: dict[str, str],
    provider: str,
) -> ConnectionTestResponse:
    import httpx

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=502, detail=f"{provider} request timed out") from exc
    except httpx.RequestError as exc:
        detail = f"Could not reach {provider}"
        if provider == "xiaomi":
            detail = f"Could not reach {provider}: {exc}"
        raise HTTPException(status_code=502, detail=detail) from exc

    if response.status_code in {401, 403}:
        raise HTTPException(status_code=401, detail=f"{provider} API key was rejected")
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"{provider} returned HTTP {response.status_code}")

    model: str | None = None
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if isinstance(payload, dict):
        model = payload.get("id") or payload.get("name")
    return ConnectionTestResponse(
        ok=True,
        message=f"{provider} connection succeeded",
        provider=provider,
        model=model,
    )


async def test_configured_http_provider(
    row,
    encrypted_field: str,
    provider: str,
    url: str,
    header_name: str,
    provider_name: str,
    use_bearer: bool = True,
) -> ConnectionTestResponse:
    api_key = get_setting_api_key(row, encrypted_field, provider_name)
    return await test_http_provider(url, build_http_headers(api_key, header_name, use_bearer=use_bearer), provider)


async def test_optional_configured_http_provider(
    row,
    encrypted_field: str,
    provider: str,
    url: str,
    header_name: str,
    provider_name: str,
    use_bearer: bool = True,
) -> ConnectionTestResponse:
    api_key = get_optional_setting_api_key(row, encrypted_field)
    if api_key is None:
        return await test_http_provider(url, {}, provider)
    return await test_http_provider(url, build_http_headers(api_key, header_name, use_bearer=use_bearer), provider)
