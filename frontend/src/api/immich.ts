import { request, getApiUrl } from './base';
import { type ImmichFilterOptions, type ImmichAssetExif } from './types';

export function getImmichFilterOptions() {
  return request<ImmichFilterOptions>('/api/immich/options');
}

export function getImmichAssetThumbnailUrl(assetId: string, size = 'preview') {
  return getApiUrl(`/api/immich/assets/${assetId}/thumbnail?size=${size}`);
}

export function getImmichAssetExif(assetId: string) {
  return request<ImmichAssetExif>(`/api/immich/assets/${assetId}/exif`);
}

export function getImmichAssetDetailUrl(
  immichUrl: string | null | undefined,
  assetId: string | null | undefined,
) {
  if (!immichUrl || !assetId) return null;
  const base = immichUrl.replace(/\/$/, '');
  return `${base}/photos/${assetId}`;
}
