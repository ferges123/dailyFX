import { useState, useEffect, useRef } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Trash2, Pencil } from 'lucide-react';
import { InlineSpinner, ErrorBanner } from '../../components/ErrorUI';
import { EmptyState, InlineError, SectionCard } from '../../components/FormUI';
import {
  getFilterPresets,
  createFilterPreset,
  updateFilterPreset,
  deleteFilterPreset,
  getImmichFilterOptions,
  type FilterPreset,
  type ImmichPersonFilter,
  type ImmichFilterOptions,
} from '../../api/client';
import { Field, SelectField } from '../../components/Field';
import {
  MultiSelectPanel,
  PersonSelectPanel,
} from '../../components/FilterPanels';
import { PresetHeader, PresetFormActions, PresetActionRow } from './PresetHeader';

type FilterFormState = {
  name: string;
  album_ids: string[];
  person_filters: ImmichPersonFilter[];
  start_date: string | null;
  end_date: string | null;
  media_type: string;
};

function FilterPresetCard({
  preset,
  albumNames,
  personNames,
  onEdit,
  onDelete,
}: {
  preset: FilterPreset;
  albumNames: Map<string, string>;
  personNames: Map<string, string>;
  onEdit: (preset: FilterPreset) => void;
  onDelete: (id: number, name: string) => void;
}) {
  const albumsList = preset.album_ids
    .map((id) => ({ id, name: albumNames.get(id) ?? id }))
    .slice(0, 5);
  const peopleList = preset.person_filters
    .map((pf) => ({
      id: pf.personId,
      name: personNames.get(pf.personId) ?? pf.personId,
    }))
    .slice(0, 5);
  const tags: string[] = [];
  if (preset.media_type && preset.media_type !== 'photo')
    tags.push(preset.media_type);
  if (preset.start_date) tags.push(`from ${preset.start_date}`);
  if (preset.end_date) tags.push(`to ${preset.end_date}`);

  return (
    <div className="grid gap-2.5 md:gap-3 rounded-xl md:rounded-2xl border border-stone-200/80 bg-white/85 px-2.5 py-2.5 md:px-3 md:py-3 shadow-[0_8px_24px_rgba(36,29,16,0.04)] backdrop-blur-md sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start">
      <div className="min-w-0 grid gap-1.5 md:gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-semibold text-stone-900 truncate">
            {preset.name}
          </span>
          <span className="app-chip px-2 py-0.5 text-[10px]">
            {albumsList.length} album{albumsList.length === 1 ? '' : 's'}
          </span>
          <span className="app-chip px-2 py-0.5 text-[10px]">
            {peopleList.length} people
          </span>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {albumsList.map((item) => (
            <span
              key={item.id}
              className="app-chip px-2 py-0.5 text-[10px] font-medium"
            >
              📁 {item.name}
            </span>
          ))}
          {peopleList.map((item) => (
            <span
              key={item.id}
              className="app-chip px-2 py-0.5 text-[10px] font-medium"
            >
              👤 {item.name}
            </span>
          ))}
          {tags.map((t) => (
            <span
              key={t}
              className="app-chip px-2 py-0.5 text-[10px] font-medium"
            >
              {t}
            </span>
          ))}
        </div>
      </div>
      <PresetActionRow>
        <button
          type="button"
          onClick={() => onEdit(preset)}
          className="app-button-secondary w-full justify-center px-2.5 py-1.5 text-xs sm:w-auto"
        >
          <Pencil size={12} /> Edit
        </button>
        <button
          type="button"
          onClick={() => onDelete(preset.id, preset.name)}
          className="app-button-secondary w-full justify-center px-2.5 py-1.5 text-xs text-rose-700 sm:w-auto"
        >
          <Trash2 size={12} /> Delete
        </button>
      </PresetActionRow>
    </div>
  );
}

