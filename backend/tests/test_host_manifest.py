import pytest
from app.services.generation.host_manifest import (
    validate_and_normalize_host_manifest,
    ManifestValidationError,
    HOST_METADATA_SOURCE,
)

def test_validation_empty_fields():
    # Empty title
    with pytest.raises(ManifestValidationError, match="updated title"):
        validate_and_normalize_host_manifest({
            "title": "   ",
            "summary": "Some summary",
            "tags": ["tag1", "tag2", "tag3"],
            "metadata_source": HOST_METADATA_SOURCE,
        })

    # Empty summary
    with pytest.raises(ManifestValidationError, match="updated summary"):
        validate_and_normalize_host_manifest({
            "title": "Some Title",
            "summary": "",
            "tags": ["tag1", "tag2", "tag3"],
            "metadata_source": HOST_METADATA_SOURCE,
        })

def test_validation_invalid_tags():
    # Tags is not a list
    with pytest.raises(ManifestValidationError, match="valid tags"):
        validate_and_normalize_host_manifest({
            "title": "Some Title",
            "summary": "Some summary",
            "tags": "tag1, tag2, tag3",
            "metadata_source": HOST_METADATA_SOURCE,
        })

    # Non-string tag
    with pytest.raises(ManifestValidationError, match="valid tags"):
        validate_and_normalize_host_manifest({
            "title": "Some Title",
            "summary": "Some summary",
            "tags": ["tag1", 123, "tag3"],
            "metadata_source": HOST_METADATA_SOURCE,
        })

    # Empty tag in list
    with pytest.raises(ManifestValidationError, match="valid tags"):
        validate_and_normalize_host_manifest({
            "title": "Some Title",
            "summary": "Some summary",
            "tags": ["tag1", "  ", "tag3"],
            "metadata_source": HOST_METADATA_SOURCE,
        })

    # Less than 3 tags
    with pytest.raises(ManifestValidationError, match="valid tags"):
        validate_and_normalize_host_manifest({
            "title": "Some Title",
            "summary": "Some summary",
            "tags": ["tag1", "tag2"],
            "metadata_source": HOST_METADATA_SOURCE,
        })

    # More than 6 tags
    with pytest.raises(ManifestValidationError, match="valid tags"):
        validate_and_normalize_host_manifest({
            "title": "Some Title",
            "summary": "Some summary",
            "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7"],
            "metadata_source": HOST_METADATA_SOURCE,
        })

def test_validation_metadata_source():
    # Missing metadata source
    with pytest.raises(ManifestValidationError, match="required metadata_source"):
        validate_and_normalize_host_manifest({
            "title": "Some Title",
            "summary": "Some summary",
            "tags": ["tag1", "tag2", "tag3"],
        })

    # Invalid metadata source
    with pytest.raises(ManifestValidationError, match="required metadata_source"):
        validate_and_normalize_host_manifest({
            "title": "Some Title",
            "summary": "Some summary",
            "tags": ["tag1", "tag2", "tag3"],
            "metadata_source": "invalid_source",
        })

def test_validation_unchanged_metadata():
    original = {
        "title": "Initial Title",
        "summary": "Initial Summary",
        "tags": ["tag1", "tag2", "tag3"],
    }

    # Everything identical -> raises validation error
    with pytest.raises(ManifestValidationError, match="did not update title, summary, or tags"):
        validate_and_normalize_host_manifest({
            "title": "  Initial Title  ",
            "summary": "Initial Summary",
            "tags": ["tag1", "tag2", "tag3"],
            "metadata_source": HOST_METADATA_SOURCE,
        }, original)

    # Title changed -> succeeds
    res1 = validate_and_normalize_host_manifest({
        "title": "New Title",
        "summary": "Initial Summary",
        "tags": ["tag1", "tag2", "tag3"],
        "metadata_source": HOST_METADATA_SOURCE,
    }, original)
    assert res1["title"] == "New Title"

    # Summary changed -> succeeds
    res2 = validate_and_normalize_host_manifest({
        "title": "Initial Title",
        "summary": "New Summary",
        "tags": ["tag1", "tag2", "tag3"],
        "metadata_source": HOST_METADATA_SOURCE,
    }, original)
    assert res2["summary"] == "New Summary"

    # Tags changed -> succeeds
    res3 = validate_and_normalize_host_manifest({
        "title": "Initial Title",
        "summary": "Initial Summary",
        "tags": ["tag1", "tag2", "tag4"],
        "metadata_source": HOST_METADATA_SOURCE,
    }, original)
    assert res3["tags"] == ["tag1", "tag2", "tag4"]

def test_normalization_behavior():
    manifest = {
        "title": "  Stripped Title  ",
        "summary": "  Stripped Summary\n",
        "tags": ["  t1  ", "  t2  ", "  t3  "],
        "metadata_source": " " + HOST_METADATA_SOURCE + " ",
        "custom_key": "custom_value",
    }
    normalized = validate_and_normalize_host_manifest(manifest)
    assert normalized["title"] == "Stripped Title"
    assert normalized["summary"] == "Stripped Summary"
    assert normalized["tags"] == ["t1", "t2", "t3"]
    assert normalized["metadata_source"] == HOST_METADATA_SOURCE
    assert normalized["custom_key"] == "custom_value"
