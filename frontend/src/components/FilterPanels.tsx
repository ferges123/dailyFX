import { Search } from 'lucide-react';
import { Field } from './Field';
import type { ImmichPersonFilter } from '../api/client';
import type { PersonFilterMode } from '../pages/filters.types';

export function MultiSelectPanel({ label, searchValue, onSearchChange, options, selectedIds, onToggle, loading }: {
  label: string; searchValue: string; onSearchChange: (v: string) => void;
  options: { id: string; label: string }[]; selectedIds: string[]; onToggle: (v: string) => void;
  loading?: boolean;
}) {
  // Always show selected items even if they don't match the search query
  const selectedNotInOptions = selectedIds
    .filter((id) => !options.some((o) => o.id === id))
    .map((id) => ({ id, label: id }));
  const visibleOptions = [...selectedNotInOptions, ...options];

  return (
    <div className="flex h-full flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <div className="text-sm font-medium text-stone-800">{label}</div>
        <div className="text-xs text-stone-500">{options.length} items{selectedIds.length > 0 ? ` · ${selectedIds.length} selected` : ''}</div>
      </div>
      <Field
        label="Search albums"
        value={searchValue}
        onChange={(e) => onSearchChange(e.target.value)}
        placeholder="Search albums"
        icon={<Search size={16} />}
      />
      <div className="flex-1 min-h-0 rounded-lg border border-stone-200 bg-stone-50 p-2">
        <div className="grid h-full max-h-80 gap-1 overflow-y-auto">
          {loading ? (
            <div className="flex h-full items-center justify-center py-12">
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-stone-200 border-t-emerald-700" />
              <span className="ml-2 text-sm text-stone-500">Loading albums...</span>
            </div>
          ) : visibleOptions.length > 0 ? visibleOptions.map((o) => (
            <label key={o.id} className="flex cursor-pointer items-start gap-2 rounded-md border border-transparent bg-white px-2 py-1.5 text-sm text-stone-800 hover:border-stone-200 hover:bg-stone-50">
              <input type="checkbox" checked={selectedIds.includes(o.id)} onChange={() => onToggle(o.id)} className="mt-0.5 h-4 w-4 accent-emerald-700" />
              <span className="min-w-0 truncate">{o.label}</span>
            </label>
          )) : <div className="px-2 py-1 text-sm text-stone-500">No options</div>}
        </div>
      </div>
    </div>
  );
}

export function PersonSelectPanel({ label, searchValue, onSearchChange, options, selectedFilters, onToggle, onModeChange, loading }: {
  label: string; searchValue: string; onSearchChange: (v: string) => void;
  options: { id: string; label: string }[]; selectedFilters: ImmichPersonFilter[];
  onToggle: (v: string) => void; onModeChange: (v: string, mode: PersonFilterMode) => void;
  loading?: boolean;
}) {
  const selectedModes = new Map(selectedFilters.map((e) => [e.personId, e.mode]));
  // Always show selected people even if they don't match the search query
  const selectedNotInOptions = selectedFilters
    .filter((f) => !options.some((o) => o.id === f.personId))
    .map((f) => ({ id: f.personId, label: f.personId }));
  const visibleOptions = [...selectedNotInOptions, ...options];
  return (
    <div className="flex h-full flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <div className="text-sm font-medium text-stone-800">{label}</div>
        <div className="text-xs text-stone-500">{options.length} items{selectedFilters.length > 0 ? ` · ${selectedFilters.length} selected` : ''}</div>
      </div>
      <Field
        label="Search people"
        value={searchValue}
        onChange={(e) => onSearchChange(e.target.value)}
        placeholder="Search people"
        icon={<Search size={16} />}
      />
      <div className="flex-1 min-h-0 rounded-lg border border-stone-200 bg-stone-50 p-2">
        <div className="grid h-full max-h-80 gap-1 overflow-y-auto">
          {loading ? (
            <div className="flex h-full items-center justify-center py-12">
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-stone-200 border-t-emerald-700" />
              <span className="ml-2 text-sm text-stone-500">Loading people...</span>
            </div>
          ) : visibleOptions.length > 0 ? visibleOptions.map((o) => {
            const isSelected = selectedModes.has(o.id);
            const mode = selectedModes.get(o.id) ?? 'optional';
            return (
              <div key={o.id} className="grid grid-cols-[auto_minmax(0,1fr)_120px] items-center gap-2 rounded-md border border-transparent bg-white px-2 py-1.5 text-sm text-stone-800 hover:border-stone-200 hover:bg-stone-50">
                <label className="flex items-center">
                  <input type="checkbox" checked={isSelected} onChange={() => onToggle(o.id)} className="h-4 w-4 accent-emerald-700" />
                </label>
                <span className="min-w-0 truncate">{o.label}</span>
                <select value={mode} onChange={(e) => onModeChange(o.id, e.target.value as PersonFilterMode)}
                  className="h-7 rounded-md border border-stone-300 bg-white px-2 text-xs outline-hidden focus:border-emerald-700">
                  <option value="optional">optional</option>
                  <option value="obligatory">obligatory</option>
                  <option value="exclude">exclude</option>
                </select>
              </div>
            );
          }) : <div className="px-2 py-1 text-sm text-stone-500">No options</div>}
        </div>
      </div>
    </div>
  );
}
