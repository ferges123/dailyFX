import { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Download, Plus, Upload } from 'lucide-react';
import {
  AIEffectCard,
  emptyForm,
  getAIEffectGroupOrder,
} from './AIEffects/AIEffectCard';
import {
  createAIEffect,
  deleteAIEffect,
  duplicateAIEffect,
  exportAIEffects,
  getAIEffects,
  importAIEffects,
  resetAIEffect,
  updateAIEffect,
  type AIEffect,
  type AIEffectImportRequest,
  type AIEffectUpsert,
} from '../api/client';
import { ErrorBanner, InlineSpinner } from '../components/ErrorUI';
import { EmptyState, InlineError, SectionCard } from '../components/FormUI';
import { Field } from '../components/Field';
import { ConfirmModal } from '../components/ConfirmModal';
import { SearchInput } from '../components/SearchInput';
import { useDebounce } from './History/useDebounce';

type AIEffectFormState = AIEffectUpsert;

export function AIEffectsPage() {
  const qc = useQueryClient();
  const effects = useQuery({ queryKey: ['ai-effects'], queryFn: getAIEffects });
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const formPanelRef = useRef<HTMLDivElement | null>(null);

  const [editing, setEditing] = useState<AIEffect | null>(null);
  const [isNew, setIsNew] = useState(false);
  const [form, setForm] = useState<AIEffectFormState>(emptyForm());
  const [error, setError] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const [groupFilter, setGroupFilter] = useState('all');
  const [effectSearch, setEffectSearch] = useState('');
  const debouncedEffectSearch = useDebounce(effectSearch, 250);
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
      const payload = {
        id: form.id.trim(),
        title: form.title.trim(),
        description: form.description?.trim() || null,
        display_group: form.display_group?.trim() || null,
        positive_prompt: form.positive_prompt.trim(),
        negative_prompt: form.negative_prompt?.trim() || null,
        custom_prompt_placeholder:
          form.custom_prompt_placeholder?.trim() || null,
        enabled: form.enabled,
      };
      return editing && !isNew
        ? updateAIEffect(editing.id, payload)
        : createAIEffect(payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['ai-effects'] });
      closeForm();
    },
    onError: (e: Error) => setError(e.message),
  });

  const resetMutation = useMutation({
    mutationFn: (effect: AIEffect) => resetAIEffect(effect.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ai-effects'] }),
    onError: (e: Error) => setError(e.message),
  });

  const duplicateMutation = useMutation({
    mutationFn: (effect: AIEffect) => duplicateAIEffect(effect.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ai-effects'] }),
    onError: (e: Error) => setError(e.message),
  });

  const deleteMutation = useMutation({
    mutationFn: (effect: AIEffect) => deleteAIEffect(effect.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ai-effects'] }),
    onError: (e: Error) => setError(e.message),
  });

  const exportMutation = useMutation({
    mutationFn: exportAIEffects,
    onSuccess: (data) => {
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: 'application/json',
      });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = 'ai-effects.export.json';
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    },
    onError: (e: Error) => setError(e.message),
  });

  const importMutation = useMutation({
    mutationFn: importAIEffects,
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['ai-effects'] });
      setImportResult(
        `Imported ${data.added.length} added, ${data.updated.length} updated, ${data.conflicts.length} conflicts.`,
      );
    },
    onError: (e: Error) => setError(e.message),
    onSettled: () => setImporting(false),
  });

  const [validationIssues, canSave] = useMemo(() => {
    const issues: string[] = [];
    if (!form.id.trim()) issues.push('Effect id is required.');
    if (!/^[a-z][a-z0-9_]*$/.test(form.id.trim()))
      issues.push(
        'Effect id must use lowercase letters, numbers, and underscores.',
      );
    if (!form.title.trim()) issues.push('Title is required.');
    if (!form.positive_prompt.trim())
      issues.push('Positive prompt is required.');
    return [issues, issues.length === 0] as const;
  }, [form]);

  const groupOptions = useMemo(() => {
    const groups = new Set<string>();
    let hasUngrouped = false;
    for (const effect of effects.data ?? []) {
      const group = effect.display_group?.trim();
      if (group) {
        groups.add(group);
      } else {
        hasUngrouped = true;
      }
    }
    const options = Array.from(groups).sort((a, b) => {
      const aOrder = getAIEffectGroupOrder(a);
      const bOrder = getAIEffectGroupOrder(b);
      if (aOrder !== bOrder) return aOrder - bOrder;
      return a.localeCompare(b);
    });
    if (hasUngrouped) options.push('Ungrouped');
    return options;
  }, [effects.data]);

  const groupedEffects = useMemo(() => {
    const query = debouncedEffectSearch.trim().toLowerCase();
    const visibleEffects = (effects.data ?? []).filter((effect) => {
      if (groupFilter === 'all') {
        // keep
      } else {
        const group = effect.display_group?.trim() || 'Ungrouped';
        if (group !== groupFilter) return false;
      }
      if (!query) return true;
      return (
        effect.title.toLowerCase().includes(query) ||
        effect.id.toLowerCase().includes(query) ||
        (effect.description ?? '').toLowerCase().includes(query) ||
        (effect.display_group ?? '').toLowerCase().includes(query) ||
        effect.positive_prompt.toLowerCase().includes(query)
      );
    });

    const groups = new Map<string, AIEffect[]>();
    for (const effect of visibleEffects) {
      const group = effect.display_group?.trim() || 'Ungrouped';
      const bucket = groups.get(group);
      if (bucket) {
        bucket.push(effect);
      } else {
        groups.set(group, [effect]);
      }
    }

    return Array.from(groups.entries()).sort(([a], [b]) => {
      const aOrder = getAIEffectGroupOrder(a);
      const bOrder = getAIEffectGroupOrder(b);
      if (aOrder !== bOrder) return aOrder - bOrder;
      return a.localeCompare(b);
    });
  }, [effects.data, groupFilter, debouncedEffectSearch]);

  const visibleEffectCount = useMemo(() => {
    if (groupFilter === 'all' && !debouncedEffectSearch.trim())
      return effects.data?.length ?? 0;
    return groupedEffects.reduce((count, [, items]) => count + items.length, 0);
  }, [effects.data, groupFilter, debouncedEffectSearch, groupedEffects]);

  const activeFilterCount =
    (groupFilter !== 'all' ? 1 : 0) + (effectSearch.trim() ? 1 : 0);

  const handleClearFilters = () => {
    setGroupFilter('all');
    setEffectSearch('');
  };

  function openNew() {
    setEditing(null);
    setIsNew(true);
    setForm(emptyForm());
    setError(null);
    setImportResult(null);
  }

  function openEdit(effect: AIEffect) {
    setEditing(effect);
    setIsNew(false);
    setForm({
      id: effect.id,
      title: effect.title,
      description: effect.description ?? '',
      display_group: effect.display_group ?? '',
      positive_prompt: effect.positive_prompt,
      negative_prompt: effect.negative_prompt ?? '',
      custom_prompt_placeholder: effect.custom_prompt_placeholder ?? '',
      enabled: effect.enabled,
    });
    setError(null);
    setImportResult(null);
  }

  function closeForm() {
    setEditing(null);
    setIsNew(false);
    setForm(emptyForm());
    setError(null);
  }

  async function handleImportFile(file: File | null) {
    if (!file) return;
    setImporting(true);
    setError(null);
    setImportResult(null);
    try {
      const parsed = JSON.parse(await file.text()) as AIEffectImportRequest;
      await importMutation.mutateAsync({
        schema_version: parsed.schema_version ?? 1,
        overwrite_existing: parsed.overwrite_existing ?? false,
        effects: parsed.effects ?? [],
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Invalid import file');
      setImporting(false);
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  }

  const isLoading = effects.isLoading && !effects.data;
  const isError = effects.isError && !effects.data;
  const showForm = isNew || editing !== null;

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
    return (
      <ErrorBanner
        title="Could not load AI effects"
        error={effects.error}
        onRetry={() => effects.refetch()}
      />
    );
  }

  return (
    <div className="grid gap-3">
      <div className="app-panel grid gap-2 p-2 md:flex md:flex-wrap md:items-center md:gap-1.5">
        <span className="inline-flex h-9 items-center rounded-xl bg-stone-100 px-2.5 text-xs font-semibold text-stone-600 md:shrink-0">
          {effects.data?.length ?? 0} preset(s)
        </span>
        <div className="w-full md:w-64 md:shrink-0">
          <SearchInput
            value={effectSearch}
            onSearch={setEffectSearch}
            onClear={() => setEffectSearch('')}
            placeholder="Search effects..."
            aria-label="Search AI effects"
            inputClassName="app-control app-control-muted h-9 pl-9 pr-8 text-sm"
            iconSize={14}
          />
        </div>
        <div className="w-full md:w-48 md:shrink-0">
          <select
            aria-label="AI effects group filter"
            value={groupFilter}
            onChange={(e) => setGroupFilter(e.target.value)}
            className="app-control app-control-muted h-9 cursor-pointer px-3 text-sm"
          >
            <option value="all">All groups</option>
            {groupOptions.map((group) => (
              <option key={group} value={group}>
                {group}
              </option>
            ))}
          </select>
        </div>
        {activeFilterCount > 0 && (
          <button
            type="button"
            onClick={handleClearFilters}
            className="app-button-ghost h-9 px-3 text-xs"
          >
            Reset
          </button>
        )}
        <div
          aria-label="AI effects header actions"
          className="order-first flex w-full flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center sm:justify-end md:order-none md:ml-auto md:w-auto md:flex-nowrap"
        >
          <button
            type="button"
            onClick={openNew}
            className="app-button-primary w-full justify-center px-3 py-2 text-sm sm:w-auto sm:py-1.5"
          >
            <Plus size={14} /> New effect
          </button>
          <button
            type="button"
            onClick={() => exportMutation.mutate()}
            className="app-button-secondary w-full justify-center px-3 py-2 text-sm sm:w-auto sm:py-1.5"
          >
            <Download size={14} /> Export
          </button>
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={importing}
            className="app-button-secondary w-full justify-center px-3 py-2 text-sm disabled:opacity-50 sm:w-auto sm:py-1.5"
          >
            <Upload size={14} /> Import
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept="application/json,.json"
            className="hidden"
            onChange={(e) => handleImportFile(e.target.files?.[0] ?? null)}
          />
        </div>
      </div>

      {error && <InlineError title="AI effect action failed" message={error} />}
      {importResult && (
        <InlineError title="Import result" message={importResult} />
      )}

      {validationIssues.length > 0 && showForm && (
        <InlineError
          title="Fix the highlighted fields"
          message={validationIssues.join(' ')}
        />
      )}

      {showForm && (
        <div ref={formPanelRef} className="app-panel grid gap-4 p-4">
          <div className="flex items-center gap-1.5">
            <div className="text-sm font-semibold text-stone-900">
              {isNew ? 'New AI effect' : `Editing: ${editing?.title}`}
            </div>
          </div>

          <SectionCard
            title="Basics"
            description="Title, identifier, and availability."
          >
            <div className="grid gap-3 sm:grid-cols-2">
              <Field
                label="ID"
                required
                value={form.id}
                onChange={(e) => setForm((f) => ({ ...f, id: e.target.value }))}
                disabled={!isNew}
                placeholder="ai_custom_style"
              />
              <Field
                label="Title"
                required
                value={form.title}
                onChange={(e) =>
                  setForm((f) => ({ ...f, title: e.target.value }))
                }
                placeholder="My Custom AI Effect"
              />
              <label className="flex items-center gap-2 rounded-2xl border border-stone-200 bg-white px-3 py-2 text-sm text-stone-700">
                <input
                  type="checkbox"
                  checked={form.enabled}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, enabled: e.target.checked }))
                  }
                  className="h-4 w-4 accent-emerald-700"
                />
                Enabled
              </label>
              <div className="sm:col-span-2">
                <Field
                  label="Description"
                  value={form.description ?? ''}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, description: e.target.value }))
                  }
                  optional
                />
              </div>
              <div className="sm:col-span-2">
                <Field
                  label="Group"
                  value={form.display_group ?? ''}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, display_group: e.target.value }))
                  }
                  optional
                  placeholder="Illustration"
                />
              </div>
            </div>
          </SectionCard>

          <SectionCard
            title="Prompts"
            description="Seed fields that can be edited locally on built-in effects."
          >
            <div className="grid gap-3">
              <label className="grid gap-1.5 text-sm font-medium text-stone-800">
                <span className="flex items-center gap-1 text-xs font-semibold uppercase tracking-[0.18em] text-stone-500">
                  <span>Positive prompt</span>
                  <span className="text-rose-500">*</span>
                </span>
                <textarea
                  value={form.positive_prompt}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, positive_prompt: e.target.value }))
                  }
                  rows={7}
                  className="app-control min-h-40 resize-y px-3 py-2 text-sm"
                  placeholder="Describe the exact transformation the model should apply."
                />
              </label>
              <label className="grid gap-1.5 text-sm font-medium text-stone-800">
                <span className="flex items-center gap-1 text-xs font-semibold uppercase tracking-[0.18em] text-stone-500">
                  <span>Negative prompt</span>
                </span>
                <textarea
                  value={form.negative_prompt ?? ''}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, negative_prompt: e.target.value }))
                  }
                  rows={5}
                  className="app-control min-h-32 resize-y px-3 py-2 text-sm"
                  placeholder="Things to avoid."
                />
              </label>
              <Field
                label="Custom prompt placeholder"
                value={form.custom_prompt_placeholder ?? ''}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    custom_prompt_placeholder: e.target.value,
                  }))
                }
                optional
                placeholder="e.g. Studio Ghibli style, soft watercolor..."
              />
            </div>
          </SectionCard>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => saveMutation.mutate()}
              disabled={!canSave || saveMutation.isPending}
              className="app-button-primary px-3 py-2 text-sm disabled:opacity-50"
            >
              Save
            </button>
            <button
              type="button"
              onClick={closeForm}
              className="app-button-secondary px-3 py-2 text-sm"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      <div className="grid gap-2">
        {visibleEffectCount === 0 && (
          <EmptyState
            title={
              debouncedEffectSearch.trim()
                ? 'No AI effects match your search'
                : 'No AI effects in this group'
            }
            description={
              debouncedEffectSearch.trim()
                ? 'Try a different keyword or clear the filters.'
                : 'Try another group filter or create a new effect.'
            }
            action={
              <button
                type="button"
                onClick={openNew}
                className="app-button-primary px-3 py-1.5 text-sm"
              >
                <Plus size={14} /> New effect
              </button>
            }
          />
        )}
        {groupedEffects.map(([groupName, items]) => (
          <SectionCard
            key={groupName}
            title={groupName}
            description={`${items.length} effect${items.length === 1 ? '' : 's'}`}
          >
            <div
              aria-label={`AI effects list: ${groupName}`}
              className="grid gap-2 lg:grid-cols-2"
            >
              {items.map((effect) => (
                <AIEffectCard
                  key={effect.id}
                  effect={effect}
                  onEdit={openEdit}
                  onDuplicate={(item) => {
                    setConfirmConfig({
                      isOpen: true,
                      title: 'Duplicate AI Effect',
                      description: `Are you sure you want to duplicate "${item.title}"?`,
                      confirmLabel: 'Duplicate',
                      variant: 'info',
                      onConfirm: () => duplicateMutation.mutate(item),
                    });
                  }}
                  onReset={(item) => {
                    setConfirmConfig({
                      isOpen: true,
                      title: 'Reset AI Effect',
                      description: `Are you sure you want to reset "${item.title}" to the built-in default?`,
                      confirmLabel: 'Reset',
                      variant: 'warning',
                      onConfirm: () => resetMutation.mutate(item),
                    });
                  }}
                  onDelete={(item) => {
                    const verb =
                      item.source === 'builtin' ? 'disable' : 'delete';
                    setConfirmConfig({
                      isOpen: true,
                      title: `${verb === 'disable' ? 'Disable' : 'Delete'} AI Effect`,
                      description: `Are you sure you want to ${verb} "${item.title}"?`,
                      confirmLabel: verb === 'disable' ? 'Disable' : 'Delete',
                      variant: 'danger',
                      onConfirm: () => deleteMutation.mutate(item),
                    });
                  }}
                />
              ))}
            </div>
          </SectionCard>
        ))}
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
