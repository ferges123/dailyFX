import { useState, useEffect, Fragment } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Bell, BellOff, Monitor, Plus, Trash2, Pencil, Check, X, Smartphone, Eye } from 'lucide-react';
import { InlineSpinner, ErrorBanner } from '../components/ErrorUI';
import { EmptyState, InlineError, SectionCard } from '../components/FormUI';
import {
  getFilterPresets, createFilterPreset, updateFilterPreset, deleteFilterPreset,
  getEffectPresets, createEffectPreset, updateEffectPreset, deleteEffectPreset,
  getNotificationPresets, createNotificationPreset, updateNotificationPreset, deleteNotificationPreset, testNotificationPreset,
  getImmichFilterOptions, getGenerationModules, getGenerationExamples,
  getVapidPublicKey, subscribeWebPush, unsubscribeWebPush, getPushSubscriptions, deletePushSubscription,
  formatNotificationProviders,
  splitNotificationProviders,
  type FilterPreset, type EffectPreset, type NotificationPreset, type ImmichPersonFilter, type ImmichFilterOptions,
} from '../api/client';
import { Field, SelectField } from '../components/Field';
import { MultiSelectPanel, PersonSelectPanel } from '../components/FilterPanels';
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

function FilterPresetsTab() {
  const qc = useQueryClient();
  const presets = useQuery({ queryKey: ['filter-presets'], queryFn: getFilterPresets });
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
    }
  });

  useEffect(() => {
    if (options.data) {
      try {
        localStorage.setItem('dailyfx_immich_filter_options', JSON.stringify(options.data));
      } catch (err) {
        console.warn('Failed to cache Immich filter options:', err);
      }
    }
  }, [options.data]);

  const [editing, setEditing] = useState<FilterPreset | null>(null);
  const [isNew, setIsNew] = useState(false);
  const [form, setForm] = useState<FilterFormState>({
    name: '', album_ids: [], person_filters: [],
    start_date: null, end_date: null, media_type: 'photo',
  });
  const [albumSearch, setAlbumSearch] = useState('');
  const [personSearch, setPersonSearch] = useState('');
  const [error, setError] = useState<string | null>(null);

  const saveMutation = useMutation({
    mutationFn: () => editing && !isNew
      ? updateFilterPreset(editing.id, form)
      : createFilterPreset(form),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['filter-presets'] }); closeForm(); },
    onError: (e: Error) => setError(e.message),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteFilterPreset(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['filter-presets'] }),
    onError: (e: Error) => setError(e.message),
  });

  function openNew() {
    setForm({ name: '', album_ids: [], person_filters: [], start_date: null, end_date: null, media_type: 'photo' });
    setAlbumSearch('');
    setPersonSearch('');
    setEditing(null); setIsNew(true); setError(null);
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
    setEditing(p); setIsNew(false); setError(null);
  }

  function closeForm() {
    setAlbumSearch('');
    setPersonSearch('');
    setEditing(null); setIsNew(false); setError(null);
  }

  const albums = (options.data?.albums ?? []).filter(a => a.album_name.toLowerCase().includes(albumSearch.toLowerCase()));
  const people = (options.data?.people ?? []).filter(p => p.name.toLowerCase().includes(personSearch.toLowerCase()));

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
    return <ErrorBanner title="Could not load filter presets" error={errorMsg} onRetry={() => { presets.refetch(); options.refetch(); }} />;
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

      <div className="flex items-center justify-between">
        <span className="text-sm text-stone-500">{presets.data?.length ?? 0} preset(s)</span>
        <button type="button" onClick={openNew}
          className="inline-flex items-center gap-1.5 rounded-md bg-emerald-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-800">
          <Plus size={14} /> New preset
        </button>
      </div>

      {error && <InlineError title="Could not save filter preset" message={error} />}

      {showForm && (
        <div className="rounded-xl border border-stone-200 bg-stone-50 p-4 grid gap-4">
          <div className="grid gap-1">
            <div className="text-sm font-semibold text-stone-900">{isNew ? 'New filter preset' : `Editing: ${editing?.name}`}</div>
            <div className="text-xs text-stone-500">Keep the core criteria visible while you fine-tune albums and people.</div>
          </div>
          {validationIssues.length > 0 && <InlineError title="Fix the highlighted fields" message={validationIssues.join(' ')} />}

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
                  onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                />
                <SelectField
                  label="Media type"
                  value={form.media_type}
                  onChange={e => setForm(f => ({ ...f, media_type: e.target.value }))}
                >
                  <option value="photo">Photos</option>
                  <option value="video">Videos</option>
                  <option value="all">All media</option>
                </SelectField>
                <div className="grid gap-1 rounded-md border border-stone-200 bg-stone-50 px-3 py-2 text-xs text-stone-500">
                  <div className="font-medium text-stone-700">Date range</div>
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
                  onChange={e => setForm(f => ({ ...f, start_date: e.target.value || null }))}
                  optional
                />
                <Field
                  label="To"
                  type="date"
                  value={form.end_date ?? ''}
                  onChange={e => setForm(f => ({ ...f, end_date: e.target.value || null }))}
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
              options={albums.map(a => ({ id: a.id, label: `${a.album_name} (${a.asset_count})` }))}
              selectedIds={form.album_ids}
              loading={options.isLoading}
              onToggle={id => setForm(f => ({ ...f, album_ids: f.album_ids.includes(id) ? f.album_ids.filter(x => x !== id) : [...f.album_ids, id] }))}
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
              options={people.map(p => ({ id: p.id, label: `${p.name} (${p.asset_count})` }))}
              selectedFilters={form.person_filters}
              loading={options.isLoading}
              onToggle={id => setForm(f => {
                const exists = f.person_filters.some(p => p.personId === id);
                const next = exists ? f.person_filters.filter(p => p.personId !== id) : [...f.person_filters, { personId: id, mode: 'optional' as const }];
                return { ...f, person_filters: next };
              })}
              onModeChange={(id, mode) => setForm(f => ({
                ...f,
                person_filters: f.person_filters.map(p => p.personId === id ? { ...p, mode: mode as ImmichPersonFilter['mode'] } : p),
              }))}
            />
          </SectionCard>

          <div className="flex flex-col gap-1.5 rounded-lg border border-stone-200 bg-white px-3 py-2 text-xs text-stone-500 sm:flex-row sm:items-center sm:justify-between">
            <span>{selectedAlbumCount} album(s) and {selectedPersonCount} people selected.</span>
            <span>Required fields are marked with an asterisk.</span>
          </div>

          <div className="flex flex-col gap-2 sm:flex-row">
            <button
              type="button"
              onClick={() => saveMutation.mutate()}
              disabled={!canSave || saveMutation.isPending}
              className="inline-flex items-center justify-center gap-1.5 rounded-md bg-emerald-700 px-3 py-2 text-sm font-semibold text-white hover:bg-emerald-800 disabled:opacity-50 w-full sm:w-auto"
            >
              <Check size={14} /> Save
            </button>
            <button
              type="button"
              onClick={closeForm}
              className="inline-flex items-center justify-center gap-1.5 rounded-md border border-stone-300 px-3 py-2 text-sm font-semibold text-stone-700 hover:bg-stone-50 w-full sm:w-auto"
            >
              <X size={14} /> Cancel
            </button>
          </div>
        </div>
      )}

      <div className="grid gap-2">
        {presets.data?.map(p => {
          const albumsList = p.album_ids
            .map(id => ({
              id,
              name: options.isLoading ? '...' : (options.data?.albums.find(a => a.id === id)?.album_name ?? id)
            }))
            .slice(0, 5);
          const peopleList = p.person_filters
            .map(pf => ({
              id: pf.personId,
              name: options.isLoading ? '...' : (options.data?.people.find(pe => pe.id === pf.personId)?.name ?? pf.personId)
            }))
            .slice(0, 5);
          const tags: string[] = [];
          if (p.media_type && p.media_type !== 'photo') tags.push(p.media_type);
          if (p.start_date) tags.push(`from ${p.start_date}`);
          if (p.end_date) tags.push(`to ${p.end_date}`);

          return (
            <div key={p.id} className="grid gap-2 rounded-lg border border-stone-200 bg-white px-3 py-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start">
              <div className="min-w-0 grid gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-semibold text-stone-900 truncate">{p.name}</span>
                  <span className="rounded-full bg-stone-100 px-2 py-0.5 text-[10px] font-semibold text-stone-600">
                    {albumsList.length} album{albumsList.length === 1 ? '' : 's'}
                  </span>
                  <span className="rounded-full bg-stone-100 px-2 py-0.5 text-[10px] font-semibold text-stone-600">
                    {peopleList.length} people
                  </span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {albumsList.map(item => (
                    <span key={item.id} className="rounded-full bg-blue-50 border border-blue-100 px-2 py-0.5 text-[10px] font-medium text-blue-700">
                      📁 {item.name}
                    </span>
                  ))}
                  {peopleList.map(item => (
                    <span key={item.id} className="rounded-full bg-purple-50 border border-purple-100 px-2 py-0.5 text-[10px] font-medium text-purple-700">
                      👤 {item.name}
                    </span>
                  ))}
                  {tags.map(t => (
                    <span key={t} className="rounded-full bg-stone-100 border border-stone-200 px-2 py-0.5 text-[10px] font-medium text-stone-600">
                      {t}
                    </span>
                  ))}
                </div>
              </div>
              <div className="flex gap-1 shrink-0">
                <button
                  type="button"
                  onClick={() => openEdit(p)}
                  className="inline-flex items-center gap-1 rounded-md border border-stone-300 bg-white px-2.5 py-1.5 text-xs font-medium text-stone-600 hover:bg-stone-50"
                >
                  <Pencil size={12} /> Edit
                </button>
                <button
                  type="button"
                  onClick={() => { if (confirm(`Delete "${p.name}"?`)) deleteMutation.mutate(p.id); }}
                  className="inline-flex items-center gap-1 rounded-md border border-stone-300 bg-white px-2.5 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50"
                >
                  <Trash2 size={12} /> Delete
                </button>
              </div>
            </div>
          );
        })}
        {presets.data?.length === 0 && (
          <EmptyState
            title="No filter presets yet"
            description="Create a filter preset to control which albums, people, and dates feed generation."
            action={(
              <button type="button" onClick={openNew} className="inline-flex items-center gap-1.5 rounded-md bg-emerald-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-800">
                <Plus size={14} /> New preset
              </button>
            )}
          />
        )}
      </div>
    </div>
  );
}

