import type { ImmichAssetExif } from '../api/types';

type JsonRecord = Record<string, unknown>;

function parseJsonRecord(value: string | null | undefined): JsonRecord | null {
  if (!value) return null;

  try {
    const parsed: unknown = JSON.parse(value);
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
      ? (parsed as JsonRecord)
      : null;
  } catch {
    return null;
  }
}

export function parseGenerationExif(
  configJson: string | null | undefined,
): ImmichAssetExif | null {
  const config = parseJsonRecord(configJson);
  const exif = config?.exif;
  return exif && typeof exif === 'object' && !Array.isArray(exif)
    ? (exif as ImmichAssetExif)
    : null;
}

export function parseFirstSourceAssetId(
  sourceAssetIds: string | null | undefined,
): string | null {
  if (!sourceAssetIds) return null;

  try {
    const parsed: unknown = JSON.parse(sourceAssetIds);
    const first = Array.isArray(parsed) ? parsed[0] : null;
    return typeof first === 'string' && first.length > 0 ? first : null;
  } catch {
    return null;
  }
}
