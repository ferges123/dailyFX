import { request, getApiUrl } from './base';
import { type ImmichFilterOptions, type ImmichAssetExif, type ImmichAssetPage } from './types';

export function getImmichFilterOptions() {
  return request<ImmichFilterOptions>('/api/immich/options');
}

export function getImmichAssets(filters?: { mediaType?: 'all' | 'photo' | 'video' }) {
  const params = new URLSearchParams();
  if (filters?.mediaType) {
    params.set('media_type', filters.mediaType);
  }
  const qs = params.toString();
  return request<ImmichAssetPage>(`/api/immich/assets${qs ? `?${qs}` : ''}`);
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
