import { request, getApiUrl } from './base';
import {
  type ImmichFilterOptions,
  type ImmichAssetExif,
  type ImmichAssetPage,
  type ImmichAlbumPage,
} from './types';

export function getImmichFilterOptions() {
  return request<ImmichFilterOptions>('/api/immich/options');
}

export function getImmichAlbums(params: { page: number; size: number }) {
  const qs = new URLSearchParams({
    page: params.page.toString(),
    size: params.size.toString(),
  }).toString();
  return request<ImmichAlbumPage>(`/api/immich/albums?${qs}`);
}

export function getImmichAssets(filters?: {
  mediaType?: 'all' | 'photo' | 'video';
  albumIds?: string[];
  page?: number;
  size?: number;
}) {
  const params = new URLSearchParams();
  if (filters?.mediaType) {
    params.set('media_type', filters.mediaType);
  }
  if (filters?.page) {
    params.set('page', filters.page.toString());
  }
  if (filters?.size) {
    params.set('size', filters.size.toString());
  }
  if (filters?.albumIds) {
    filters.albumIds.forEach((id) => params.append('album_ids', id));
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
