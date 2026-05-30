import type { ImmichAssetSearchFilters, ImmichPersonFilter } from '../api/client';
import { appStateCookieMaxAge, appStateCookieName, filterPresetsKey } from './filters.types';
import type { AppStateCookie, FilterPreset } from './filters.types';

export function normalizePersonFilters(candidate: Partial<ImmichAssetSearchFilters> | null | undefined): ImmichPersonFilter[] {
  const rawFilters = Array.isArray(candidate?.personFilters) ? candidate.personFilters : [];
  const normalized = rawFilters
    .map((item) => {
      if (!item || typeof item !== 'object') return null;
      const personId = typeof item.personId === 'string' && item.personId.length > 0 ? item.personId : null;
      const mode = item.mode === 'obligatory' || item.mode === 'exclude' || item.mode === 'optional' ? item.mode : 'optional';
      return personId ? { personId, mode } : null;
    })
    .filter((item): item is ImmichPersonFilter => item !== null);

  if (normalized.length > 0) return normalized;

  const legacyCandidate = candidate as Partial<ImmichAssetSearchFilters> & { personIds?: unknown; personMode?: unknown };
  const legacyPersonIds = Array.isArray(legacyCandidate?.personIds)
    ? legacyCandidate.personIds.filter((v): v is string => typeof v === 'string' && v.length > 0)
    : [];
  const legacyMode = legacyCandidate?.personMode === 'obligatory' || legacyCandidate?.personMode === 'exclude' || legacyCandidate?.personMode === 'optional'
    ? legacyCandidate.personMode : 'optional';
  return legacyPersonIds.map((personId) => ({ personId, mode: legacyMode }));
}

export function normalizeFilters(candidate: Partial<ImmichAssetSearchFilters> | null | undefined): ImmichAssetSearchFilters {
  return {
    albumIds: Array.isArray(candidate?.albumIds) ? candidate.albumIds.filter(Boolean) : [],
    personFilters: normalizePersonFilters(candidate),
    startDate: typeof candidate?.startDate === 'string' && candidate.startDate.length > 0 ? candidate.startDate : '',
    endDate: typeof candidate?.endDate === 'string' && candidate.endDate.length > 0 ? candidate.endDate : '',
    mediaType: candidate?.mediaType === 'photo' || candidate?.mediaType === 'video' || candidate?.mediaType === 'all' ? candidate.mediaType : 'all',
  };
}

export function readAppStateCookie(): Partial<AppStateCookie> | null {
  if (typeof document === 'undefined') return null;
  const prefix = `${appStateCookieName}=`;
  const cookie = document.cookie.split('; ').find((e) => e.startsWith(prefix));
  if (!cookie) return null;
  try {
    return JSON.parse(decodeURIComponent(cookie.slice(prefix.length))) as Partial<AppStateCookie>;
  } catch {
    return null;
  }
}

export function writeAppStateCookie(state: AppStateCookie): void {
  if (typeof document === 'undefined') return;
  document.cookie = `${appStateCookieName}=${encodeURIComponent(JSON.stringify(state))}; Path=/; Max-Age=${appStateCookieMaxAge}; SameSite=Lax`;
}

export function readFilterPresets(): FilterPreset[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(filterPresetsKey);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed
      .map((item) => {
        if (!item || typeof item !== 'object') return null;
        const c = item as Partial<FilterPreset>;
        if (typeof c.id !== 'string' || typeof c.name !== 'string' || typeof c.createdAt !== 'string') return null;
        return { id: c.id, name: c.name, createdAt: c.createdAt, filters: normalizeFilters(c.filters) };
      })
      .filter((item): item is FilterPreset => item !== null);
  } catch {
    return [];
  }
}

export function writeFilterPresets(presets: FilterPreset[]): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(filterPresetsKey, JSON.stringify(presets));
}
