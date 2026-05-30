from io import BytesIO

from PIL import Image, ImageOps

from app.immich.errors import ImmichUnexpectedResponseError


async def get_image_bytes(client, asset) -> bytes:
    """Try original, then thumbnail fallback. Always returns orientation-corrected JPEG."""
    try:
        raw = await client.get_asset_data(asset.id)
    except ImmichUnexpectedResponseError:
        raw, _ = await client.get_asset_thumbnail(asset.id, size="preview")
        if not raw:
            raise RuntimeError(f"Asset {asset.id} has no accessible image data")
    img = ImageOps.exif_transpose(Image.open(BytesIO(raw)))
    out = BytesIO()
    img.convert("RGB").save(out, format="JPEG", quality=92)
    return out.getvalue()