export function FilterPresetsTab() {
  const qc = useQueryClient();
  const presets = useQuery({
    queryKey: ['filter-presets'],
    queryFn: getFilterPresets,
  });
  const options = useQuery<ImmichFilterOptions>({
    queryKey: ['immich-filter-options'],
    queryFn: getImmichFilterOptions,
    staleTime: 1000 * 60 * 60, // 1 hour
    initialData: () => {
      try {
        const cached = localStorage.getItem('dailyfx_immich_filter_options');
        return cached ? (JSON.parse(cached) as ImmichFilterOptions) : undefined;
      } catch {
        return undefined;
      }
    },
  });

  useEffect(() => {
    if (options.data) {
      try {
        localStorage.setItem(
          'dailyfx_immich_filter_options',
          JSON.stringify(options.data),
        );
      } catch (err) {
        console.warn('Failed to cache Immich filter options:', err);
      }
    }
  }, [options.data]);

  const [editing, setEditing] = useState<FilterPreset | null>(null);
  const [isNew, setIsNew] = useState(false);
  const [form, setForm] = useState<FilterFormState>({
    name: '',
    album_ids: [],
    person_filters: [],
    start_date: null,
    end_date: null,
    media_type: 'photo',
  });
  const [albumSearch, setAlbumSearch] = useState('');
  const [personSearch, setPersonSearch] = useState('');
  const [error, setError] = useState<string | null>(null);
  const formPanelRef = useRef<HTMLDivElement | null>(null);

  const saveMutation = useMutation({
    mutationFn: () =>
      editing && !isNew
        ? updateFilterPreset(editing.id, form)
        : createFilterPreset(form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['filter-presets'] });
      closeForm();
    },
    onError: (e: Error) => setError(e.message),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteFilterPreset(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['filter-presets'] }),
    onError: (e: Error) => setError(e.message),
  });

  function openNew() {
    setForm({
      name: '',
      album_ids: [],
      person_filters: [],
      start_date: null,
      end_date: null,
      media_type: 'photo',
    });
    setAlbumSearch('');
    setPersonSearch('');
    setEditing(null);
    setIsNew(true);
    setError(null);
  }

  function openEdit(p: FilterPreset) {
    setForm({
      name: p.name,
      album_ids: p.album_ids,
      person_filters: p.person_filters as ImmichPersonFilter[],
      start_date: p.start_date,
      end_date: p.end_date,
      media_type: p.media_type,
    });
    setAlbumSearch('');
    setPersonSearch('');
    setEditing(p);
    setIsNew(false);
    setError(null);
  }

  function closeForm() {
    setAlbumSearch('');
    setPersonSearch('');
    setEditing(null);
    setIsNew(false);
    setError(null);
  }

  const albums = (options.data?.albums ?? []).filter((a) =>
    a.album_name.toLowerCase().includes(albumSearch.toLowerCase()),
  );
  const people = (options.data?.people ?? []).filter((p) =>
    p.name.toLowerCase().includes(personSearch.toLowerCase()),
  );

  const showForm = isNew || editing !== null;
  const isLoading = presets.isLoading && !presets.data;
  const isError = presets.isError && !presets.data;
  const validationIssues: string[] = [];
  if (!form.name.trim()) validationIssues.push('Preset name is required.');
  if (form.start_date && form.end_date && form.start_date > form.end_date) {
    validationIssues.push('From date must be earlier than To date.');
  }
  const canSave = validationIssues.length === 0;
  const selectedAlbumCount = form.album_ids.length;
  const selectedPersonCount = form.person_filters.length;

  useEffect(() => {
    if (!showForm) return;
    formPanelRef.current?.scrollIntoView?.({
      behavior: 'smooth',
      block: 'start',
    });
  }, [showForm, isNew, editing?.id]);

  if (isLoading) {
    return <InlineSpinner />;
  }

  if (isError) {
    const errorMsg = presets.error;
    return (
      <ErrorBanner
        title="Could not load filter presets"
        error={errorMsg}
        onRetry={() => {
          presets.refetch();
          options.refetch();
        }}
      />
    );
  }

  return (
    <div className="grid gap-3">
      {options.isError && (
        <ErrorBanner
          title="Filter options unavailable"
          error={options.error as Error | string | null}
          onRetry={() => options.refetch()}
        />
      )}

      <PresetHeader count={presets.data?.length ?? 0} onCreate={openNew} />

      {error && (
        <InlineError title="Could not save filter preset" message={error} />
      )}

      {showForm && (
        <div
          ref={formPanelRef}
          className="app-panel grid gap-3 p-3 md:gap-4 md:p-4"
        >
          <div className="grid gap-0.5 md:gap-1">
            <div className="text-sm font-semibold text-stone-900">
              {isNew ? 'New filter preset' : `Editing: ${editing?.name}`}
            </div>
            <div className="text-sm text-stone-500">
              Keep the core criteria visible while you fine-tune albums and
              people.
            </div>
          </div>
          {validationIssues.length > 0 && (
            <InlineError
              title="Fix the highlighted fields"
              message={validationIssues.join(' ')}
            />
          )}

          <SectionCard
            title="Basics"
            description="Set the name, media type, and optional date window."
          >
            <div className="grid gap-3">
              <div className="grid gap-3 sm:grid-cols-3">
                <Field
                  label="Name"
                  required
                  value={form.name}
                  maxLength={255}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, name: e.target.value }))
                  }
                />
                <SelectField
                  label="Media type"
                  value={form.media_type}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, media_type: e.target.value }))
                  }
                >
                  <option value="photo">Photos</option>
                  <option value="video">Videos</option>
                  <option value="all">All media</option>
                </SelectField>
                <div className="grid gap-1 rounded-xl border border-stone-200 bg-stone-50 px-3 py-2 text-xs text-stone-500">
                  <div className="font-semibold uppercase tracking-[0.18em] text-stone-500">
                    Date range
                  </div>
                  <div>
                    {form.start_date && form.end_date
                      ? `${form.start_date} to ${form.end_date}`
                      : form.start_date
                        ? `From ${form.start_date}`
                        : form.end_date
                          ? `Up to ${form.end_date}`
                          : 'No date limit'}
                  </div>
                </div>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <Field
                  label="From"
                  type="date"
                  value={form.start_date ?? ''}
                  onChange={(e) =>
                    setForm((f) => ({
                      ...f,
                      start_date: e.target.value || null,
                    }))
                  }
                  optional
                />
                <Field
                  label="To"
                  type="date"
                  value={form.end_date ?? ''}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, end_date: e.target.value || null }))
                  }
                  optional
                />
              </div>
            </div>
          </SectionCard>

          <SectionCard
            title="Albums"
            description="Choose one or more albums to include."
          >
            <MultiSelectPanel
              label="Albums"
              searchValue={albumSearch}
              onSearchChange={setAlbumSearch}
              options={albums.map((a) => ({
                id: a.id,
                label: `${a.album_name} (${a.asset_count})`,
              }))}
              selectedIds={form.album_ids}
              loading={options.isLoading}
              onToggle={(id) =>
                setForm((f) => ({
                  ...f,
                  album_ids: f.album_ids.includes(id)
                    ? f.album_ids.filter((x) => x !== id)
                    : [...f.album_ids, id],
                }))
              }
            />
          </SectionCard>

          <SectionCard
            title="People"
            description="Choose people and mark whether they are optional, required, or excluded."
          >
            <PersonSelectPanel
              label="People"
              searchValue={personSearch}
              onSearchChange={setPersonSearch}
              options={people.map((p) => ({
                id: p.id,
                label: `${p.name} (${p.asset_count})`,
              }))}
              selectedFilters={form.person_filters}
              loading={options.isLoading}
              onToggle={(id) =>
                setForm((f) => {
                  const exists = f.person_filters.some(
                    (p) => p.personId === id,
                  );
                  const next = exists
                    ? f.person_filters.filter((p) => p.personId !== id)
                    : [
                        ...f.person_filters,
                        { personId: id, mode: 'optional' as const },
                      ];
                  return { ...f, person_filters: next };
                })
              }
              onModeChange={(id, mode) =>
                setForm((f) => ({
                  ...f,
                  person_filters: f.person_filters.map((p) =>
                    p.personId === id
                      ? { ...p, mode: mode as ImmichPersonFilter['mode'] }
                      : p,
                  ),
                }))
              }
            />
          </SectionCard>

          <div className="flex flex-col gap-1.5 rounded-xl border border-stone-200 bg-white px-3 py-2 text-xs text-stone-500 sm:flex-row sm:items-center sm:justify-between">
            <span>
              {selectedAlbumCount} album(s) and {selectedPersonCount} people
              selected.
            </span>
            <span>Required fields are marked with an asterisk.</span>
          </div>

          <PresetFormActions
            onSave={() => saveMutation.mutate()}
            onCancel={closeForm}
            canSave={canSave}
            pending={saveMutation.isPending}
          />
        </div>
      )}

      <div aria-label="Filter presets list" className="grid gap-2 lg:grid-cols-2">
        {(() => {
          const albumNames = new Map(
            (options.data?.albums ?? []).map((a) => [a.id, a.album_name]),
          );
          const personNames = new Map(
            (options.data?.people ?? []).map((p) => [p.id, p.name]),
          );
          return presets.data?.map((p) => (
            <FilterPresetCard
              key={p.id}
              preset={p}
              albumNames={albumNames}
              personNames={personNames}
              onEdit={openEdit}
              onDelete={(id, name) => {
                if (confirm(`Delete "${name}"?`)) deleteMutation.mutate(id);
              }}
            />
          ));
        })()}
        {presets.data?.length === 0 && (
          <div className="xl:col-span-2">
            <EmptyState
              title="No filter presets yet"
              description="Create a filter preset to control which albums, people, and dates feed generation."
              action={
                <button
                  type="button"
                  onClick={openNew}
                  className="app-button-primary px-3 py-1.5 text-sm"
                >
                  <Plus size={14} /> New preset
                </button>
              }
            />
          </div>
        )}
      </div>
    </div>
  );
}

export function FilterPresetsPage() {
  return (
    <section className="grid gap-4">
      <div className="app-panel grid gap-4 p-4">
        <FilterPresetsTab />
      </div>
    </section>
  );
}
