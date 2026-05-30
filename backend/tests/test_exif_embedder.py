"""Tests for EXIF embedder module."""
import pytest
from io import BytesIO
from PIL import Image

from app.services.generation.exif_embedder import (
    embed_exif_metadata,
    _degrees_to_dms,
    _embed_camera_info,
    _embed_exposure_info,
    _embed_gps_info,
)


@pytest.fixture
def sample_image_bytes():
    """Create a simple test image."""
    img = Image.new("RGB", (100, 100), color="red")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def sample_exif_info():
    """Sample EXIF data from Immich."""
    return {
        "make": "Canon",
        "model": "EOS R5",
        "lensModel": "RF 24-70mm F2.8",
        "fNumber": 2.8,
        "exposureTime": 0.004,
        "focalLength": 50.0,
        "iso": 400,
        "latitude": 52.5200,
        "longitude": 13.4050,
    }


class TestDegreesToDms:
    """Tests for GPS coordinate conversion."""

    def test_positive_latitude(self):
        result = _degrees_to_dms(52.5200)
        assert len(result) == 3
        assert result[0] == 52
        assert result[1] == 31

    def test_negative_longitude(self):
        result = _degrees_to_dms(-13.4050)
        assert len(result) == 3
        assert result[0] == 13

    def test_zero(self):
        result = _degrees_to_dms(0.0)
        assert result[0] == 0
        assert result[1] == 0


class TestEmbedExifMetadata:
    """Tests for main EXIF embedding function."""

    def test_embed_basic_metadata(self, sample_image_bytes):
        """Test embedding basic description and software tag."""
        result = embed_exif_metadata(
            sample_image_bytes,
            asset=None,
            description="Test image",
            exif_info={}
        )
        
        assert isinstance(result, bytes)
        assert len(result) > 0
        
        # Verify it's a valid image
        img = Image.open(BytesIO(result))
        exif = img.getexif()
        assert exif[0x010E] == "Test image"  # TAG_IMAGE_DESCRIPTION
        assert exif[0x0131] == "dailyFX"    # TAG_SOFTWARE

    def test_embed_camera_info(self, sample_image_bytes, sample_exif_info):
        """Test embedding camera make, model, and lens."""
        result = embed_exif_metadata(
            sample_image_bytes,
            asset=None,
            description="Test",
            exif_info=sample_exif_info
        )
        
        img = Image.open(BytesIO(result))
        exif = img.getexif()
        assert exif[0x010F] == "Canon"              # TAG_MAKE
        assert exif[0x0110] == "EOS R5"             # TAG_MODEL
        assert exif[0xA434] == "RF 24-70mm F2.8"    # TAG_LENS_MODEL

    def test_embed_exposure_info(self, sample_image_bytes, sample_exif_info):
        """Test embedding exposure settings."""
        result = embed_exif_metadata(
            sample_image_bytes,
            asset=None,
            description="Test",
            exif_info=sample_exif_info
        )
        
        img = Image.open(BytesIO(result))
        exif = img.getexif()
        assert exif[0x829D] == 2.8      # TAG_F_NUMBER
        assert exif[0x829A] == 0.004    # TAG_EXPOSURE_TIME
        assert exif[0x920A] == 50.0     # TAG_FOCAL_LENGTH
        assert exif[0x8827] == 400      # TAG_ISO

    def test_embed_gps_info(self, sample_image_bytes, sample_exif_info):
        """Test embedding GPS coordinates."""
        result = embed_exif_metadata(
            sample_image_bytes,
            asset=None,
            description="Test",
            exif_info=sample_exif_info
        )
        
        img = Image.open(BytesIO(result))
        exif = img.getexif()
        gps = exif.get_ifd(0x8825)  # TAG_GPS_IFD
        
        assert gps[1] == "N"  # GPS_LATITUDE_REF (positive)
        assert len(gps[2]) == 3  # GPS_LATITUDE (degrees, minutes, seconds)
        assert gps[3] == "E"  # GPS_LONGITUDE_REF (positive)
        assert len(gps[4]) == 3  # GPS_LONGITUDE

    def test_embed_with_missing_fields(self, sample_image_bytes):
        """Test handling of missing EXIF fields."""
        partial_exif = {"make": "Canon"}
        
        result = embed_exif_metadata(
            sample_image_bytes,
            asset=None,
            description="Test",
            exif_info=partial_exif
        )
        
        img = Image.open(BytesIO(result))
        exif = img.getexif()
        assert exif[0x010F] == "Canon"  # TAG_MAKE exists
        assert 0x0110 not in exif       # TAG_MODEL missing

    def test_embed_with_invalid_values(self, sample_image_bytes):
        """Test handling of invalid EXIF values."""
        invalid_exif = {
            "fNumber": "invalid",
            "iso": "not_a_number",
            "latitude": "invalid",
        }
        
        # Should not raise exception
        result = embed_exif_metadata(
            sample_image_bytes,
            asset=None,
            description="Test",
            exif_info=invalid_exif
        )
        
        assert isinstance(result, bytes)
        img = Image.open(BytesIO(result))
        assert img.format == "PNG"

    def test_embed_with_empty_exif(self, sample_image_bytes):
        """Test with empty EXIF info."""
        result = embed_exif_metadata(
            sample_image_bytes,
            asset=None,
            description="Test",
            exif_info={}
        )
        
        img = Image.open(BytesIO(result))
        exif = img.getexif()
        assert exif[0x0131] == "dailyFX"  # Software tag always present
