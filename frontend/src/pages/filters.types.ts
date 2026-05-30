import type { ImmichAssetSearchFilters, ImmichPersonFilter } from '../api/client';
import type { HistoryStatusFilter } from './history.types';

export type PersonFilterMode = ImmichPersonFilter['mode'];

export type AppStateCookie = {
  filters: ImmichAssetSearchFilters;
  filtersExpanded: boolean;
  albumSearch: string;
  personSearch: string;
  historySearch: string;
  historyStatus: HistoryStatusFilter;
  selectedPresetId: string | null;
};

export type FilterPreset = {
  id: string;
  name: string;
  filters: ImmichAssetSearchFilters;
  createdAt: string;
};

export const defaultFilters: ImmichAssetSearchFilters = {
  albumIds: [],
  personFilters: [],
  startDate: '',
  endDate: '',
  mediaType: 'all',
};

export const appStateCookieName = 'fx-dashboard-state-v1';
export const appStateCookieMaxAge = 60 * 60 * 24 * 365;
export const filterPresetsKey = 'fx-filter-presets-v1';
