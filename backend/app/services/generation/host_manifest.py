HOST_METADATA_SOURCE = "host_agent_final_vision"


class ManifestValidationError(ValueError):
    pass


def validate_and_normalize_host_manifest(
    manifest: dict[str, object], original_manifest: dict[str, object] | None = None
) -> dict[str, object]:
    if not isinstance(manifest, dict):
        raise ManifestValidationError("Host manifest is not a JSON object")

    normalized = dict(manifest)

    title = str(normalized.get("title") or "").strip()
    summary = str(normalized.get("summary") or "").strip()
    tags = normalized.get("tags")
    metadata_source = str(normalized.get("metadata_source") or "").strip()

    if not title:
        raise ManifestValidationError("Host manifest did not include an updated title")
    if not summary:
        raise ManifestValidationError("Host manifest did not include an updated summary")
    if not isinstance(tags, list):
        raise ManifestValidationError("Host manifest did not include valid tags")

    normalized_tags = []
    for tag in tags:
        if not isinstance(tag, str):
            raise ManifestValidationError("Host manifest did not include valid tags")
        tag_text = tag.strip()
        if not tag_text:
            raise ManifestValidationError("Host manifest did not include valid tags")
        normalized_tags.append(tag_text)

    if not 3 <= len(normalized_tags) <= 6:
        raise ManifestValidationError("Host manifest did not include valid tags")

    if metadata_source != HOST_METADATA_SOURCE:
        raise ManifestValidationError("Host manifest did not include the required metadata_source")

    normalized["title"] = title
    normalized["summary"] = summary
    normalized["tags"] = normalized_tags
    normalized["metadata_source"] = metadata_source

    if isinstance(original_manifest, dict):
        original_title = str(original_manifest.get("title") or "").strip()
        original_summary = str(original_manifest.get("summary") or "").strip()
        original_tags_raw = original_manifest.get("tags")
        original_tags = []
        if isinstance(original_tags_raw, list):
            for tag in original_tags_raw:
                if isinstance(tag, str):
                    tag_text = tag.strip()
                    if tag_text:
                        original_tags.append(tag_text)
        if title == original_title and summary == original_summary and normalized_tags == original_tags:
            raise ManifestValidationError("Host agent did not update title, summary, or tags")

    return normalized
