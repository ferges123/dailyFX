import type {
  ImmichPersonFilter,
} from '../api/client';

export type PersonFilterMode = ImmichPersonFilter['mode'];

export type PeoplePreset = {
  id: string;
  name: string;
  filters: import('../api/client').ImmichAssetSearchFilters;
  createdAt: string;
};
