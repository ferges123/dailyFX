import { Search, Inbox } from 'lucide-react';
import { Field } from './Field';
import { InlineSpinner } from './ErrorUI';
import type { ImmichPersonFilter } from '../api/client';
import type { PersonFilterMode } from '../pages/people.types';

const PERSON_MODE_META: Record<
  PersonFilterMode,
  { label: string; activeClass: string }
> = {
  optional: {
    label: 'Optional',
    activeClass:
      'border-stone-300 bg-stone-100 text-stone-700 hover:border-stone-400',
  },
  obligatory: {
    label: 'Required',
    activeClass:
      'border-emerald-300 bg-emerald-50 text-emerald-800 hover:border-emerald-400',
  },
  exclude: {
    label: 'Exclude',
    activeClass: 'border-rose-300 bg-rose-50 text-rose-700 hover:border-rose-400',
  },
};

export function MultiSelectPanel({
  label,
  searchValue,
  onSearchChange,
  options,
  selectedIds,
  onToggle,
  loading,
  searchLabel,
  searchPlaceholder,
  emptyLabel = 'No options',
}: {
  label: string;
  searchValue: string;
  onSearchChange: (v: string) => void;
  options: { id: string; label: string }[];
  selectedIds: string[];
  onToggle: (v: string) => void;
  loading?: boolean;
  searchLabel?: string;
  searchPlaceholder?: string;
  emptyLabel?: string;
}) {
  const searchLabelText = searchLabel ?? `Search ${label.toLowerCase()}`;
  const placeholderText = searchPlaceholder ?? searchLabelText;
  // Always show selected items even if they don't match the search query
  const selectedNotInOptions = selectedIds
    .filter((id) => !options.some((o) => o.id === id))
    .map((id) => ({ id, label: id }));
  const visibleOptions = [...selectedNotInOptions, ...options];

  return (
    <div className="flex h-full flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <div className="text-sm font-semibold text-stone-800">{label}</div>
        <div className="text-xs text-stone-500">
          {options.length} items
          {selectedIds.length > 0 ? ` · ${selectedIds.length} selected` : ''}
        </div>
      </div>
      <Field
        label={searchLabelText}
        value={searchValue}
        onChange={(e) => onSearchChange(e.target.value)}
        placeholder={placeholderText}
        icon={<Search size={16} />}
      />
      <div className="app-panel-soft flex-1 min-h-0 p-2">
        <div className="grid h-full max-h-80 gap-1 overflow-y-auto">
          {loading ? (
            <InlineSpinner />
          ) : visibleOptions.length > 0 ? (
            visibleOptions.map((o) => {
              const isSelected = selectedIds.includes(o.id);
              return (
                <label
                  key={o.id}
                  className={`flex cursor-pointer items-start gap-2 rounded-md border px-2 py-1.5 text-sm transition ${
                    isSelected
                      ? 'border-emerald-200 bg-emerald-50/60 text-stone-900'
                      : 'border-transparent bg-white text-stone-800 hover:border-stone-200 hover:bg-stone-50'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => onToggle(o.id)}
                    className="mt-0.5 h-4 w-4 accent-emerald-700"
                  />
                  <span className="min-w-0 truncate">{o.label}</span>
                </label>
              );
            })
          ) : (
            <div className="flex flex-col items-center justify-center gap-1.5 py-8 text-center">
              <Inbox size={18} className="text-stone-300" />
              <span className="text-xs text-stone-500">{emptyLabel}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function PersonSelectPanel({
  label,
  searchValue,
  onSearchChange,
  options,
  selectedFilters,
  onToggle,
  onModeChange,
  loading,
  searchLabel,
  searchPlaceholder,
  emptyLabel = 'No people available',
}: {
  label: string;
  searchValue: string;
  onSearchChange: (v: string) => void;
  options: { id: string; label: string }[];
  selectedFilters: ImmichPersonFilter[];
  onToggle: (v: string) => void;
  onModeChange: (v: string, mode: PersonFilterMode) => void;
  loading?: boolean;
  searchLabel?: string;
  searchPlaceholder?: string;
  emptyLabel?: string;
}) {
  const searchLabelText = searchLabel ?? `Search ${label.toLowerCase()}`;
  const placeholderText = searchPlaceholder ?? searchLabelText;
  const selectedModes = new Map(
    selectedFilters.map((e) => [e.personId, e.mode]),
  );
  // Always show selected people even if they don't match the search query
  const selectedNotInOptions = selectedFilters
    .filter((f) => !options.some((o) => o.id === f.personId))
    .map((f) => ({ id: f.personId, label: f.personId }));
  const visibleOptions = [...selectedNotInOptions, ...options];
  return (
    <div className="flex h-full flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <div className="text-sm font-semibold text-stone-800">{label}</div>
        <div className="text-xs text-stone-500">
          {options.length} items
          {selectedFilters.length > 0
            ? ` · ${selectedFilters.length} selected`
            : ''}
        </div>
      </div>
      <Field
        label={searchLabelText}
        value={searchValue}
        onChange={(e) => onSearchChange(e.target.value)}
        placeholder={placeholderText}
        icon={<Search size={16} />}
      />
      <div className="app-panel-soft flex-1 min-h-0 p-2">
        <div className="grid h-full max-h-80 gap-1 overflow-y-auto">
          {loading ? (
            <InlineSpinner />
          ) : visibleOptions.length > 0 ? (
            visibleOptions.map((o) => {
              const isSelected = selectedModes.has(o.id);
              const mode = selectedModes.get(o.id) ?? 'optional';
              return (
                <div
                  key={o.id}
                  className={`rounded-md border px-2 py-1.5 text-sm transition ${
                    isSelected
                      ? 'border-emerald-200 bg-emerald-50/40'
                      : 'border-transparent bg-white hover:border-stone-200 hover:bg-stone-50'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <label className="flex min-w-0 flex-1 cursor-pointer items-center gap-2">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => onToggle(o.id)}
                        className="h-4 w-4 shrink-0 accent-emerald-700"
                      />
                      <span className="min-w-0 truncate text-stone-800">
                        {o.label}
                      </span>
                    </label>
                    {isSelected ? (
                      <div
                        role="group"
                        aria-label={`Filter mode for ${o.label}`}
                        className="flex shrink-0 gap-1"
                      >
                        {(Object.keys(PERSON_MODE_META) as PersonFilterMode[]).map(
                          (m) => {
                            const meta = PERSON_MODE_META[m];
                            const active = mode === m;
                            return (
                              <button
                                key={m}
                                type="button"
                                onClick={() => onModeChange(o.id, m)}
                                aria-pressed={active}
                                className={`inline-flex h-6 items-center rounded-md border px-1.5 text-[10px] font-bold uppercase tracking-wide transition ${
                                  active
                                    ? meta.activeClass
                                    : 'border-transparent bg-transparent text-stone-400 hover:bg-stone-100 hover:text-stone-600'
                                }`}
                              >
                                {meta.label}
                              </button>
                            );
                          },
                        )}
                      </div>
                    ) : null}
                  </div>
                </div>
              );
            })
          ) : (
            <div className="flex flex-col items-center justify-center gap-1.5 py-8 text-center">
              <Inbox size={18} className="text-stone-300" />
              <span className="text-xs text-stone-500">{emptyLabel}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
