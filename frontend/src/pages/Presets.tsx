import { useState, useEffect, Fragment, type ReactNode } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Bell,
  BellOff,
  Monitor,
  Plus,
  Trash2,
  Pencil,
  Check,
  X,
  Smartphone,
  Eye,
} from 'lucide-react';
import { InlineSpinner, ErrorBanner } from '../components/ErrorUI';
import { EmptyState, InlineError, SectionCard } from '../components/FormUI';
import {
  getFilterPresets,
  createFilterPreset,
  updateFilterPreset,
  deleteFilterPreset,
  getEffectPresets,
  createEffectPreset,
  updateEffectPreset,
  deleteEffectPreset,
  getNotificationPresets,
  createNotificationPreset,
  updateNotificationPreset,
  deleteNotificationPreset,
  testNotificationPreset,
  testPushSubscription,
  getImmichFilterOptions,
  getGenerationModules,
  getGenerationExamples,
  getVapidPublicKey,
  subscribeWebPush,
  unsubscribeWebPush,
  getPushSubscriptions,
  deletePushSubscription,
  formatNotificationProviders,
  splitNotificationProviders,
  type FilterPreset,
  type EffectPreset,
  type NotificationPreset,
  type ImmichPersonFilter,
  type ImmichFilterOptions,
  type GenerationModuleInfo,
} from '../api/client';
import { Field, SelectField } from '../components/Field';
import {
  MultiSelectPanel,
  PersonSelectPanel,
} from '../components/FilterPanels';
import { FilterRow, ModuleConfigEditor } from '../components/EffectsComponents';
import {
  createDefaultModificationGroups,
  parseModificationGroups,
} from './automation.utils';
import { type ModificationGroupsConfig } from './automation.types';

// ── Filter Presets Tab ────────────────────────────────────────────────────────

type FilterFormState = {
  name: string;
  album_ids: string[];
  person_filters: ImmichPersonFilter[];
  start_date: string | null;
  end_date: string | null;
  media_type: string;
};

function PresetHeader({
  count,
  onCreate,
  buttonLabel = 'New preset',
}: {
  count: number;
  onCreate: () => void;
  buttonLabel?: string;
}) {
  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
      <span className="text-sm text-stone-500">{count} preset(s)</span>
      <button
        type="button"
        onClick={onCreate}
        className="app-button-primary w-full justify-center px-3 py-2 text-sm sm:w-auto sm:py-1.5"
      >
        <Plus size={14} /> {buttonLabel}
      </button>
    </div>
  );
}

function PresetFormActions({
  onSave,
  onCancel,
  canSave,
  pending,
  saveLabel = 'Save',
}: {
  onSave: () => void;
  onCancel: () => void;
  canSave: boolean;
  pending: boolean;
  saveLabel?: string;
}) {
  return (
    <div className="flex flex-col gap-2 sm:flex-row">
      <button
        type="button"
        onClick={onSave}
        disabled={!canSave || pending}
        className="app-button-primary w-full justify-center px-3 py-2 text-sm disabled:opacity-50 sm:w-auto"
      >
        <Check size={14} /> {saveLabel}
      </button>
      <button
        type="button"
        onClick={onCancel}
        className="app-button-secondary w-full justify-center px-3 py-2 text-sm sm:w-auto"
      >
        <X size={14} /> Cancel
      </button>
    </div>
  );
}

function PresetActionRow({ children }: { children: ReactNode }) {
  return (
    <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row sm:flex-wrap sm:gap-1.5 sm:shrink-0 sm:items-center">
      {children}
    </div>
  );
}

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

