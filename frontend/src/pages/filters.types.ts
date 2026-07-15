import type {
  ImmichPersonFilter,
} from '../api/client';

export type PersonFilterMode = ImmichPersonFilter['mode'];

export type FilterPreset = {
  id: string;
  name: string;
  filters: import('../api/client').ImmichAssetSearchFilters;
  createdAt: string;
};
