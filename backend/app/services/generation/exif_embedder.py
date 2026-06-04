"""EXIF metadata embedding for generated images."""

from fractions import Fraction
from io import BytesIO

from PIL import Image
from PIL.TiffImagePlugin import IFDRational

from app.immich.models import ImmichExifInfo

# EXIF tags
TAG_IMAGE_DESCRIPTION = 0x010E
TAG_SOFTWARE = 0x0131
TAG_DATETIME_ORIGINAL = 0x9003
TAG_MAKE = 0x010F
TAG_MODEL = 0x0110
TAG_LENS_MODEL = 0xA434
TAG_F_NUMBER = 0x829D
TAG_EXPOSURE_TIME = 0x829A
TAG_ISO = 0x8827
TAG_FOCAL_LENGTH = 0x920A
TAG_GPS_IFD = 0x8825

# GPS tags
GPS_LATITUDE_REF = 1
GPS_LATITUDE = 2
GPS_LONGITUDE_REF = 3
GPS_LONGITUDE = 4


def _degrees_to_dms(degrees: float) -> list[IFDRational]:
    """Convert decimal degrees to DMS (degrees, minutes, seconds) format."""
    d = int(abs(degrees))
    m = int((abs(degrees) - d) * 60)
    s = Fraction((abs(degrees) - d - m / 60) * 3600).limit_denominator(1_000_000)
    return [IFDRational(d), IFDRational(m), IFDRational(s)]


def _embed_camera_info(exif, exif_info: ImmichExifInfo) -> None:
    """Embed camera make, model, and lens info."""
    if make := exif_info.get("make"):
        exif[TAG_MAKE] = str(make)
    if model := exif_info.get("model"):
        exif[TAG_MODEL] = str(model)
    if lens := exif_info.get("lensModel"):
        exif[TAG_LENS_MODEL] = str(lens)


def _embed_exposure_info(exif, exif_info: ImmichExifInfo) -> None:
    """Embed exposure settings (f-number, shutter speed, focal length, ISO)."""
    for tag, key in [(TAG_F_NUMBER, "fNumber"), (TAG_EXPOSURE_TIME, "exposureTime"), (TAG_FOCAL_LENGTH, "focalLength")]:
        if (v := exif_info.get(key)) is not None:
            try:
                exif[tag] = float(v)
            except (TypeError, ValueError):
                pass

    if (iso := exif_info.get("iso")) is not None:
        try:
            exif[TAG_ISO] = int(iso)
        except (TypeError, ValueError):
            pass


def _embed_gps_info(exif, exif_info: ImmichExifInfo) -> None:
    """Embed GPS coordinates."""
    lat, lon = exif_info.get("latitude"), exif_info.get("longitude")
    if lat is None or lon is None:
        return

    try:
        lat, lon = float(lat), float(lon)
        gps = exif.get_ifd(TAG_GPS_IFD)
        gps[GPS_LATITUDE_REF] = "N" if lat >= 0 else "S"
        gps[GPS_LATITUDE] = _degrees_to_dms(lat)
        gps[GPS_LONGITUDE_REF] = "E" if lon >= 0 else "W"
        gps[GPS_LONGITUDE] = _degrees_to_dms(lon)
    except (TypeError, ValueError):
        pass


def embed_exif_metadata(image_bytes: bytes, asset, description: str, exif_info: ImmichExifInfo) -> bytes:
    """
    Embed EXIF metadata from source asset into generated image.

    Args:
        image_bytes: Generated image bytes
        asset: Source Immich asset (for datetime)
        description: Image description to embed
        exif_info: EXIF data from Immich API

    Returns:
        Image bytes with embedded EXIF metadata
    """
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    exif = img.getexif()

    # Basic metadata
    exif[TAG_SOFTWARE] = "dailyFX"
    exif[TAG_IMAGE_DESCRIPTION] = description

    if exif_info:
        _embed_camera_info(exif, exif_info)
        _embed_exposure_info(exif, exif_info)
        _embed_gps_info(exif, exif_info)

    out = BytesIO()
    img.save(out, format="PNG", exif=exif.tobytes())
    return out.getvalue()