// ── Effect Presets Tab ────────────────────────────────────────────────────────

function EffectPresetsTab() {
  const qc = useQueryClient();
  const presets = useQuery({ queryKey: ['effect-presets'], queryFn: getEffectPresets });
  const modules = useQuery({ queryKey: ['generation-modules'], queryFn: getGenerationModules });
  const examples = useQuery({ queryKey: ['generation-examples'], queryFn: getGenerationExamples, retry: false });

  const [editing, setEditing] = useState<EffectPreset | null>(null);
  const [isNew, setIsNew] = useState(false);
  const [name, setName] = useState('');
  const [groups, setGroups] = useState<ModificationGroupsConfig>(createDefaultModificationGroups());
  const [error, setError] = useState<string | null>(null);
  const [effectTab, setEffectTab] = useState<'local' | 'ai'>('local');
  const [expandedPreviews, setExpandedPreviews] = useState<Record<string, boolean>>({});

  const saveMutation = useMutation({
    mutationFn: () => {
      const body = { name, groups };
      return editing && !isNew ? updateEffectPreset(editing.id, body) : createEffectPreset(body);
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['effect-presets'] }); closeForm(); },
    onError: (e: Error) => setError(e.message),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteEffectPreset(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['effect-presets'] }),
    onError: (e: Error) => setError(e.message),
  });

  function openNew() {
    setName(''); setGroups(createDefaultModificationGroups());
    setEditing(null); setIsNew(true); setError(null);
    setExpandedPreviews({});
  }

  function openEdit(p: EffectPreset) {
    setName(p.name);
    const parsed = parseModificationGroups(JSON.stringify(p.groups));
    setGroups(parsed.value);
    setEditing(p); setIsNew(false); setError(null);
    setExpandedPreviews({});
  }

  function closeForm() { setEditing(null); setIsNew(false); setError(null); }

  const showForm = isNew || editing !== null;
  const moduleList = modules.data ?? [];

  const localModules = moduleList.filter(mod => !mod.name.startsWith('ai_'));
  const aiModules = moduleList.filter(mod => mod.name.startsWith('ai_'));

  const activeLocalCount = localModules.filter(mod => groups[mod.name]?.enabled).length;
  const activeAiCount = aiModules.filter(mod => groups[mod.name]?.enabled).length;

  const currentModules = effectTab === 'local' ? localModules : aiModules;
  const isLoading = presets.isLoading && !presets.data;
  const isError = presets.isError && !presets.data;
  const validationIssues: string[] = [];
  if (!name.trim()) validationIssues.push('Preset name is required.');
  if (activeLocalCount + activeAiCount === 0) validationIssues.push('Enable at least one effect before saving.');
  const canSave = validationIssues.length === 0;

  if (isLoading) {
    return <InlineSpinner />;
  }

  if (isError) {
    const errorMsg = presets.error;
    return <ErrorBanner title="Could not load effect presets" error={errorMsg} onRetry={() => { presets.refetch(); modules.refetch(); }} />;
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

      <div className="flex items-center justify-between">
        <span className="text-sm text-stone-500">{presets.data?.length ?? 0} preset(s)</span>
        <button type="button" onClick={openNew}
          className="inline-flex items-center gap-1.5 rounded-md bg-emerald-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-800">
          <Plus size={14} /> New preset
        </button>
      </div>

      {error && <InlineError title="Could not save effect preset" message={error} />}

      {showForm && (
        <div className="rounded-md border border-stone-200 bg-stone-50 p-4 grid gap-3">
          <div className="text-sm font-semibold text-stone-700">{isNew ? 'New effect preset' : `Editing: ${editing?.name}`}</div>
          <Field label="Name" value={name} maxLength={255} onChange={e => setName(e.target.value)} />
          
          <div className="grid gap-2">
            {/* Sub-tabs for Local and AI Effects */}
            <div className="flex gap-2 border-b border-stone-200 mb-2">
              <button
                type="button"
                onClick={() => setEffectTab('local')}
                className={`flex items-center gap-2 px-3 py-2 text-xs font-semibold border-b-2 -mb-px transition-all duration-200 ${
                  effectTab === 'local'
                    ? 'border-emerald-600 text-emerald-700'
                    : 'border-transparent text-stone-500 hover:text-stone-800'
                }`}
              >
                <span>Local Effects</span>
                <span className={`inline-flex items-center justify-center px-1.5 py-0.5 text-[10px] font-bold rounded-full transition-colors ${
                  activeLocalCount > 0
                    ? 'bg-emerald-100 text-emerald-800'
                    : 'bg-stone-100 text-stone-500'
                }`}>
                  {activeLocalCount}
                </span>
              </button>
              <button
                type="button"
                onClick={() => setEffectTab('ai')}
                className={`flex items-center gap-2 px-3 py-2 text-xs font-semibold border-b-2 -mb-px transition-all duration-200 ${
                  effectTab === 'ai'
                    ? 'border-emerald-600 text-emerald-700'
                    : 'border-transparent text-stone-500 hover:text-stone-800'
                }`}
              >
                <span>AI Effects</span>
                <span className={`inline-flex items-center justify-center px-1.5 py-0.5 text-[10px] font-bold rounded-full transition-colors ${
                  activeAiCount > 0
                    ? 'bg-purple-100 text-purple-800'
                    : 'bg-stone-100 text-stone-500'
                }`}>
                  {activeAiCount}
                </span>
              </button>
            </div>

            {/* Desktop View Table */}
            <div className="hidden md:block overflow-x-auto max-h-[500px] overflow-y-auto border border-stone-200 rounded-md shadow-sm">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-stone-200 bg-stone-100/70 text-[11px] font-semibold text-stone-500 uppercase tracking-wider">
                    <th className="py-2 px-3 font-semibold">Effect</th>
                    <th className="py-2 px-3 font-semibold w-16 text-center">Enable</th>
                    <th className="py-2 px-3 font-semibold w-20 text-center">Weight</th>
                    <th className="py-2 px-3 font-semibold">Configuration</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-200/60 bg-white">
                  {currentModules.map(mod => {
                    const group = groups[mod.name] ?? { enabled: false, weight: mod.default_weight, config: mod.default_config ?? {} };
                    const exampleInfo = examples.data?.find(ex => ex.module_name === mod.name);
                    const hasExample = !!exampleInfo;
                    const isExpanded = !!expandedPreviews[mod.name];

                    return (
                      <Fragment key={mod.name}>
                        <FilterRow
                          title={
                            <div className="grid gap-0.5">
                              <div className="flex items-center gap-1.5 font-semibold text-stone-800 text-sm leading-snug">
                                <span>{mod.label}</span>
                                {hasExample && (
                                  <button
                                    type="button"
                                    onClick={() => setExpandedPreviews(prev => ({ ...prev, [mod.name]: !prev[mod.name] }))}
                                    title="Toggle preview image"
                                    className={`inline-flex items-center justify-center p-1 rounded hover:bg-stone-100 transition-colors ${
                                      isExpanded ? 'text-emerald-700 bg-emerald-50 hover:bg-emerald-100' : 'text-stone-400 hover:text-stone-600'
                                    }`}
                                  >
                                    <Eye size={13} />
                                  </button>
                                )}
                              </div>
                              <div className="text-stone-400 text-[11px] font-normal leading-normal">{mod.description}</div>
                            </div>
                          }
                          icon={null}
                          enabled={group.enabled}
                          weight={group.weight}
                          onEnabledChange={(enabled: boolean) => setGroups(g => ({ ...g, [mod.name]: { ...group, enabled } }))}
                          onWeightChange={(weight: number) => setGroups(g => ({ ...g, [mod.name]: { ...group, weight } }))}
                          config={mod.config_schema?.length > 0 ? (
                            <ModuleConfigEditor
                              module={mod}
                              config={group.config as Record<string, unknown>}
                              onChange={(key, value) => setGroups(g => ({ ...g, [mod.name]: { ...group, config: { ...group.config, [key]: value } } }))}
                            />
                          ) : null}
                        />
                        {isExpanded && exampleInfo && (
                          <tr className="bg-stone-50/30">
                            <td colSpan={4} className="py-3 px-3 border-t border-stone-200">
                              <div className="flex flex-col sm:flex-row gap-4 items-start bg-white p-3 rounded-md border border-stone-200 shadow-sm max-w-2xl">
                                <div className="shrink-0 max-w-full">
                                  <img
                                    src={exampleInfo.image_url}
                                    alt={mod.label}
                                    className="w-full sm:w-64 rounded border border-stone-200 shadow-sm"
                                    loading="lazy"
                                  />
                                </div>
                                <div className="grid gap-1 min-w-0">
                                  <div className="text-[10px] font-bold text-stone-400 uppercase tracking-wide">Example Result</div>
                                  <div className="text-sm font-semibold text-stone-800 truncate">{exampleInfo.title}</div>
                                  <div className="text-xs text-stone-600 leading-relaxed">{exampleInfo.summary}</div>
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Mobile View Cards */}
            <div className="md:hidden grid gap-3 max-h-[500px] overflow-y-auto p-0.5">
              {currentModules.map(mod => {
                const group = groups[mod.name] ?? { enabled: false, weight: mod.default_weight, config: mod.default_config ?? {} };
                const exampleInfo = examples.data?.find(ex => ex.module_name === mod.name);
                const hasExample = !!exampleInfo;
                const isExpanded = !!expandedPreviews[mod.name];

                return (
                  <div
                    key={mod.name}
                    className={`rounded-lg border p-3 grid gap-3.5 transition ${
                      group.enabled ? 'border-emerald-250 bg-emerald-50/10' : 'border-stone-200 bg-white'
                    }`}
                  >
                    {/* Top Row: Title, Enable Checkbox, Weight Input */}
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1.5 font-bold text-stone-900 text-sm">
                          <span>{mod.label}</span>
                          {hasExample && (
                            <button
                              type="button"
                              onClick={() => setExpandedPreviews(prev => ({ ...prev, [mod.name]: !prev[mod.name] }))}
                              className={`inline-flex h-6 w-6 items-center justify-center rounded hover:bg-stone-100 transition-colors ${
                                isExpanded ? 'text-emerald-700 bg-emerald-50' : 'text-stone-400'
                              }`}
                            >
                              <Eye size={14} />
                            </button>
                          )}
                        </div>
                        <div className="text-stone-500 text-[11px] leading-snug mt-0.5">{mod.description}</div>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        {/* Enable checkbox */}
                        <label className="flex items-center gap-1 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={group.enabled}
                            onChange={(e) => setGroups(g => ({ ...g, [mod.name]: { ...group, enabled: e.target.checked } }))}
                            className="h-4 w-4 accent-emerald-700 rounded border-stone-300"
                          />
                          <span className="text-[11px] font-semibold text-stone-500 uppercase">On</span>
                        </label>
                        {/* Weight Field */}
                        <label className="flex items-center gap-1 text-[11px] font-medium text-stone-500">
                          <span>Weight:</span>
                          <input
                            type="number"
                            min={0}
                            value={group.weight}
                            onChange={(e) => setGroups(g => ({ ...g, [mod.name]: { ...group, weight: Number(e.target.value) || 0 } }))}
                            className="w-10 rounded border border-stone-300 bg-white py-0.5 text-center text-xs outline-none focus:border-emerald-700"
                          />
                        </label>
                      </div>
                    </div>

                    {/* Middle: Configuration Schema Fields */}
                    {mod.config_schema?.length > 0 && (
                      <div className="border-t border-stone-100 pt-2 text-xs">
                        <div className="text-[10px] font-bold text-stone-400 uppercase tracking-wider mb-2">Configuration</div>
                        <ModuleConfigEditor
                          module={mod}
                          config={group.config as Record<string, unknown>}
                          onChange={(key, value) => setGroups(g => ({ ...g, [mod.name]: { ...group, config: { ...group.config, [key]: value } } }))}
                        />
                      </div>
                    )}

                    {/* Bottom: Example Preview */}
                    {isExpanded && exampleInfo && (
                      <div className="border-t border-stone-100 pt-2">
                        <div className="flex flex-col gap-2 bg-stone-50 p-2 rounded border border-stone-200">
                          <img
                            src={exampleInfo.image_url}
                            alt={mod.label}
                            className="w-full rounded border border-stone-200 shadow-sm"
                            loading="lazy"
                          />
                          <div className="min-w-0">
                            <div className="text-[9px] font-bold text-stone-400 uppercase tracking-wide">Example Result</div>
                            <div className="text-xs font-semibold text-stone-800">{exampleInfo.title}</div>
                            <div className="text-[11px] text-stone-600 leading-snug mt-0.5">{exampleInfo.summary}</div>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
          
          <div className="flex flex-col sm:flex-row gap-2">
            <button type="button" onClick={() => saveMutation.mutate()}
              disabled={!name.trim() || saveMutation.isPending}
              className="inline-flex items-center justify-center gap-1.5 rounded-md bg-emerald-700 px-3 py-2 text-sm font-semibold text-white hover:bg-emerald-800 disabled:opacity-50 w-full sm:w-auto">
              <Check size={14} /> Save
            </button>
            <button type="button" onClick={closeForm}
              className="inline-flex items-center justify-center gap-1.5 rounded-md border border-stone-300 px-3 py-2 text-sm font-semibold text-stone-700 hover:bg-stone-50 w-full sm:w-auto">
              <X size={14} /> Cancel
            </button>
          </div>
        </div>
      )}

      <div className="grid gap-2">
        {presets.data?.map(p => {
          const enabledEntries = Object.entries(p.groups).filter(([, g]) => g.enabled);
          const enabledNames = enabledEntries.map(([name]) => {
            const mod = modules.data?.find(m => m.name === name);
            return mod?.label ?? name.replace(/_/g, ' ');
          });
          return (
            <div key={p.id} className="flex items-start justify-between gap-3 rounded-md border border-stone-200 bg-white px-3 py-2.5 sm:py-2">
              <div className="min-w-0 flex-1 grid gap-1.5">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-stone-850 truncate">{p.name}</span>
                  <span className="shrink-0 inline-flex items-center justify-center rounded-full bg-emerald-100 text-emerald-800 text-[10px] font-bold px-1.5 py-0.5">
                    {enabledEntries.length} active
                  </span>
                </div>
                {enabledNames.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {enabledNames.map(label => (
                      <span key={label} className="rounded-full bg-stone-100 border border-stone-200 px-2 py-0.5 text-[10px] font-medium text-stone-600">
                        {label}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              <div className="flex gap-1 shrink-0">
                <button type="button" onClick={() => openEdit(p)}
                  className="inline-flex items-center gap-1 rounded px-2.5 py-1.5 sm:py-1 text-xs font-semibold text-stone-500 hover:bg-stone-100 bg-stone-50 sm:bg-transparent">
                  <Pencil size={12} /> Edit
                </button>
                <button type="button" onClick={() => { if (confirm(`Delete "${p.name}"?`)) deleteMutation.mutate(p.id); }}
                  className="inline-flex items-center gap-1 rounded px-2.5 py-1.5 sm:py-1 text-xs font-semibold text-red-500 hover:bg-red-50 bg-red-50/30 sm:bg-transparent">
                  <Trash2 size={12} /> Delete
                </button>
              </div>
            </div>
          );
        })}
        {presets.data?.length === 0 && (
          <EmptyState
            title="No effect presets yet"
            description="Create an effect preset to choose which local and AI modules should run."
            action={(
              <button type="button" onClick={openNew} className="inline-flex items-center gap-1.5 rounded-md bg-emerald-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-800">
                <Plus size={14} /> New preset
              </button>
            )}
          />
        )}
      </div>
    </div>
  );
}

// ── Notification Presets Tab ──────────────────────────────────────────────────

function NotificationPresetsTab() {
  const qc = useQueryClient();
  const presets = useQuery({ queryKey: ['notification-presets'], queryFn: getNotificationPresets });

  const [editing, setEditing] = useState<NotificationPreset | null>(null);
  const [isNew, setIsNew] = useState(false);
  const [form, setForm] = useState({ name: '', channels: ['web'] as string[], url: '', topic: '', token: '', webhook_url: '' });
  const [error, setError] = useState<string | null>(null);

  const CHANNELS = ['web', 'ntfy', 'gotify', 'telegram', 'homeassistant', 'apprise'] as const;
  const CHANNEL_LABELS: Record<(typeof CHANNELS)[number], string> = {
    web: 'Web Push',
    ntfy: 'ntfy',
    gotify: 'Gotify',
    telegram: 'Telegram',
    homeassistant: 'Home Assistant',
    apprise: 'Apprise',
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
      };
      return editing && !isNew ? updateNotificationPreset(editing.id, body) : createNotificationPreset(body);
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['notification-presets'] }); closeForm(); },
    onError: (e: Error) => setError(e.message),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteNotificationPreset(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notification-presets'] }),
    onError: (e: Error) => setError(e.message),
  });

  const [testResult, setTestResult] = useState<{ id: number; msg: string; ok: boolean } | null>(null);
  const testMutation = useMutation({
    mutationFn: (id: number) => testNotificationPreset(id),
    onSuccess: (data, id) => setTestResult({ id, msg: data.sent.join(', ') || data.errors.join(', '), ok: data.ok }),
    onError: (e: Error, id) => setTestResult({ id, msg: e.message, ok: false }),
  });

  function openNew() {
    setForm({ name: '', channels: ['web'], url: '', topic: '', token: '', webhook_url: '' });
    setEditing(null); setIsNew(true); setError(null);
  }

  function openEdit(p: NotificationPreset) {
    const channels = splitNotificationProviders(p.provider);
    setForm({ name: p.name, channels, url: p.url ?? '', topic: p.topic ?? '', token: '', webhook_url: p.webhook_url ?? '' });
    setEditing(p); setIsNew(false); setError(null);
  }

  function closeForm() { setEditing(null); setIsNew(false); setError(null); }

  function toggleChannel(ch: string) {
    setForm(f => ({
      ...f,
      channels: f.channels.includes(ch) ? f.channels.filter(c => c !== ch) : [...f.channels, ch],
    }));
  }

  const showForm = isNew || editing !== null;
  const hasWeb = form.channels.includes('web');
  const hasNtfy = form.channels.includes('ntfy');
  const hasGotify = form.channels.includes('gotify');
  const hasTelegram = form.channels.includes('telegram');
  const hasHomeAssistant = form.channels.includes('homeassistant');
  const hasApprise = form.channels.includes('apprise');
  const needsUrl = hasNtfy || hasGotify || hasHomeAssistant || hasApprise;
  const validationIssues: string[] = [];
  if (!form.name.trim()) validationIssues.push('Preset name is required.');
  if (form.channels.length === 0) validationIssues.push('Select at least one channel.');
  if (needsUrl && !form.url.trim()) validationIssues.push('A server URL is required for the selected channels.');
  if (hasNtfy && !form.topic.trim()) validationIssues.push('ntfy topic is required.');
  if (hasTelegram && !form.topic.trim()) validationIssues.push('Telegram chat ID is required.');
  if (hasHomeAssistant && !form.token.trim() && !editing?.token_masked) validationIssues.push('Home Assistant access token is required.');
  const canSave = validationIssues.length === 0;


  // Web Push state
  const subscriptions = useQuery({ queryKey: ['push-subscriptions'], queryFn: getPushSubscriptions, enabled: hasWeb });
  const deleteSubMutation = useMutation({ mutationFn: deletePushSubscription, onSuccess: () => qc.invalidateQueries({ queryKey: ['push-subscriptions'] }) });
  const [pushSub, setPushSub] = useState<PushSubscription | null>(null);
  const [pushStatus, setPushStatus] = useState<'idle' | 'pending' | 'subscribed' | 'error'>('idle');

  useEffect(() => {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) return;
    navigator.serviceWorker.register('/sw.js').then(reg => {
      reg.pushManager.getSubscription().then(sub => {
        if (sub) { setPushSub(sub); setPushStatus('subscribed'); }
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
        setPushSub(null); setPushStatus('idle');
        qc.invalidateQueries({ queryKey: ['push-subscriptions'] });
      } else {
        const vapidKey = await getVapidPublicKey();
        const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: vapidKey });
        await subscribeWebPush(sub);
        setPushSub(sub); setPushStatus('subscribed');
        qc.invalidateQueries({ queryKey: ['push-subscriptions'] });
      }
    } catch { setPushStatus('idle'); }
  }

  const isLoading = presets.isLoading && !presets.data;
  const isError = presets.isError && !presets.data;

  if (isLoading) {
    return <InlineSpinner />;
  }

  if (isError) {
    return <ErrorBanner title="Could not load notification presets" error={presets.error} onRetry={() => presets.refetch()} />;
  }

  return (
    <div className="grid gap-3">
      <div className="flex items-center justify-between">
        <span className="text-sm text-stone-500">{presets.data?.length ?? 0} preset(s)</span>
        <button type="button" onClick={openNew}
          className="inline-flex items-center gap-1.5 rounded-md bg-emerald-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-800">
          <Plus size={14} /> New preset
        </button>
      </div>

      {error && <InlineError title="Could not save notification preset" message={error} />}

      {showForm && (
        <div className="rounded-xl border border-stone-200 bg-stone-50 p-4 grid gap-4">
          <div className="grid gap-1">
            <div className="text-sm font-semibold text-stone-900">{isNew ? 'New notification preset' : `Editing: ${editing?.name}`}</div>
            <div className="text-xs text-stone-500">Channels are stored as a single preset, but each one keeps its own connection details.</div>
          </div>

          {validationIssues.length > 0 && <InlineError title="Fix the highlighted fields" message={validationIssues.join(' ')} />}

          <SectionCard title="Basics" description="Name the preset and choose where notifications go.">
            <div className="grid gap-3">
              <Field label="Name" required value={form.name} maxLength={255} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
              <div className="grid gap-2">
                <div className="text-sm font-medium text-stone-800">Channels <span className="text-rose-500">*</span></div>
                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {CHANNELS.map(ch => (
                    <label key={ch} className={`flex items-start gap-2 rounded-md border px-3 py-2 text-sm transition-colors ${form.channels.includes(ch) ? 'border-emerald-200 bg-emerald-50/50 text-emerald-900' : 'border-stone-200 bg-white text-stone-700'}`}>
                      <input
                        type="checkbox"
                        checked={form.channels.includes(ch)}
                        onChange={() => toggleChannel(ch)}
                        className="mt-0.5 h-4 w-4 accent-emerald-700"
                      />
                      <div className="grid gap-0.5">
                        <span className="font-medium">{CHANNEL_LABELS[ch]}</span>
                        <span className="text-xs text-stone-500">
                          {ch === 'web' ? 'Browser push notifications.' : ch === 'telegram' ? 'Telegram bot delivery.' : 'External notification provider.'}
                        </span>
                      </div>
                    </label>
                  ))}
                </div>
              </div>
            </div>
          </SectionCard>

          {hasWeb && (
            <SectionCard title="Web Push" description="Manage browser subscriptions for this preset.">
              <div className="grid gap-3">
                <div className="flex flex-wrap items-center gap-2">
                  <button type="button" onClick={handlePushToggle}
                    disabled={pushStatus === 'pending' || !('PushManager' in window)}
                    className="inline-flex h-8 items-center gap-1.5 rounded-md border border-stone-300 bg-white px-3 text-xs font-medium text-stone-700 hover:bg-stone-50 disabled:opacity-50">
                    {pushStatus === 'subscribed' ? <BellOff size={12} /> : <Bell size={12} />}
                    {pushStatus === 'subscribed' ? 'Unsubscribe this browser' : pushStatus === 'pending' ? 'Wait…' : 'Subscribe this browser'}
                  </button>
                  {pushStatus === 'subscribed' && <span className="text-xs font-medium text-emerald-700">Subscribed</span>}
                </div>
                {subscriptions.data && subscriptions.data.subscriptions.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {subscriptions.data.subscriptions.map(sub => {
                      const label = sub.device_label || sub.user_agent || 'Unknown browser';
                      const isMobile = /mobile|android|iphone|ipad/i.test(label);
                      return (
                        <div key={sub.id} className="flex items-center gap-2 rounded-md border border-stone-200 bg-stone-50 px-2 py-1">
                          {isMobile ? <Smartphone size={14} className="shrink-0 text-stone-400" /> : <Monitor size={14} className="shrink-0 text-stone-400" />}
                          <span className="flex-1 truncate text-xs text-stone-700">{label}</span>
                          <button type="button" onClick={() => deleteSubMutation.mutate(sub.id)}
                            disabled={deleteSubMutation.isPending}
                            className="shrink-0 text-stone-400 hover:text-red-600 disabled:opacity-50">
                            <Trash2 size={14} />
                          </button>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </SectionCard>
          )}

          <SectionCard title="Provider settings" description="Fill in the fields required by the selected channels.">
            <div className="grid gap-3">
              {needsUrl && (
                <Field
                  label={hasApprise ? 'Apprise endpoint URL(s)' : 'Endpoint URL'}
                  required
                  type={hasApprise ? 'text' : 'url'}
                  maxLength={2048}
                  value={form.url}
                  onChange={e => setForm(f => ({ ...f, url: e.target.value }))}
                  placeholder={hasApprise ? 'tgram://bot_token/chat_id, mailto://user:pass@gmail.com' : hasHomeAssistant ? 'http://homeassistant.local:8123' : 'https://ntfy.sh'}
                  hint={hasApprise ? 'Required for Apprise.' : hasHomeAssistant ? 'Required for the Home Assistant notify service.' : 'Required for the selected provider(s).'}
                />
              )}
              {hasNtfy && (
                <Field label="Topic" required value={form.topic} maxLength={255} onChange={e => setForm(f => ({ ...f, topic: e.target.value }))} />
              )}
              {hasTelegram && (
                <Field label="Telegram Chat ID" required value={form.topic} maxLength={255} onChange={e => setForm(f => ({ ...f, topic: e.target.value }))} placeholder="-10012345678 or @channelname" />
              )}
              {hasHomeAssistant && (
                <Field
                  label="Notify service name"
                  optional
                  value={form.topic}
                  maxLength={255}
                  onChange={e => setForm(f => ({ ...f, topic: e.target.value }))}
                  placeholder="e.g. notify or mobile_app_phone"
                  hint="Leave blank to use the default notify service."
                />
              )}
              {(hasNtfy || hasGotify || hasTelegram || hasHomeAssistant) && (
                <Field
                  label={hasTelegram ? 'Telegram Bot Token' : hasHomeAssistant ? 'Home Assistant Access Token (LLAT)' : 'Token'}
                  required={hasTelegram || hasHomeAssistant}
                  optional={!hasTelegram && !hasHomeAssistant}
                  type="password"
                  value={form.token}
                  placeholder={editing?.token_masked ?? ''}
                  onChange={e => setForm(f => ({ ...f, token: e.target.value }))}
                />
              )}
              <Field
                label="Webhook URL"
                optional
                type="url"
                maxLength={2048}
                value={form.webhook_url}
                onChange={e => setForm(f => ({ ...f, webhook_url: e.target.value }))}
                placeholder="https://example.com/webhook"
              />
            </div>
          </SectionCard>

          <div className="flex flex-col gap-2 sm:flex-row">
            <button type="button" onClick={() => saveMutation.mutate()}
              disabled={!canSave || saveMutation.isPending}
              className="inline-flex items-center justify-center gap-1.5 rounded-md bg-emerald-700 px-3 py-2 text-sm font-semibold text-white hover:bg-emerald-800 disabled:opacity-50 w-full sm:w-auto">
              <Check size={14} /> Save
            </button>
            <button type="button" onClick={closeForm}
              className="inline-flex items-center justify-center gap-1.5 rounded-md border border-stone-300 px-3 py-2 text-sm font-semibold text-stone-700 hover:bg-stone-50 w-full sm:w-auto">
              <X size={14} /> Cancel
            </button>
          </div>
        </div>
      )}

      <div className="grid gap-2">
        {presets.data?.map(p => (
          <div key={p.id} className="flex flex-col gap-3 rounded-md border border-stone-200 bg-white px-3 py-2.5 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0 grid gap-1">
              <div className="text-sm font-semibold text-stone-900">{p.name}</div>
              <div className="flex flex-wrap gap-1.5">
                <span className="rounded-full bg-stone-100 px-2 py-0.5 text-[11px] font-medium text-stone-600">
                  {formatNotificationProviders(p.provider)}
                </span>
                {p.has_token && (
                  <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700">
                    token set
                  </span>
                )}
              </div>
            </div>
            <div className="flex flex-wrap gap-1.5 shrink-0 items-center">
              <button type="button" onClick={() => testMutation.mutate(p.id)}
                disabled={testMutation.isPending}
                className="inline-flex items-center gap-1 rounded-md border border-stone-300 bg-white px-2.5 py-1.5 text-xs font-medium text-blue-700 hover:bg-blue-50 disabled:opacity-50">
                <Bell size={12} /> Test
              </button>
              {testResult?.id === p.id && (
                <span className={`text-xs ${testResult.ok ? 'text-emerald-700' : 'text-red-600'}`}>{testResult.msg}</span>
              )}
              <button type="button" onClick={() => openEdit(p)}
                className="inline-flex items-center gap-1 rounded-md border border-stone-300 bg-white px-2.5 py-1.5 text-xs font-medium text-stone-600 hover:bg-stone-50">
                <Pencil size={12} /> Edit
              </button>
              <button type="button" onClick={() => { if (confirm(`Delete "${p.name}"?`)) deleteMutation.mutate(p.id); }}
                className="inline-flex items-center gap-1 rounded-md border border-stone-300 bg-white px-2.5 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50">
                <Trash2 size={12} /> Delete
              </button>
            </div>
          </div>
        ))}
        {presets.data?.length === 0 && (
          <EmptyState
            title="No notification presets yet"
            description="Create a notification preset to wire one or more delivery channels into schedules."
            action={(
              <button type="button" onClick={openNew} className="inline-flex items-center gap-1.5 rounded-md bg-emerald-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-800">
                <Plus size={14} /> New preset
              </button>
            )}
          />
        )}
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export function FilterPresetsPage() {
  return (
    <section className="grid gap-4">
      <div className="rounded-lg border border-stone-200 bg-white p-4 grid gap-4">
        <FilterPresetsTab />
      </div>
    </section>
  );
}

export function EffectPresetsPage() {
  return (
    <section className="grid gap-4">
      <div className="rounded-lg border border-stone-200 bg-white p-4 grid gap-4">
        <EffectPresetsTab />
      </div>
    </section>
  );
}

export function NotificationPresetsPage() {
  return (
    <section className="grid gap-4">
      <div className="rounded-lg border border-stone-200 bg-white p-4 grid gap-4">
        <NotificationPresetsTab />
      </div>
    </section>
  );
}
