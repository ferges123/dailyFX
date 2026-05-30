from app.immich.client import ImmichClient
from app.immich.errors import ImmichConfigurationError
from app.immich.models import ImmichAlbumSummary, ImmichAssetPage, ImmichPersonSummary, ImmichSearchFilters
from app.models.settings import SettingsModel
from app.security import decrypt_secret
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def get_or_create_settings(db: Session) -> SettingsModel:
    row = db.get(SettingsModel, 1)
    if row:
        return row
    row = SettingsModel(id=1)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        # Another request may have created the singleton row at the same time.
        db.rollback()
        row = db.get(SettingsModel, 1)
        if row is None:
            raise
        return row
    db.refresh(row)
    return row


def build_immich_client(row: SettingsModel) -> ImmichClient:
    if not row.immich_url:
        raise ImmichConfigurationError("Immich URL is not configured")
    api_key = decrypt_secret(row.encrypted_immich_api_key)
    if not api_key:
        raise ImmichConfigurationError("Immich API key is not configured")
    return ImmichClient(row.immich_url, api_key, timeout=30.0)


async def list_filter_options(row: SettingsModel) -> tuple[list[ImmichAlbumSummary], list[ImmichPersonSummary]]:
    client = build_immich_client(row)
    albums = await client.list_albums()
    people = await client.list_people()
    return albums, people


async def search_assets(row: SettingsModel, filters: ImmichSearchFilters) -> ImmichAssetPage:
    client = build_immich_client(row)
    return await client.search_assets(filters)


async def get_asset_thumbnail(row: SettingsModel, asset_id: str, size: str = "preview") -> tuple[bytes, str | None]:
    client = build_immich_client(row)
    return await client.get_asset_thumbnail(asset_id, size=size)
