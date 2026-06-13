import { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Copy,
  Download,
  MoreHorizontal,
  Pencil,
  Plus,
  RefreshCcw,
  Trash2,
  Upload,
} from 'lucide-react';
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

const AI_EFFECT_GROUP_ORDER = [
  'Portrait',
  'Illustration',
  'Poster',
  '3D / Toy',
  'Pop Culture',
  'Cinematic',
  'Sci-Fi',
  'Horror',
  'Historical',
  'Ungrouped',
];

function getAIEffectGroupOrder(group: string): number {
  const index = AI_EFFECT_GROUP_ORDER.indexOf(group);
  return index === -1 ? Number.POSITIVE_INFINITY : index;
}

type AIEffectFormState = AIEffectUpsert;

function emptyForm(): AIEffectFormState {
  return {
    id: '',
    title: '',
    description: '',
    display_group: '',
    positive_prompt: '',
    negative_prompt: '',
    custom_prompt_placeholder: '',
    enabled: true,
  };
}

function formatStatus(effect: AIEffect): string[] {
  const tags: string[] = [];
  if (effect.source === 'builtin') {
    tags.push('Built-in');
    if (effect.user_modified_at) tags.push('Modified locally');
    if (
      effect.user_modified_at &&
      effect.builtin_hash &&
      effect.latest_builtin_hash &&
      effect.builtin_hash !== effect.latest_builtin_hash
    ) {
      tags.push('Default changed');
    }
  } else if (effect.source === 'custom') {
    tags.push('Custom');
  } else {
    tags.push('Imported');
  }
  if (!effect.enabled) tags.push('Disabled');
  return tags;
}

