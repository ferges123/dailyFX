import { useState, useEffect, useRef, Fragment } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Eye, Plus, Pencil, Trash2 } from 'lucide-react';
import { InlineSpinner, ErrorBanner } from '../../components/ErrorUI';
import { EmptyState, InlineError } from '../../components/FormUI';
import {
  getEffectPresets,
  createEffectPreset,
  updateEffectPreset,
  deleteEffectPreset,
  getGenerationModules,
  getGenerationExamples,
  type EffectPreset,
  type GenerationModuleInfo,
} from '../../api/client';
import { Field } from '../../components/Field';
import { ConfirmModal } from '../../components/ConfirmModal';
import { FilterRow, ModuleConfigEditor } from '../../components/EffectsComponents';
import {
  createDefaultModificationGroups,
  parseModificationGroups,
} from '../automation.utils';
import { type ModificationGroupsConfig } from '../automation.types';
import { PresetHeader, PresetFormActions, PresetActionRow } from './PresetHeader';

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

export function EffectPresetsTab() {
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
  const formPanelRef = useRef<HTMLDivElement | null>(null);
  const [confirmConfig, setConfirmConfig] = useState<{
    isOpen: boolean;
    title: string;
    description: string;
    confirmLabel?: string;
    onConfirm: () => void;
    variant?: 'danger' | 'warning' | 'info';
  } | null>(null);

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

  const currentModules =
    effectTab === 'local'
      ? localModules
      : aiModules;
  const isLoading = presets.isLoading && !presets.data;
  const isError = presets.isError && !presets.data;
  const validationIssues: string[] = [];
  if (!name.trim()) validationIssues.push('Preset name is required.');
  if (activeLocalCount + activeAiCount === 0)
    validationIssues.push('Enable at least one effect before saving.');
  const canSave = validationIssues.length === 0;

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
        <div
          ref={formPanelRef}
          className="app-panel grid gap-2.5 p-3 md:gap-3 md:p-4"
        >
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

      <div aria-label="Effect presets list" className="grid gap-2 lg:grid-cols-2">
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
                    setConfirmConfig({
                      isOpen: true,
                      title: 'Delete Effect Preset',
                      description: `Are you sure you want to delete "${p.name}"?`,
                      confirmLabel: 'Delete',
                      variant: 'danger',
                      onConfirm: () => deleteMutation.mutate(p.id),
                    });
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

      {confirmConfig && (
        <ConfirmModal
          isOpen={confirmConfig.isOpen}
          title={confirmConfig.title}
          description={confirmConfig.description}
          confirmLabel={confirmConfig.confirmLabel}
          variant={confirmConfig.variant}
          onConfirm={() => {
            confirmConfig.onConfirm();
            setConfirmConfig(null);
          }}
          onClose={() => setConfirmConfig(null)}
        />
      )}
    </div>
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