function NotificationPresetCard({
  preset,
  testResult,
  testingId,
  onTest,
  onEdit,
  onDelete,
}: {
  preset: NotificationPreset;
  testResult: { id: number; msg: string; ok: boolean } | null;
  testingId: number | null;
  onTest: (id: number) => void;
  onEdit: (preset: NotificationPreset) => void;
  onDelete: (id: number, name: string) => void;
}) {
  return (
    <div className="flex flex-col gap-2.5 md:gap-3 rounded-xl md:rounded-2xl border border-stone-200/80 bg-white/85 px-2.5 py-2.5 md:px-3 md:py-3 shadow-[0_8px_24px_rgba(36,29,16,0.04)] backdrop-blur-md sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0 grid gap-1">
        <div className="text-sm font-semibold text-stone-900">
          {preset.name}
        </div>
        <div className="flex flex-wrap gap-1.5">
          <span className="app-chip px-2 py-0.5 text-[11px]">
            {formatNotificationProviders(preset.provider)}
          </span>
          {preset.has_token && (
            <span className="app-chip border-emerald-100 bg-emerald-50 px-2 py-0.5 text-[11px] text-emerald-700">
              token set
            </span>
          )}
        </div>
      </div>
      <PresetActionRow>
        <button
          type="button"
          onClick={() => onTest(preset.id)}
          disabled={testingId === preset.id}
          className="app-button-secondary w-full justify-center px-2.5 py-1.5 text-xs text-blue-700 disabled:opacity-50 sm:w-auto"
        >
          <Bell size={12} /> Test
        </button>
        {testResult?.id === preset.id && (
          <span
            className={`w-full text-xs sm:w-auto ${testResult.ok ? 'text-emerald-700' : 'text-red-600'}`}
          >
            {testResult.msg}
          </span>
        )}
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

type EffectModuleLike = GenerationModuleInfo;

type EffectGroupLike = {
  enabled: boolean;
  weight: number;
  config: Record<string, unknown>;
};

type EffectExampleLike = {
  image_url: string;
  title: string;
  summary: string;
};

function EffectPresetTableItem({
  mod,
  group,
  exampleInfo,
  isExpanded,
  onTogglePreview,
  onEnabledChange,
  onWeightChange,
  onConfigChange,
}: {
  mod: EffectModuleLike;
  group: EffectGroupLike;
  exampleInfo?: EffectExampleLike | null;
  isExpanded: boolean;
  onTogglePreview: () => void;
  onEnabledChange: (enabled: boolean) => void;
  onWeightChange: (weight: number) => void;
  onConfigChange: (key: string, value: unknown) => void;
}) {
  return (
    <Fragment>
      <FilterRow
        title={
          <div className="grid gap-0.5">
            <div className="flex items-center gap-1.5 font-semibold text-stone-800 text-sm leading-snug">
              <span>{mod.label}</span>
              {!!exampleInfo && (
                <button
                  type="button"
                  onClick={onTogglePreview}
                  title="Toggle preview image"
                  className={`inline-flex items-center justify-center rounded-md p-1 transition-colors ${
                    isExpanded
                      ? 'text-emerald-700 bg-emerald-50 hover:bg-emerald-100'
                      : 'text-stone-400 hover:text-stone-600'
                  }`}
                >
                  <Eye size={13} />
                </button>
              )}
            </div>
            <div className="text-[11px] font-normal leading-normal text-stone-500">
              {mod.description}
            </div>
          </div>
        }
        icon={null}
        enabled={group.enabled}
        weight={group.weight}
        onEnabledChange={onEnabledChange}
        onWeightChange={onWeightChange}
        config={
          (mod.config_schema?.length ?? 0) > 0 ? (
            <ModuleConfigEditor
              module={mod}
              config={group.config}
              onChange={onConfigChange}
            />
          ) : null
        }
      />
      {isExpanded && exampleInfo && (
        <tr className="bg-stone-50/30">
          <td colSpan={4} className="border-t border-stone-200 px-3 py-3">
            <div className="flex max-w-2xl flex-col items-start gap-4 rounded-2xl border border-stone-200 bg-white p-3 shadow-[0_8px_24px_rgba(36,29,16,0.04)] sm:flex-row">
              <div className="shrink-0 max-w-full">
                <img
                  src={exampleInfo.image_url}
                  alt={mod.label}
                  className="w-full rounded-lg border border-stone-200 shadow-xs sm:w-64"
                  loading="lazy"
                />
              </div>
              <div className="grid gap-1 min-w-0">
                <div className="text-[10px] font-bold uppercase tracking-wide text-stone-400">
                  Example Result
                </div>
                <div className="text-sm font-semibold text-stone-800 truncate">
                  {exampleInfo.title}
                </div>
                <div className="text-xs text-stone-600 leading-relaxed">
                  {exampleInfo.summary}
                </div>
              </div>
            </div>
          </td>
        </tr>
      )}
    </Fragment>
  );
}

function EffectPresetMobileCard({
  mod,
  group,
  exampleInfo,
  isExpanded,
  onTogglePreview,
  onEnabledChange,
  onWeightChange,
  onConfigChange,
}: {
  mod: EffectModuleLike;
  group: EffectGroupLike;
  exampleInfo?: EffectExampleLike | null;
  isExpanded: boolean;
  onTogglePreview: () => void;
  onEnabledChange: (enabled: boolean) => void;
  onWeightChange: (weight: number) => void;
  onConfigChange: (key: string, value: unknown) => void;
}) {
  return (
    <div
      className={`grid gap-2.5 rounded-xl md:rounded-2xl border p-2.5 md:p-3 shadow-[0_8px_24px_rgba(36,29,16,0.04)] backdrop-blur-md transition ${
        group.enabled
          ? 'border-emerald-200 bg-emerald-50/20'
          : 'border-stone-200/80 bg-white/90'
      }`}
    >
      <div className="grid gap-2 xl:grid-cols-2">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5 text-sm font-semibold text-stone-900">
              <span>{mod.label}</span>
              <span
                className={`app-chip px-1.5 py-0.5 text-[9px] ${group.enabled ? 'border-emerald-100 bg-emerald-50 text-emerald-800' : ''}`}
              >
                {group.enabled ? 'On' : 'Off'}
              </span>
            </div>
            <div className="mt-0.5 text-[11px] leading-snug text-stone-500">
              {mod.description}
            </div>
          </div>
          {!!exampleInfo && (
            <button
              type="button"
              onClick={onTogglePreview}
              className={`inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-xl border transition-colors ${
                isExpanded
                  ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                  : 'border-stone-200 bg-white text-stone-400 hover:text-stone-600'
              }`}
            >
              <Eye size={14} />
            </button>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2 md:gap-3">
          <label className="flex items-center gap-1.5 md:gap-2 rounded-xl border border-stone-200 bg-white/80 px-2 md:px-2.5 py-1 md:py-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-stone-500">
            <input
              type="checkbox"
              checked={group.enabled}
              onChange={(e) => onEnabledChange(e.target.checked)}
              className="h-4 w-4 rounded-sm border-stone-300 accent-emerald-700"
            />
            Enable
          </label>
          <label className="flex items-center gap-1.5 md:gap-2 rounded-xl border border-stone-200 bg-white/80 px-2 md:px-2.5 py-1 md:py-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-stone-500">
            <span>Weight</span>
            <input
              type="number"
              min={0}
              value={group.weight}
              onChange={(e) => onWeightChange(Number(e.target.value) || 0)}
              className="app-control h-7 w-12 px-2 py-0.5 text-center text-xs"
            />
          </label>
        </div>
      </div>

      {(mod.config_schema?.length ?? 0) > 0 && (
        <div className="border-t border-stone-100 pt-1.5 text-xs">
          <div className="mb-1.5 text-[10px] font-bold uppercase tracking-wider text-stone-400">
            Configuration
          </div>
          <ModuleConfigEditor
            module={mod}
            config={group.config}
            onChange={onConfigChange}
          />
        </div>
      )}

      {isExpanded && exampleInfo && (
        <div className="border-t border-stone-100 pt-1.5">
          <div className="flex flex-col gap-1.5 md:gap-2 rounded-xl border border-stone-200 bg-stone-50 p-2 md:p-2.5">
            <img
              src={exampleInfo.image_url}
              alt={mod.label}
              className="w-full rounded-xl border border-stone-200 shadow-xs"
              loading="lazy"
            />
            <div className="min-w-0">
              <div className="text-[9px] font-bold uppercase tracking-wide text-stone-400">
                Example Result
              </div>
              <div className="text-xs font-semibold text-stone-800">
                {exampleInfo.title}
              </div>
              <div className="mt-0.5 text-[11px] leading-snug text-stone-600">
                {exampleInfo.summary}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function FilterPresetsTab() {
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
        <div className="app-panel grid gap-3 p-3 md:gap-4 md:p-4">
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

      <div className="grid gap-2">
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

// ── Effect Presets Tab ────────────────────────────────────────────────────────

function EffectPresetsTab() {
  const qc = useQueryClient();
  const presets = useQuery({
    queryKey: ['effect-presets'],
    queryFn: getEffectPresets,
  });
  const modules = useQuery({
    queryKey: ['generation-modules'],
    queryFn: getGenerationModules,
  });
  const examples = useQuery({
    queryKey: ['generation-examples'],
    queryFn: getGenerationExamples,
    retry: false,
  });

  const [editing, setEditing] = useState<EffectPreset | null>(null);
  const [isNew, setIsNew] = useState(false);
  const [name, setName] = useState('');
  const [groups, setGroups] = useState<ModificationGroupsConfig>(
    createDefaultModificationGroups(),
  );
  const [error, setError] = useState<string | null>(null);
  const [effectTab, setEffectTab] = useState<'local' | 'ai'>('local');
  const [expandedPreviews, setExpandedPreviews] = useState<
    Record<string, boolean>
  >({});

  const saveMutation = useMutation({
    mutationFn: () => {
      const body = { name, groups };
      return editing && !isNew
        ? updateEffectPreset(editing.id, body)
        : createEffectPreset(body);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['effect-presets'] });
      closeForm();
    },
    onError: (e: Error) => setError(e.message),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteEffectPreset(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['effect-presets'] }),
    onError: (e: Error) => setError(e.message),
  });

  function openNew() {
    setName('');
    setGroups(createDefaultModificationGroups());
    setEditing(null);
    setIsNew(true);
    setError(null);
    setExpandedPreviews({});
  }

  function openEdit(p: EffectPreset) {
    setName(p.name);
    const parsed = parseModificationGroups(JSON.stringify(p.groups));
    setGroups(parsed.value);
    setEditing(p);
    setIsNew(false);
    setError(null);
    setExpandedPreviews({});
  }

  function closeForm() {
    setEditing(null);
    setIsNew(false);
    setError(null);
  }

  const showForm = isNew || editing !== null;
  const moduleList = modules.data ?? [];

  const localModules = moduleList.filter((mod) => !mod.name.startsWith('ai_'));
  const aiModules = moduleList.filter((mod) => mod.name.startsWith('ai_'));

  const activeLocalCount = localModules.filter(
    (mod) => groups[mod.name]?.enabled,
  ).length;
  const activeAiCount = aiModules.filter(
    (mod) => groups[mod.name]?.enabled,
  ).length;

  const currentModules = effectTab === 'local' ? localModules : aiModules;
  const isLoading = presets.isLoading && !presets.data;
  const isError = presets.isError && !presets.data;
  const validationIssues: string[] = [];
  if (!name.trim()) validationIssues.push('Preset name is required.');
  if (activeLocalCount + activeAiCount === 0)
    validationIssues.push('Enable at least one effect before saving.');
  const canSave = validationIssues.length === 0;

  if (isLoading) {
    return <InlineSpinner />;
  }

  if (isError) {
    const errorMsg = presets.error;
    return (
      <ErrorBanner
        title="Could not load effect presets"
        error={errorMsg}
        onRetry={() => {
          presets.refetch();
          modules.refetch();
        }}
      />
    );
  }

  return (
    <div className="grid gap-3">
      {modules.isError && (
        <ErrorBanner
          title="Effect modules unavailable"
          error={modules.error as Error | string | null}
          onRetry={() => modules.refetch()}
        />
      )}

      <PresetHeader count={presets.data?.length ?? 0} onCreate={openNew} />

      {error && (
        <InlineError title="Could not save effect preset" message={error} />
      )}

      {showForm && (
        <div className="app-panel grid gap-2.5 p-3 md:gap-3 md:p-4">
          <div className="text-sm font-semibold text-stone-900">
            {isNew ? 'New effect preset' : `Editing: ${editing?.name}`}
          </div>
          <Field
            label="Name"
            value={name}
            maxLength={255}
            onChange={(e) => setName(e.target.value)}
          />

          <div className="grid gap-2">
            {/* Sub-tabs for Local and AI Effects */}
            <div className="grid gap-2 border-b border-stone-200/70 pb-2 sm:flex sm:gap-1.5 sm:pb-2">
              <button
                type="button"
                onClick={() => setEffectTab('local')}
                className={`flex w-full items-center justify-center gap-2 rounded-xl border px-3 py-2 text-xs font-semibold transition-all duration-200 sm:w-auto sm:rounded-t-xl sm:border-x-0 sm:border-b-2 sm:-mb-px ${
                  effectTab === 'local'
                    ? 'border-emerald-200 bg-emerald-50 text-emerald-700 sm:border-emerald-600 sm:bg-transparent'
                    : 'border-stone-200 bg-white text-stone-500 hover:text-stone-800 sm:border-transparent sm:bg-transparent'
                }`}
              >
                <span>Local Effects</span>
                <span
                  className={`inline-flex items-center justify-center px-1.5 py-0.5 text-[10px] font-bold rounded-full transition-colors ${
                    activeLocalCount > 0
                      ? 'bg-emerald-100 text-emerald-800'
                      : 'bg-stone-100 text-stone-500'
                  }`}
                >
                  {activeLocalCount}
                </span>
              </button>
              <button
                type="button"
                onClick={() => setEffectTab('ai')}
                className={`flex w-full items-center justify-center gap-2 rounded-xl border px-3 py-2 text-xs font-semibold transition-all duration-200 sm:w-auto sm:rounded-t-xl sm:border-x-0 sm:border-b-2 sm:-mb-px ${
                  effectTab === 'ai'
                    ? 'border-emerald-200 bg-emerald-50 text-emerald-700 sm:border-emerald-600 sm:bg-transparent'
                    : 'border-stone-200 bg-white text-stone-500 hover:text-stone-800 sm:border-transparent sm:bg-transparent'
                }`}
              >
                <span>AI Effects</span>
                <span
                  className={`inline-flex items-center justify-center px-1.5 py-0.5 text-[10px] font-bold rounded-full transition-colors ${
                    activeAiCount > 0
                      ? 'bg-purple-100 text-purple-800'
                      : 'bg-stone-100 text-stone-500'
                  }`}
                >
                  {activeAiCount}
                </span>
              </button>
            </div>

            {/* Desktop View Table */}
            <div className="hidden max-h-[500px] overflow-x-auto overflow-y-auto rounded-2xl border border-stone-200 bg-white/80 shadow-[0_8px_24px_rgba(36,29,16,0.04)] md:block">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-stone-200/80 bg-stone-100/70 text-[11px] font-semibold uppercase tracking-wider text-stone-500">
                    <th className="py-2 px-3 font-semibold">Effect</th>
                    <th className="py-2 px-3 font-semibold w-16 text-center">
                      Enable
                    </th>
                    <th className="py-2 px-3 font-semibold w-20 text-center">
                      Weight
                    </th>
                    <th className="py-2 px-3 font-semibold">Configuration</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-200/60 bg-white">
                  {currentModules.map((mod) => {
                    const group = groups[mod.name] ?? {
                      enabled: false,
                      weight: mod.default_weight,
                      config: mod.default_config ?? {},
                    };
                    const exampleInfo = examples.data?.find(
                      (ex) => ex.module_name === mod.name,
                    );
                    const isExpanded = !!expandedPreviews[mod.name];
                    return (
                      <EffectPresetTableItem
                        key={mod.name}
                        mod={mod}
                        group={group}
                        exampleInfo={exampleInfo}
                        isExpanded={isExpanded}
                        onTogglePreview={() =>
                          setExpandedPreviews((prev) => ({
                            ...prev,
                            [mod.name]: !prev[mod.name],
                          }))
                        }
                        onEnabledChange={(enabled: boolean) =>
                          setGroups((g) => ({
                            ...g,
                            [mod.name]: { ...group, enabled },
                          }))
                        }
                        onWeightChange={(weight: number) =>
                          setGroups((g) => ({
                            ...g,
                            [mod.name]: { ...group, weight },
                          }))
                        }
                        onConfigChange={(key, value) =>
                          setGroups((g) => ({
                            ...g,
                            [mod.name]: {
                              ...group,
                              config: { ...group.config, [key]: value },
                            },
                          }))
                        }
                      />
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Mobile View Cards */}
            <div className="md:hidden grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-3 max-h-[500px] overflow-y-auto p-0.5">
              {currentModules.map((mod) => {
                const group = groups[mod.name] ?? {
                  enabled: false,
                  weight: mod.default_weight,
                  config: mod.default_config ?? {},
                };
                const exampleInfo = examples.data?.find(
                  (ex) => ex.module_name === mod.name,
                );
                const isExpanded = !!expandedPreviews[mod.name];

                return (
                  <EffectPresetMobileCard
                    key={mod.name}
                    mod={mod}
                    group={group}
                    exampleInfo={exampleInfo}
                    isExpanded={isExpanded}
                    onTogglePreview={() =>
                      setExpandedPreviews((prev) => ({
                        ...prev,
                        [mod.name]: !prev[mod.name],
                      }))
                    }
                    onEnabledChange={(enabled: boolean) =>
                      setGroups((g) => ({
                        ...g,
                        [mod.name]: { ...group, enabled },
                      }))
                    }
                    onWeightChange={(weight: number) =>
                      setGroups((g) => ({
                        ...g,
                        [mod.name]: { ...group, weight },
                      }))
                    }
                    onConfigChange={(key, value) =>
                      setGroups((g) => ({
                        ...g,
                        [mod.name]: {
                          ...group,
                          config: { ...group.config, [key]: value },
                        },
                      }))
                    }
                  />
                );
              })}
            </div>
          </div>

          <PresetFormActions
            onSave={() => saveMutation.mutate()}
            onCancel={closeForm}
            canSave={canSave}
            pending={saveMutation.isPending}
          />
        </div>
      )}

      <div className="grid gap-2 xl:grid-cols-2">
        {presets.data?.map((p) => {
          const enabledEntries = Object.entries(p.groups).filter(
            ([, g]) => g.enabled,
          );
          const enabledNames = enabledEntries.map(([name]) => {
            const mod = modules.data?.find((m) => m.name === name);
            return mod?.label ?? name.replace(/_/g, ' ');
          });
          return (
            <div
              key={p.id}
              className="flex flex-col gap-2.5 md:gap-3 rounded-2xl border border-stone-200/80 bg-white/85 px-3 py-2.5 shadow-[0_8px_24px_rgba(36,29,16,0.04)] backdrop-blur-md sm:flex-row sm:items-center sm:justify-between sm:py-2"
            >
              <div className="min-w-0 flex-1 grid gap-1.5">
                <div className="flex items-center gap-2">
                  <span className="truncate text-sm font-semibold text-stone-900">
                    {p.name}
                  </span>
                  <span className="app-chip shrink-0 px-1.5 py-0.5 text-[10px] text-emerald-800">
                    {enabledEntries.length} active
                  </span>
                </div>
                {enabledNames.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {enabledNames.map((label) => (
                      <span
                        key={label}
                        className="app-chip px-2 py-0.5 text-[10px]"
                      >
                        {label}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              <PresetActionRow>
                <button
                  type="button"
                  onClick={() => openEdit(p)}
                  className="inline-flex w-full items-center justify-center gap-1 rounded-xl px-2.5 py-1.5 text-xs font-semibold text-stone-600 hover:bg-stone-100 sm:w-auto sm:bg-transparent sm:py-1"
                >
                  <Pencil size={12} /> Edit
                </button>
                <button
                  type="button"
                  onClick={() => {
                    if (confirm(`Delete "${p.name}"?`))
                      deleteMutation.mutate(p.id);
                  }}
                  className="inline-flex w-full items-center justify-center gap-1 rounded-xl px-2.5 py-1.5 text-xs font-semibold text-rose-700 hover:bg-rose-50 bg-rose-50/30 sm:w-auto sm:bg-transparent sm:py-1"
                >
                  <Trash2 size={12} /> Delete
                </button>
              </PresetActionRow>
            </div>
          );
        })}
        {presets.data?.length === 0 && (
          <div className="xl:col-span-2">
            <EmptyState
              title="No effect presets yet"
              description="Create an effect preset to choose which local and AI modules should run."
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

// ── Notification Presets Tab ──────────────────────────────────────────────────

function NotificationPresetsTab() {
  const qc = useQueryClient();
  const presets = useQuery({
    queryKey: ['notification-presets'],
    queryFn: getNotificationPresets,
  });

  const [editing, setEditing] = useState<NotificationPreset | null>(null);
  const [isNew, setIsNew] = useState(false);
  const [form, setForm] = useState({
    name: '',
    channels: ['web'] as string[],
    url: '',
    topic: '',
    token: '',
    webhook_url: '',
    push_subscription_ids: [] as number[],
  });
  const [error, setError] = useState<string | null>(null);

  const CHANNELS = [
    'web',
    'ntfy',
    'gotify',
    'telegram',
    'homeassistant',
    'apprise',
    'discord',
    'slack',
  ] as const;
  const CHANNEL_LABELS: Record<(typeof CHANNELS)[number], string> = {
    web: 'Web Push',
    ntfy: 'ntfy',
    gotify: 'Gotify',
    telegram: 'Telegram',
    homeassistant: 'Home Assistant',
    apprise: 'Apprise',
    discord: 'Discord',
    slack: 'Slack',
  };

  const saveMutation = useMutation({
    mutationFn: () => {
      const body = {
        name: form.name,
        provider: form.channels.join(','),
        url: form.url || null,
        topic: form.topic || null,
        token: form.token || null,
        webhook_url: form.webhook_url || null,
        push_subscription_ids: form.push_subscription_ids,
      };
      return editing && !isNew
        ? updateNotificationPreset(editing.id, body)
        : createNotificationPreset(body);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['notification-presets'] });
      closeForm();
    },
    onError: (e: Error) => setError(e.message),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteNotificationPreset(id),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ['notification-presets'] }),
    onError: (e: Error) => setError(e.message),
  });

  const [testResult, setTestResult] = useState<{
    id: number;
    msg: string;
    ok: boolean;
  } | null>(null);
  const testMutation = useMutation({
    mutationFn: (id: number) => testNotificationPreset(id),
    onSuccess: (data, id) =>
      setTestResult({
        id,
        msg: data.sent.join(', ') || data.errors.join(', '),
        ok: data.ok,
      }),
    onError: (e: Error, id) => setTestResult({ id, msg: e.message, ok: false }),
  });
  const testingId = testMutation.isPending
    ? (testMutation.variables ?? null)
    : null;

  function openNew() {
    setForm({
      name: '',
      channels: ['web'],
      url: '',
      topic: '',
      token: '',
      webhook_url: '',
      push_subscription_ids: [],
    });
    setEditing(null);
    setIsNew(true);
    setError(null);
  }

  function openEdit(p: NotificationPreset) {
    const channels = splitNotificationProviders(p.provider);
    setForm({
      name: p.name,
      channels,
      url: p.url ?? '',
      topic: p.topic ?? '',
      token: '',
      webhook_url: p.webhook_url ?? '',
      push_subscription_ids: p.push_subscription_ids ?? [],
    });
    setEditing(p);
    setIsNew(false);
    setError(null);
  }

  function closeForm() {
    setEditing(null);
    setIsNew(false);
    setError(null);
  }

  function toggleChannel(ch: string) {
    setForm((f) => ({
      ...f,
      channels: f.channels.includes(ch)
        ? f.channels.filter((c) => c !== ch)
        : [...f.channels, ch],
    }));
  }

  const showForm = isNew || editing !== null;
  const hasWeb = form.channels.includes('web');
  const hasNtfy = form.channels.includes('ntfy');
  const hasGotify = form.channels.includes('gotify');
  const hasTelegram = form.channels.includes('telegram');
  const hasHomeAssistant = form.channels.includes('homeassistant');
  const hasApprise = form.channels.includes('apprise');
  const hasDiscord = form.channels.includes('discord');
  const hasSlack = form.channels.includes('slack');
  const needsUrl = hasNtfy || hasGotify || hasHomeAssistant || hasApprise;
  const validationIssues: string[] = [];
  if (!form.name.trim()) validationIssues.push('Preset name is required.');
  if (form.channels.length === 0)
    validationIssues.push('Select at least one channel.');
  if (needsUrl && !form.url.trim())
    validationIssues.push(
      'A server URL is required for the selected channels.',
    );
  if (hasNtfy && !form.topic.trim())
    validationIssues.push('ntfy topic is required.');
  if (hasTelegram && !form.topic.trim())
    validationIssues.push('Telegram chat ID is required.');
  if (hasHomeAssistant && !form.token.trim() && !editing?.token_masked)
    validationIssues.push('Home Assistant access token is required.');
  if (hasDiscord && !form.webhook_url.trim())
    validationIssues.push('Discord Webhook URL is required.');
  if (hasSlack && !form.webhook_url.trim())
    validationIssues.push('Slack Webhook URL is required.');
  const canSave = validationIssues.length === 0;

  // Web Push state
  const subscriptions = useQuery({
    queryKey: ['push-subscriptions'],
    queryFn: getPushSubscriptions,
    enabled: hasWeb,
  });
  const deleteSubMutation = useMutation({
    mutationFn: deletePushSubscription,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['push-subscriptions'] }),
  });
  const [pushSub, setPushSub] = useState<PushSubscription | null>(null);
  const [pushStatus, setPushStatus] = useState<
    'idle' | 'pending' | 'subscribed' | 'error'
  >('idle');

  const webPushSupport = {
    hasNotification: typeof window !== 'undefined' && 'Notification' in window,
    hasServiceWorker: typeof navigator !== 'undefined' && 'serviceWorker' in navigator,
    hasPushManager: typeof window !== 'undefined' && 'PushManager' in window,
    isSecureContext: typeof window !== 'undefined' && window.isSecureContext,
  };

  const [notificationPermission, setNotificationPermission] = useState<string>(
    webPushSupport.hasNotification ? Notification.permission : 'unsupported'
  );

  const requestNotificationPermission = async () => {
    if (!webPushSupport.hasNotification) return;
    try {
      const permission = await Notification.requestPermission();
      setNotificationPermission(permission);
    } catch (err) {
      console.error('Failed to request permission', err);
    }
  };

  const canSubscribeToPush =
    webPushSupport.hasNotification &&
    webPushSupport.hasServiceWorker &&
    webPushSupport.hasPushManager &&
    webPushSupport.isSecureContext &&
    notificationPermission !== 'denied';

  const [testSubResult, setTestSubResult] = useState<{ id: number; ok: boolean; msg: string } | null>(null);

  const testSubMutation = useMutation({
    mutationFn: (subId: number) => testPushSubscription(subId),
    onSuccess: (data, subId) => {
      setTestSubResult({ id: subId, ok: true, msg: 'Test sent' });
      setTimeout(() => setTestSubResult(null), 5000);
    },
    onError: (e: Error, subId) => {
      setTestSubResult({ id: subId, ok: false, msg: `Error: ${e.message}` });
      setTimeout(() => setTestSubResult(null), 5000);
    },
  });

  function togglePushSubscriptionTarget(id: number, checked: boolean) {
    setForm((prev) => {
      const current = prev.push_subscription_ids ?? [];
      return {
        ...prev,
        push_subscription_ids: checked
          ? Array.from(new Set([...current, id]))
          : current.filter((item) => item !== id),
      };
    });
  }

  useEffect(() => {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) return;
    navigator.serviceWorker.ready.then((reg) => {
      reg.pushManager.getSubscription().then((sub) => {
        if (sub) {
          setPushSub(sub);
          setPushStatus('subscribed');
        }
      });
    });
  }, []);

  async function handlePushToggle() {
    if (pushStatus === 'pending') return;
    setPushStatus('pending');
    try {
      const reg = await navigator.serviceWorker.ready;
      if (pushSub) {
        await unsubscribeWebPush(pushSub);
        await pushSub.unsubscribe();
        setPushSub(null);
        setPushStatus('idle');
        qc.invalidateQueries({ queryKey: ['push-subscriptions'] });
      } else {
        const vapidKey = await getVapidPublicKey();
        const sub = await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: vapidKey,
        });
        await subscribeWebPush(sub);
        setPushSub(sub);
        setPushStatus('subscribed');
        qc.invalidateQueries({ queryKey: ['push-subscriptions'] });
      }
    } catch {
      setPushStatus('idle');
    }
  }

  const isLoading = presets.isLoading && !presets.data;
  const isError = presets.isError && !presets.data;

  if (isLoading) {
    return <InlineSpinner />;
  }

  if (isError) {
    return (
      <ErrorBanner
        title="Could not load notification presets"
        error={presets.error}
        onRetry={() => presets.refetch()}
      />
    );
  }

  return (
    <div className="grid gap-3">
      <PresetHeader count={presets.data?.length ?? 0} onCreate={openNew} />

      {error && (
        <InlineError
          title="Could not save notification preset"
          message={error}
        />
      )}

      {showForm && (
        <div className="app-panel grid gap-4 p-4">
          <div className="grid gap-0.5 md:gap-1">
            <div className="text-sm font-semibold text-stone-900">
              {isNew ? 'New notification preset' : `Editing: ${editing?.name}`}
            </div>
            <div className="text-sm text-stone-500">
              Channels are stored as a single preset, but each one keeps its own
              connection details.
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
            description="Name the preset and choose where notifications go."
          >
            <div className="grid gap-3">
              <Field
                label="Name"
                required
                value={form.name}
                maxLength={255}
                onChange={(e) =>
                  setForm((f) => ({ ...f, name: e.target.value }))
                }
              />
              <div className="grid gap-2">
                <div className="text-sm font-semibold text-stone-800">
                  Channels <span className="text-rose-500">*</span>
                </div>
                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {CHANNELS.map((ch) => (
                    <label
                      key={ch}
                      className={`flex items-start gap-2 rounded-2xl border px-3 py-2 text-sm transition-colors ${form.channels.includes(ch) ? 'border-emerald-200 bg-emerald-50/50 text-emerald-900' : 'border-stone-200 bg-white text-stone-700'}`}
                    >
                      <input
                        type="checkbox"
                        checked={form.channels.includes(ch)}
                        onChange={() => toggleChannel(ch)}
                        className="mt-0.5 h-4 w-4 accent-emerald-700"
                      />
                      <div className="grid gap-0.5">
                        <span className="font-medium">
                          {CHANNEL_LABELS[ch]}
                        </span>
                        <span className="text-xs text-stone-500">
                          {ch === 'web'
                            ? 'Browser push notifications.'
                            : ch === 'telegram'
                              ? 'Telegram bot delivery.'
                              : 'External notification provider.'}
                        </span>
                      </div>
                    </label>
                  ))}
                </div>
              </div>
            </div>
          </SectionCard>

          {hasWeb && (
            <SectionCard
              title="Web Push"
              description="Manage browser subscriptions and device targets for this preset."
            >
              <div className="grid gap-4">
                {/* Diagnostics Status Badge */}
                {(() => {
                  let diagnosticsText = '';
                  let diagnosticsColor = 'text-stone-500 bg-stone-100 border-stone-200';
                  let showPermissionButton = false;

                  if (!webPushSupport.hasNotification || !webPushSupport.hasServiceWorker || !webPushSupport.hasPushManager) {
                    diagnosticsText = 'This browser does not support Web Push';
                    diagnosticsColor = 'text-rose-700 bg-rose-50 border-rose-200';
                  } else if (!webPushSupport.isSecureContext) {
                    diagnosticsText = 'Web Push requires HTTPS or a local localhost context';
                    diagnosticsColor = 'text-amber-700 bg-amber-50 border-amber-200';
                  } else if (notificationPermission === 'default') {
                    diagnosticsText = 'Requires permission';
                    diagnosticsColor = 'text-amber-700 bg-amber-50 border-amber-200';
                    showPermissionButton = true;
                  } else if (notificationPermission === 'denied') {
                    diagnosticsText = 'Blocked in browser settings';
                    diagnosticsColor = 'text-rose-700 bg-rose-50 border-rose-200';
                  } else if (notificationPermission === 'granted') {
                    diagnosticsText = 'Notifications enabled';
                    diagnosticsColor = 'text-emerald-700 bg-emerald-50 border-emerald-200';
                  }

                  return (
                    <div className="flex flex-wrap items-center gap-2">
                      <div className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${diagnosticsColor}`}>
                        <span className="h-1.5 w-1.5 rounded-full bg-current" />
                        Status: {diagnosticsText}
                      </div>
                      {showPermissionButton && (
                        <button
                          type="button"
                          onClick={requestNotificationPermission}
                          className="app-button-secondary h-6 px-2.5 text-[10px] font-semibold"
                        >
                          Grant permission
                        </button>
                      )}
                    </div>
                  );
                })()}

                {/* Local Browser Subscription Controls */}
                <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
                  <button
                    type="button"
                    onClick={handlePushToggle}
                    disabled={
                      pushStatus === 'pending' || !canSubscribeToPush
                    }
                    className="app-button-secondary h-8 w-full px-3 text-xs disabled:opacity-50 sm:w-auto"
                  >
                    {pushStatus === 'subscribed' ? (
                      <BellOff size={12} />
                    ) : (
                      <Bell size={12} />
                    )}
                    {pushStatus === 'subscribed'
                      ? 'Unsubscribe this browser'
                      : pushStatus === 'pending'
                        ? 'Wait…'
                        : 'Subscribe this browser'}
                  </button>
                  {pushStatus === 'subscribed' && (
                    <span className="text-xs font-medium text-emerald-700">
                      Subscribed
                    </span>
                  )}
                </div>

                {/* Warn if no device is targeted */}
                {(form.push_subscription_ids ?? []).length === 0 && (
                  <div className="rounded-xl bg-amber-50 border border-amber-200 p-2.5 text-xs text-amber-800">
                    This preset will not send Web Push notifications until you select at least one device.
                  </div>
                )}

                {/* Subscriptions List with Checkboxes */}
                {subscriptions.data &&
                  subscriptions.data.subscriptions.length > 0 ? (
                    <div className="grid gap-2">
                      <div className="text-xs font-semibold text-stone-500">
                        Select devices to target with this preset:
                      </div>
                      {subscriptions.data.subscriptions.map((sub) => {
                        const label =
                          sub.device_label ||
                          sub.user_agent ||
                          'Unknown browser';
                        const isMobile = /mobile|android|iphone|ipad/i.test(
                          label,
                        );
                        const isChecked = (form.push_subscription_ids ?? []).includes(sub.id);
                        const isTesting = testSubMutation.isPending && testSubMutation.variables === sub.id;
                        const testStatus = testSubResult && testSubResult.id === sub.id ? testSubResult : null;

                        return (
                          <div
                            key={sub.id}
                            className="flex items-center gap-3 rounded-2xl border border-stone-200 bg-stone-50 px-3 py-2 hover:bg-stone-100 transition-colors"
                          >
                            <input
                              type="checkbox"
                              id={`push-sub-${sub.id}`}
                              checked={isChecked}
                              onChange={(e) => togglePushSubscriptionTarget(sub.id, e.target.checked)}
                              className="h-4 w-4 rounded border-stone-300 text-stone-900 focus:ring-stone-900"
                            />
                            <label
                              htmlFor={`push-sub-${sub.id}`}
                              className="flex flex-1 items-center gap-2 cursor-pointer"
                            >
                              {isMobile ? (
                                <Smartphone
                                  size={14}
                                  className="shrink-0 text-stone-400"
                                />
                              ) : (
                                <Monitor
                                  size={14}
                                  className="shrink-0 text-stone-400"
                                />
                              )}
                              <span className="flex-1 truncate text-xs text-stone-700 font-medium">
                                {label}
                              </span>
                            </label>

                            {testStatus && (
                              <span className={`text-[10px] font-medium transition-opacity duration-300 ${testStatus.ok ? 'text-emerald-600' : 'text-rose-600'}`}>
                                {testStatus.msg}
                              </span>
                            )}

                            <button
                              type="button"
                              onClick={() => testSubMutation.mutate(sub.id)}
                              disabled={isTesting}
                              className="shrink-0 text-[10px] font-semibold text-stone-600 hover:text-stone-900 bg-stone-200 hover:bg-stone-300 px-2.5 py-0.5 rounded-full transition-colors disabled:opacity-50"
                            >
                              {isTesting ? 'Testing...' : 'Test'}
                            </button>

                            <button
                              type="button"
                              onClick={() => {
                                if (confirm('Deleting this subscription will remove it from all preset targets. Continue?')) {
                                  deleteSubMutation.mutate(sub.id);
                                  setForm((f) => ({
                                    ...f,
                                    push_subscription_ids: (f.push_subscription_ids ?? []).filter((id) => id !== sub.id),
                                  }));
                                }
                              }}
                              disabled={deleteSubMutation.isPending}
                              className="shrink-0 text-stone-400 hover:text-rose-600 disabled:opacity-50 transition-colors"
                              title="Delete globally"
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="text-xs text-stone-500 italic">
                      No registered devices found. Register this browser above.
                    </div>
                  )}
              </div>
            </SectionCard>
          )}

          <SectionCard
            title="Provider settings"
            description="Fill in the fields required by the selected channels."
          >
            <div className="grid gap-3">
              {needsUrl && (
                <Field
                  label={
                    hasApprise ? 'Apprise endpoint URL(s)' : 'Endpoint URL'
                  }
                  required
                  type={hasApprise ? 'text' : 'url'}
                  maxLength={2048}
                  value={form.url}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, url: e.target.value }))
                  }
                  placeholder={
                    hasApprise
                      ? 'tgram://bot_token/chat_id, mailto://user:pass@gmail.com'
                      : hasHomeAssistant
                        ? 'http://homeassistant.local:8123'
                        : 'https://ntfy.sh'
                  }
                  hint={
                    hasApprise
                      ? 'Required for Apprise.'
                      : hasHomeAssistant
                        ? 'Use the Home Assistant base URL, including port if needed.'
                        : hasNtfy
                          ? 'Use your ntfy server URL, such as https://ntfy.sh or your self-hosted instance.'
                          : 'Required for the selected provider(s).'
                  }
                />
              )}
              {hasNtfy && (
                <Field
                  label="Topic"
                  required
                  value={form.topic}
                  maxLength={255}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, topic: e.target.value }))
                  }
                  hint="The ntfy topic name. Add a token only if the topic is protected."
                />
              )}
              {hasTelegram && (
                <Field
                  label="Telegram Chat ID"
                  required
                  value={form.topic}
                  maxLength={255}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, topic: e.target.value }))
                  }
                  placeholder="-10012345678 or @channelname"
                  hint="Use the chat ID for a private chat or group, or an @channelname for a channel."
                />
              )}
              {hasHomeAssistant && (
                <Field
                  label="Notify service name"
                  optional
                  value={form.topic}
                  maxLength={255}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, topic: e.target.value }))
                  }
                  placeholder="e.g. notify or mobile_app_phone"
                  hint="Leave blank to use the default notify service. Use persistent_notification for a sidebar notice."
                />
              )}
              {(hasNtfy || hasGotify || hasTelegram || hasHomeAssistant) && (
                <Field
                  label={
                    hasTelegram
                      ? 'Telegram Bot Token'
                      : hasHomeAssistant
                        ? 'Home Assistant Access Token (LLAT)'
                        : 'Token'
                  }
                  required={hasTelegram || hasHomeAssistant}
                  optional={!hasTelegram && !hasHomeAssistant}
                  type="password"
                  value={form.token}
                  placeholder={editing?.token_masked ?? ''}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, token: e.target.value }))
                  }
                />
              )}
              <Field
                label="Webhook URL"
                required={hasDiscord || hasSlack}
                optional={!hasDiscord && !hasSlack}
                type="url"
                maxLength={2048}
                value={form.webhook_url}
                onChange={(e) =>
                  setForm((f) => ({ ...f, webhook_url: e.target.value }))
                }
                placeholder={
                  hasDiscord
                    ? 'https://discord.com/api/webhooks/...'
                    : hasSlack
                      ? 'https://hooks.slack.com/services/...'
                      : 'https://example.com/webhook'
                }
              />
              {(hasNtfy ||
                hasTelegram ||
                hasHomeAssistant ||
                hasDiscord ||
                hasSlack) && (
                <div className="rounded-2xl border border-stone-200 bg-stone-50/80 p-3 text-xs text-stone-600">
                  <div className="mb-1.5 text-[10px] font-bold uppercase tracking-[0.18em] text-stone-500">
                    Provider tips
                  </div>
                  <div className="grid gap-1.5 leading-relaxed">
                    {hasNtfy && (
                      <p>
                        <span className="font-semibold text-stone-800">
                          ntfy:
                        </span>{' '}
                        messages include a click target and image attachment
                        when your DailyFX external URL is configured, so the
                        phone notification can open the review page and preview
                        the image.
                      </p>
                    )}
                    {hasTelegram && (
                      <p>
                        <span className="font-semibold text-stone-800">
                          Telegram:
                        </span>{' '}
                        the bot sends the image directly with Accept / Reject
                        buttons, so the chat ID and bot token are the only
                        required values.
                      </p>
                    )}
                    {hasHomeAssistant && (
                      <p>
                        <span className="font-semibold text-stone-800">
                          Home Assistant:
                        </span>{' '}
                        use a long-lived access token and a notify service such
                        as{' '}
                        <code className="rounded-sm bg-white px-1 py-0.5 text-[11px] text-stone-700">
                          mobile_app_phone
                        </code>{' '}
                        or{' '}
                        <code className="rounded-sm bg-white px-1 py-0.5 text-[11px] text-stone-700">
                          persistent_notification
                        </code>
                        .
                      </p>
                    )}
                    {hasDiscord && (
                      <p>
                        <span className="font-semibold text-stone-800">
                          Discord:
                        </span>{' '}
                        messages are delivered directly to the configured
                        channel webhook with image preview embeds when your
                        DailyFX external URL is configured.
                      </p>
                    )}
                    {hasSlack && (
                      <p>
                        <span className="font-semibold text-stone-800">
                          Slack:
                        </span>{' '}
                        messages are delivered directly to the configured
                        channel webhook using Slack's rich block kit, including
                        image preview and review action buttons.
                      </p>
                    )}
                  </div>
                </div>
              )}
            </div>
          </SectionCard>

          <PresetFormActions
            onSave={() => saveMutation.mutate()}
            onCancel={closeForm}
            canSave={canSave}
            pending={saveMutation.isPending}
          />
        </div>
      )}

      <div className="grid gap-2 xl:grid-cols-2">
        {presets.data?.map((p) => (
          <NotificationPresetCard
            key={p.id}
            preset={p}
            testResult={testResult}
            testingId={testingId}
            onTest={(id) => testMutation.mutate(id)}
            onEdit={openEdit}
            onDelete={(id, name) => {
              if (confirm(`Delete "${name}"?`)) deleteMutation.mutate(id);
            }}
          />
        ))}
        {presets.data?.length === 0 && (
          <div className="xl:col-span-2">
            <EmptyState
              title="No notification presets yet"
              description="Create a notification preset to wire one or more delivery channels into schedules."
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

// ── Main Page ─────────────────────────────────────────────────────────────────

export function FilterPresetsPage() {
  return (
    <section className="grid gap-4">
      <div className="app-panel grid gap-4 p-4">
        <FilterPresetsTab />
      </div>
    </section>
  );
}

export function EffectPresetsPage() {
  return (
    <section className="grid gap-4">
      <div className="app-panel grid gap-4 p-4">
        <EffectPresetsTab />
      </div>
    </section>
  );
}

export function NotificationPresetsPage() {
  return (
    <section className="grid gap-4">
      <div className="app-panel grid gap-4 p-4">
        <NotificationPresetsTab />
      </div>
    </section>
  );
}