function AIEffectCard({
  effect,
  onEdit,
  onDuplicate,
  onReset,
  onDelete,
}: {
  effect: AIEffect;
  onEdit: (effect: AIEffect) => void;
  onDuplicate: (effect: AIEffect) => void;
  onReset: (effect: AIEffect) => void;
  onDelete: (effect: AIEffect) => void;
}) {
  const statusTags = formatStatus(effect);
  const [showPrompts, setShowPrompts] = useState(false);
  const [showActions, setShowActions] = useState(false);

  return (
    <div
      className={`grid gap-2 rounded-xl border px-3 py-2.5 ${effect.enabled ? 'border-stone-200/80 bg-white/85' : 'border-stone-200 bg-stone-50/80'}`}
    >
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 grid gap-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold text-stone-900">
              {effect.title}
            </span>
            <span className="app-chip px-2 py-0.5 text-[10px]">
              {effect.id}
            </span>
            {effect.display_group && (
              <span className="app-chip px-2 py-0.5 text-[10px]">
                group {effect.display_group}
              </span>
            )}
          </div>
          <div className="flex flex-wrap gap-1.5">
            {statusTags.map((tag) => (
              <span
                key={tag}
                className="app-chip px-2 py-0.5 text-[10px] font-medium"
              >
                {tag}
              </span>
            ))}
          </div>
        </div>
        <div className="relative flex flex-wrap gap-1.5 sm:justify-end">
          <button
            type="button"
            onClick={() => onEdit(effect)}
            aria-label={`Edit ${effect.title}`}
            className="app-button-secondary px-2.5 py-1.5 text-xs"
          >
            <Pencil size={12} /> Edit
          </button>
          <button
            type="button"
            onClick={() => setShowActions((current) => !current)}
            aria-expanded={showActions}
            aria-label={`More actions for ${effect.title}`}
            className="app-button-secondary px-2 py-1.5 text-xs"
          >
            <MoreHorizontal size={14} />
          </button>
          {showActions && (
            <div className="z-10 flex w-full flex-wrap gap-1.5 rounded-xl border border-stone-200 bg-white p-1.5 shadow-sm sm:absolute sm:right-0 sm:top-9 sm:w-56 sm:flex-col">
              <button
                type="button"
                onClick={() => {
                  setShowActions(false);
                  onDuplicate(effect);
                }}
                aria-label={`Duplicate ${effect.title}`}
                className="app-button-secondary justify-start px-2.5 py-1.5 text-xs"
              >
                <Copy size={12} /> Duplicate
              </button>
              {effect.source === 'builtin' && (
                <button
                  type="button"
                  onClick={() => {
                    setShowActions(false);
                    onReset(effect);
                  }}
                  aria-label={`Reset ${effect.title}`}
                  className="app-button-secondary justify-start px-2.5 py-1.5 text-xs text-blue-700"
                >
                  <RefreshCcw size={12} /> Reset
                </button>
              )}
              <button
                type="button"
                onClick={() => {
                  setShowActions(false);
                  onDelete(effect);
                }}
                aria-label={`Delete ${effect.title}`}
                className="app-button-secondary justify-start px-2.5 py-1.5 text-xs text-rose-700"
              >
                <Trash2 size={12} /> Delete
              </button>
            </div>
          )}
        </div>
      </div>

      {effect.description && (
        <div className="text-xs leading-5 text-stone-600">
          {effect.description}
        </div>
      )}

      <div className="flex flex-wrap gap-1.5">
        <button
          type="button"
          onClick={() => setShowPrompts((current) => !current)}
          className="app-button-secondary px-2.5 py-1.5 text-xs"
        >
          {showPrompts ? 'Hide prompts' : 'Show prompts'}
        </button>
      </div>

      {showPrompts && (
        <div className="grid gap-2 sm:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
          <div className="grid gap-1.5">
            <div className="text-[10px] font-bold uppercase tracking-wide text-stone-400">
              Positive prompt
            </div>
            <pre className="max-h-28 overflow-auto whitespace-pre-wrap rounded-xl border border-stone-200 bg-stone-50 px-3 py-2 text-xs leading-5 text-stone-700">
              {effect.positive_prompt}
            </pre>
          </div>
          <div className="grid gap-1.5">
            <div className="text-[10px] font-bold uppercase tracking-wide text-stone-400">
              Negative prompt
            </div>
            <pre className="max-h-28 overflow-auto whitespace-pre-wrap rounded-xl border border-stone-200 bg-stone-50 px-3 py-2 text-xs leading-5 text-stone-700">
              {effect.negative_prompt || 'None'}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}

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
    const visibleEffects = (effects.data ?? []).filter((effect) => {
      if (groupFilter === 'all') return true;
      const group = effect.display_group?.trim() || 'Ungrouped';
      return group === groupFilter;
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
  }, [effects.data, groupFilter]);

  const visibleEffectCount = useMemo(() => {
    if (groupFilter === 'all') return effects.data?.length ?? 0;
    return groupedEffects.reduce((count, [, items]) => count + items.length, 0);
  }, [effects.data, groupFilter, groupedEffects]);

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
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <span className="text-sm text-stone-500">
          {effects.data?.length ?? 0} preset(s)
        </span>
        <div
          aria-label="AI effects header actions"
          className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center sm:justify-end"
        >
          <select
            aria-label="AI effects group filter"
            value={groupFilter}
            onChange={(e) => setGroupFilter(e.target.value)}
            className="app-control h-9 w-full px-3 py-1.5 text-sm sm:w-48"
          >
            <option value="all">All groups</option>
            {groupOptions.map((group) => (
              <option key={group} value={group}>
                {group}
              </option>
            ))}
          </select>
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
            title="No AI effects in this group"
            description="Try another group filter or create a new effect."
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
                    if (confirm(`Duplicate "${item.title}"?`))
                      duplicateMutation.mutate(item);
                  }}
                  onReset={(item) => {
                    if (
                      confirm(`Reset "${item.title}" to the built-in default?`)
                    )
                      resetMutation.mutate(item);
                  }}
                  onDelete={(item) => {
                    const verb =
                      item.source === 'builtin' ? 'disable' : 'delete';
                    if (
                      confirm(
                        `${verb === 'disable' ? 'Disable' : 'Delete'} "${item.title}"?`,
                      )
                    )
                      deleteMutation.mutate(item);
                  }}
                />
              ))}
            </div>
          </SectionCard>
        ))}
      </div>
    </div>
  );
}
