import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CalendarDays, Check, Pencil, Play, Plus, RefreshCw, ToggleLeft, ToggleRight, Trash2, X } from 'lucide-react';
import {
  getSchedules, createSchedule, updateSchedule, deleteSchedule, triggerScheduleNow,
  getFilterPresets, getEffectPresets, getNotificationPresets,
  type Schedule,
} from '../api/client';
import { Field, SelectField } from '../components/Field';
import { EmptyState, InlineError, ProviderModelField, SectionCard } from '../components/FormUI';
import {
  parseAutomationSchedule,
  serializeAutomationSchedule,
  describeAutomationSchedule,
} from './automation.utils';
import { automationScheduleModeOptions, weekdayOptions, type AutomationScheduleMode } from './automation.types';
import { formatDateTime } from './datetime.utils';
import { getVisionModelOptions, getImageModelOptions } from './Settings';

import { InlineSpinner, ErrorBanner } from '../components/ErrorUI';

type FormState = {
  name: string;
  enabled: boolean;
  scheduleMode: AutomationScheduleMode;
  scheduleDays: number[];
  scheduleTime: string;
  filter_preset_id: number | '';
  effect_preset_id: number | '';
  notification_preset_ids: number[];
  album_name: string;
  ai_vision_provider: string;
  ai_vision_model: string;
  ai_image_provider: string;
  ai_image_model: string;
  ai_prompt_enrichment: boolean;
};

const emptyForm: FormState = {
  name: '', enabled: false,
  scheduleMode: 'daily', scheduleDays: [], scheduleTime: '08:00',
  filter_preset_id: '', effect_preset_id: '', notification_preset_ids: [],
  album_name: 'AI Photos',
  ai_vision_provider: 'none', ai_vision_model: 'gpt-4o-mini',
  ai_image_provider: 'none', ai_image_model: 'gpt-image-1',
  ai_prompt_enrichment: false,
};

function scheduleToForm(s: Schedule): FormState {
  const parsed = parseAutomationSchedule(s.schedule_expr);
  return {
    name: s.name, enabled: s.enabled,
    scheduleMode: parsed.mode, scheduleDays: parsed.days, scheduleTime: parsed.time,
    filter_preset_id: s.filter_preset_id,
    effect_preset_id: s.effect_preset_id,
    notification_preset_ids: s.notification_preset_ids ?? [],
    album_name: s.album_name,
    ai_vision_provider: s.ai_vision_provider ?? 'none',
    ai_vision_model: s.ai_vision_model ?? 'gpt-4o-mini',
    ai_image_provider: s.ai_image_provider ?? 'none',
    ai_image_model: s.ai_image_model ?? 'gpt-image-1',
    ai_prompt_enrichment: s.ai_prompt_enrichment ?? false,
  };
}

function statusBadge(status: string | null) {
  if (!status) return null;
  const colors: Record<string, string> = {
    completed: 'bg-emerald-100 text-emerald-800',
    started: 'bg-blue-100 text-blue-800',
    error: 'bg-red-100 text-red-800',
    not_due: 'bg-stone-100 text-stone-600',
    disabled: 'bg-stone-100 text-stone-400',
  };
  return (
    <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${colors[status] ?? 'bg-stone-100 text-stone-600'}`}>
      {status}
    </span>
  );
}

function scheduleEnabledClass(enabled: boolean) {
  return enabled ? 'border-emerald-200 bg-emerald-50/40' : 'border-stone-200 bg-white';
}

function tickSummary(status: string | null, reason: string | null) {
  if (!status) return 'No runs yet';
  return reason ? `${status} · ${reason}` : status;
}

export function SchedulesPage() {
  const qc = useQueryClient();
  const schedules = useQuery({ queryKey: ['schedules'], queryFn: getSchedules });
  const filterPresets = useQuery({ queryKey: ['filter-presets'], queryFn: getFilterPresets });
  const effectPresets = useQuery({ queryKey: ['effect-presets'], queryFn: getEffectPresets });
  const notifPresets = useQuery({ queryKey: ['notification-presets'], queryFn: getNotificationPresets });

  const [editing, setEditing] = useState<Schedule | null>(null);
  const [isNew, setIsNew] = useState(false);
  const [form, setForm] = useState<FormState>(emptyForm);
  const [error, setError] = useState<string | null>(null);
  const [runningId, setRunningId] = useState<number | null>(null);

  const saveMutation = useMutation({
    mutationFn: () => {
      const schedule_expr = serializeAutomationSchedule({
        mode: form.scheduleMode, days: form.scheduleDays, time: form.scheduleTime,
      });
      const body = {
        name: form.name, enabled: form.enabled, schedule_expr,
        filter_preset_id: Number(form.filter_preset_id),
        effect_preset_id: Number(form.effect_preset_id),
        notification_preset_ids: form.notification_preset_ids,
        album_name: form.album_name,
        ai_vision_provider: form.ai_vision_provider,
        ai_vision_model: form.ai_vision_model,
        ai_image_provider: form.ai_image_provider,
        ai_image_model: form.ai_image_model,
        ai_prompt_enrichment: form.ai_prompt_enrichment,
      };
      return editing && !isNew ? updateSchedule(editing.id, body) : createSchedule(body);
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['schedules'] }); closeForm(); },
    onError: (e: Error) => setError(e.message),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteSchedule(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['schedules'] }),
    onError: (e: Error) => setError(e.message),
  });

  const toggleMutation = useMutation({
    mutationFn: (s: Schedule) => updateSchedule(s.id, {
      name: s.name, enabled: !s.enabled, schedule_expr: s.schedule_expr,
      filter_preset_id: s.filter_preset_id, effect_preset_id: s.effect_preset_id,
      notification_preset_ids: s.notification_preset_ids ?? [], album_name: s.album_name,
      ai_vision_provider: s.ai_vision_provider, ai_vision_model: s.ai_vision_model,
      ai_image_provider: s.ai_image_provider, ai_image_model: s.ai_image_model,
      ai_prompt_enrichment: s.ai_prompt_enrichment ?? false,
    }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['schedules'] }),
    onError: (e: Error) => setError(e.message),
  });

  const runMutation = useMutation({
    mutationFn: (id: number) => triggerScheduleNow(id),
    onMutate: (id) => setRunningId(id),
    onSuccess: (data) => {
      if (data?.task_id) {
        sessionStorage.setItem('dailyfx_last_started_task_id', data.task_id);
      }
    },
    onSettled: () => { setRunningId(null); qc.invalidateQueries({ queryKey: ['schedules'] }); },
    onError: (e: Error) => setError(e.message),
  });

  function openNew() { setForm(emptyForm); setEditing(null); setIsNew(true); setError(null); }
  function openEdit(s: Schedule) { setForm(scheduleToForm(s)); setEditing(s); setIsNew(false); setError(null); }
  function closeForm() { setEditing(null); setIsNew(false); setError(null); }

  function toggleDay(day: number) {
    setForm(f => ({
      ...f,
      scheduleMode: 'custom',
      scheduleDays: f.scheduleDays.includes(day)
        ? f.scheduleDays.filter(d => d !== day)
        : [...f.scheduleDays, day].sort((a, b) => a - b),
    }));
  }

  const showForm = isNew || editing !== null;
  const validationIssues: string[] = [];
  if (!form.name.trim()) validationIssues.push('Schedule name is required.');
  if (form.filter_preset_id === '') validationIssues.push('Choose a filter preset.');
  if (form.effect_preset_id === '') validationIssues.push('Choose an effect preset.');
  if (form.scheduleMode === 'custom' && form.scheduleDays.length === 0) validationIssues.push('Custom schedules need at least one weekday.');
  const canSave = validationIssues.length === 0;
  const anyLoading = schedules.isLoading || filterPresets.isLoading || effectPresets.isLoading || notifPresets.isLoading;
  const anyError = schedules.error || filterPresets.error || effectPresets.error || notifPresets.error;

  if (anyLoading) {
    return <InlineSpinner />;
  }

  if (anyError) {
    const errorMsg = schedules.error || filterPresets.error || effectPresets.error || notifPresets.error;
    return (
      <ErrorBanner
        error={errorMsg}
        onRetry={() => {
          schedules.refetch();
          filterPresets.refetch();
          effectPresets.refetch();
          notifPresets.refetch();
        }}
      />
    );
  }

  return (
    <section className="grid gap-4">
      <div className="rounded-lg border border-stone-200 bg-white p-4 grid gap-4">
        <div className="flex items-start justify-between gap-2">
          <div>
            <h2 className="text-base font-semibold text-stone-950">Schedules</h2>
            <p className="text-sm text-stone-500">Automated generation schedules with preset configurations.</p>
          </div>
          <button type="button" onClick={openNew}
            className="inline-flex items-center gap-1.5 rounded-md bg-emerald-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-800 shrink-0">
            <Plus size={14} /> New schedule
          </button>
        </div>

        {error && <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}

        {/* Form */}
        {showForm && (
          <div className="rounded-xl border border-stone-200 bg-stone-50 p-4 grid gap-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-stone-900">
                  {isNew ? 'New schedule' : `Editing: ${editing?.name}`}
                </div>
                <div className="text-xs text-stone-500">Required fields are marked with an asterisk.</div>
              </div>
              <div className="text-xs text-stone-500">
                {describeAutomationSchedule({ mode: form.scheduleMode, days: form.scheduleDays, time: form.scheduleTime })}
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
              description="Choose the schedule name and target album."
            >
              <div className="grid gap-3 sm:grid-cols-2">
                <Field
                  label="Name"
                  required
                  value={form.name}
                  maxLength={255}
                  onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  className="text-xs"
                  hint="Shown in the schedules list."
                />
                <Field
                  label="Album name"
                  required
                  value={form.album_name}
                  maxLength={255}
                  onChange={e => setForm(f => ({ ...f, album_name: e.target.value }))}
                  className="text-xs"
                  hint="The album created or updated on run."
                />
              </div>
            </SectionCard>

            <SectionCard
              title="Schedule"
              description="Pick when the job runs and how much control you need."
            >
              <div className="grid gap-3">
                <div className="flex flex-wrap gap-1.5">
                  {automationScheduleModeOptions.map(opt => (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => {
                        const days = opt.value === 'weekdays' ? [0, 1, 2, 3, 4] : opt.value === 'weekends' ? [5, 6] : [];
                        setForm(f => ({ ...f, scheduleMode: opt.value, scheduleDays: days }));
                      }}
                      className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                        form.scheduleMode === opt.value
                          ? 'border-emerald-500 bg-emerald-50 text-emerald-800'
                          : 'border-stone-300 bg-white text-stone-700 hover:border-emerald-300'
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
                {form.scheduleMode === 'custom' && (
                  <div className="flex flex-wrap gap-1.5">
                    {weekdayOptions.map(d => (
                      <button
                        key={d.value}
                        type="button"
                        onClick={() => toggleDay(d.value)}
                        className={`rounded border px-2.5 py-1 text-xs font-medium transition-colors ${
                          form.scheduleDays.includes(d.value)
                            ? 'border-emerald-500 bg-emerald-50 text-emerald-800'
                            : 'border-stone-300 bg-white text-stone-600 hover:border-emerald-300'
                        }`}
                      >
                        {d.label}
                      </button>
                    ))}
                  </div>
                )}
                <div className="grid gap-3 sm:grid-cols-[140px_1fr] sm:items-end">
                  <label className="grid gap-1 text-sm font-medium text-stone-800">
                    <span className="flex items-center gap-1">
                      <span>Time</span>
                      <span className="text-rose-500">*</span>
                    </span>
                    <input
                      type="time"
                      value={form.scheduleTime}
                      onChange={e => setForm(f => ({ ...f, scheduleTime: e.target.value }))}
                      className="h-9 w-full min-w-0 rounded-md border border-stone-300 bg-white px-3 text-sm outline-none focus:border-emerald-700"
                    />
                  </label>
                  <div className="rounded-md bg-stone-100 px-3 py-2 text-xs leading-5 text-stone-600">
                    {describeAutomationSchedule({ mode: form.scheduleMode, days: form.scheduleDays, time: form.scheduleTime })}
                  </div>
                </div>
              </div>
            </SectionCard>

            <SectionCard
              title="Presets"
              description="Link the filter, effect, and notification presets used by the run."
            >
              <div className="grid gap-3 lg:grid-cols-3">
                <SelectField label="Filter preset" value={String(form.filter_preset_id)} required className="text-xs" onChange={e => setForm(f => ({ ...f, filter_preset_id: e.target.value ? Number(e.target.value) : '' }))}>
                  <option value="">Select a filter preset</option>
                  {filterPresets.data?.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                </SelectField>
                <SelectField label="Effect preset" value={String(form.effect_preset_id)} required className="text-xs" onChange={e => setForm(f => ({ ...f, effect_preset_id: e.target.value ? Number(e.target.value) : '' }))}>
                  <option value="">Select an effect preset</option>
                  {effectPresets.data?.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                </SelectField>
                <div className="grid gap-1">
                  <div className="text-sm font-medium text-stone-800">
                    Notification presets <span className="text-rose-500">*</span>
                  </div>
                  <div className="rounded-md border border-stone-300 bg-white p-2">
                    <div className="flex flex-wrap gap-1.5">
                      {notifPresets.data?.filter(p => form.notification_preset_ids.includes(p.id)).map(p => (
                        <span key={p.id} className="inline-flex items-center gap-1 rounded-full border border-stone-200 bg-stone-100 px-2 py-0.5 text-[11px] font-medium text-stone-800">
                          {p.name}
                          <button
                            type="button"
                            onClick={() => setForm(f => ({ ...f, notification_preset_ids: f.notification_preset_ids.filter(x => x !== p.id) }))}
                            className="rounded-sm p-0.5 text-stone-400 hover:text-stone-700"
                          >
                            <X size={10} />
                          </button>
                        </span>
                      ))}
                      {form.notification_preset_ids.length === 0 && (
                        <span className="text-xs text-stone-500">No notification presets selected.</span>
                      )}
                    </div>
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <select
                        value=""
                        onChange={e => {
                          const id = Number(e.target.value);
                          if (id && !form.notification_preset_ids.includes(id)) {
                            setForm(f => ({ ...f, notification_preset_ids: [...f.notification_preset_ids, id] }));
                          }
                        }}
                        className="h-9 rounded-md border border-stone-300 bg-white px-2 text-xs outline-none focus:border-emerald-700"
                      >
                        <option value="">Add notification preset</option>
                        {notifPresets.data
                          ?.filter(p => !form.notification_preset_ids.includes(p.id))
                          .map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                      </select>
                      <span className="text-xs text-stone-500">You can attach more than one channel preset.</span>
                    </div>
                  </div>
                </div>
              </div>
            </SectionCard>

            <SectionCard
              title="AI settings"
              description="Optional. Enable one or both providers to enrich prompts."
            >
              <div className="grid gap-3">
                <ProviderModelField
                  label="Vision"
                  provider={form.ai_vision_provider}
                  providerOptions={[
                    { label: 'OpenAI', value: 'openai' },
                    { label: 'Gemini', value: 'gemini' },
                    { label: 'Xiaomi', value: 'xiaomi' },
                    { label: 'OpenRouter', value: 'openrouter' },
                    { label: 'Local AI', value: 'local' },
                  ]}
                  onProviderChange={(p) => {
                    setForm(f => {
                      const next = { ...f, ai_vision_provider: p };
                      if (p !== 'openrouter') {
                        const opts = getVisionModelOptions(p);
                        if (!opts.some((o) => o.value === f.ai_vision_model)) {
                          next.ai_vision_model = opts[0]?.value ?? f.ai_vision_model;
                        }
                      }
                      return next;
                    });
                  }}
                  model={form.ai_vision_model}
                  modelOptions={getVisionModelOptions(form.ai_vision_provider)}
                  onModelChange={(value) => setForm(f => ({ ...f, ai_vision_model: value }))}
                  freeTextProviders={['openrouter', 'local']}
                  providerHelp="Used to build richer prompt context before generation."
                  modelPlaceholder="e.g. your-local-model"
                />
                <ProviderModelField
                  label="Image"
                  provider={form.ai_image_provider}
                  providerOptions={[
                    { label: 'OpenAI', value: 'openai' },
                    { label: 'Gemini', value: 'gemini' },
                    { label: 'OpenRouter', value: 'openrouter' },
                    { label: 'BytePlus', value: 'byteplus' },
                    { label: 'Local AI', value: 'local' },
                  ]}
                  onProviderChange={(p) => {
                    setForm(f => {
                      const next = { ...f, ai_image_provider: p };
                      if (p !== 'openrouter' && p !== 'byteplus') {
                        const opts = getImageModelOptions(p);
                        if (!opts.some((o) => o.value === f.ai_image_model)) {
                          next.ai_image_model = opts[0]?.value ?? f.ai_image_model;
                        }
                      }
                      return next;
                    });
                  }}
                  model={form.ai_image_model}
                  modelOptions={getImageModelOptions(form.ai_image_provider)}
                  onModelChange={(value) => setForm(f => ({ ...f, ai_image_model: value }))}
                  freeTextProviders={['openrouter', 'byteplus', 'local']}
                  providerHelp="Set this only when you want a separate image-generation provider."
                  modelPlaceholder="e.g. your-local-model"
                />
                <label className={`flex items-center gap-2 rounded-md border border-stone-200 bg-white px-3 py-2 text-sm font-medium text-stone-800 ${form.ai_vision_provider === 'none' || form.ai_image_provider === 'none' ? 'opacity-60' : ''}`}>
                  <input
                    type="checkbox"
                    checked={form.ai_prompt_enrichment}
                    onChange={(e) => setForm(f => ({ ...f, ai_prompt_enrichment: e.target.checked }))}
                    disabled={form.ai_vision_provider === 'none' || form.ai_image_provider === 'none'}
                    className="h-4 w-4 rounded border-stone-300 text-emerald-600 focus:ring-emerald-500"
                  />
                  <div className="grid gap-0.5">
                    <span>AI prompt enrichment</span>
                    <span className="text-xs text-stone-500">
                      {form.ai_vision_provider === 'none' || form.ai_image_provider === 'none'
                        ? 'Enable both providers before turning this on.'
                        : 'Combine vision output with the effect prompt.'}
                    </span>
                  </div>
                </label>
              </div>
            </SectionCard>

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

        {/* List */}
        <div className="grid gap-3">
          {schedules.data?.map(s => (
            <div key={s.id} className={`rounded-xl border p-4 grid gap-3 ${scheduleEnabledClass(s.enabled)}`}>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold text-stone-900">{s.name}</span>
                    <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${s.enabled ? 'bg-emerald-100 text-emerald-800' : 'bg-stone-100 text-stone-500'}`}>
                      {s.enabled ? 'enabled' : 'disabled'}
                    </span>
                    {statusBadge(s.last_tick_status)}
                  </div>
                  <div className="mt-1 text-xs text-stone-500">
                    {describeAutomationSchedule(parseAutomationSchedule(s.schedule_expr))}
                    {' · '}Album: <span className="font-medium">{s.album_name}</span>
                  </div>
                  <div className="mt-2 grid gap-2 sm:grid-cols-3">
                    <div className="rounded-md bg-white/80 px-2.5 py-2 text-xs text-stone-600">
                      <div className="font-semibold text-stone-900">Next run</div>
                      <div className="mt-0.5">{s.next_run_at ? formatDateTime(s.next_run_at) : 'Not scheduled'}</div>
                    </div>
                    <div className="rounded-md bg-white/80 px-2.5 py-2 text-xs text-stone-600">
                      <div className="font-semibold text-stone-900">Last run</div>
                      <div className="mt-0.5">{s.last_run_at ? formatDateTime(s.last_run_at) : 'No runs yet'}</div>
                    </div>
                    <div className="rounded-md bg-white/80 px-2.5 py-2 text-xs text-stone-600">
                      <div className="font-semibold text-stone-900">Last result</div>
                      <div className="mt-0.5">{tickSummary(s.last_tick_status, s.last_tick_reason)}</div>
                    </div>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1.5 text-[11px] text-stone-500">
                    {s.filter_preset_name && <span className="rounded-full bg-white/80 px-2 py-0.5">Filter: {s.filter_preset_name}</span>}
                    {s.effect_preset_name && <span className="rounded-full bg-white/80 px-2 py-0.5">Effect: {s.effect_preset_name}</span>}
                    {s.notification_preset_names && s.notification_preset_names.length > 0 && <span className="rounded-full bg-white/80 px-2 py-0.5">Notifications: {s.notification_preset_names.join(', ')}</span>}
                    {s.ai_vision_provider !== 'none' && <span className="rounded-full bg-white/80 px-2 py-0.5">Vision: {s.ai_vision_provider} ({s.ai_vision_model})</span>}
                    {s.ai_image_provider !== 'none' && <span className="rounded-full bg-white/80 px-2 py-0.5">Image: {s.ai_image_provider} ({s.ai_image_model})</span>}
                    {s.ai_prompt_enrichment && <span className="rounded-full bg-white/80 px-2 py-0.5">Prompt enrichment on</span>}
                  </div>
                </div>
                <div className="flex flex-wrap gap-1.5 sm:shrink-0 justify-start sm:justify-end">
                  <button type="button" onClick={() => toggleMutation.mutate(s)}
                    disabled={toggleMutation.isPending}
                    title={s.enabled ? 'Disable' : 'Enable'}
                    className={`inline-flex items-center gap-1 rounded-md px-2.5 py-1.5 text-xs font-medium disabled:opacity-50 ${s.enabled ? 'text-emerald-700 hover:bg-emerald-50 bg-emerald-50/70' : 'text-stone-500 hover:bg-stone-100 bg-white/70'}`}>
                    {s.enabled ? <ToggleRight size={14} /> : <ToggleLeft size={14} />}
                    {s.enabled ? 'On' : 'Off'}
                  </button>
                  <button type="button" onClick={() => runMutation.mutate(s.id)}
                    disabled={runningId === s.id}
                    title="Run now"
                    className="inline-flex items-center gap-1 rounded-md px-2.5 py-1.5 text-xs font-medium text-emerald-700 hover:bg-emerald-50 bg-white/70 disabled:opacity-50">
                    {runningId === s.id ? <RefreshCw size={12} className="animate-spin" /> : <Play size={12} />}
                    Run now
                  </button>
                  <button type="button" onClick={() => openEdit(s)}
                    className="inline-flex items-center gap-1 rounded-md px-2.5 py-1.5 text-xs font-medium text-stone-500 hover:bg-stone-100 bg-white/70">
                    <Pencil size={12} /> Edit
                  </button>
                  <button type="button" onClick={() => { if (confirm(`Delete "${s.name}"?`)) deleteMutation.mutate(s.id); }}
                    className="inline-flex items-center gap-1 rounded-md px-2.5 py-1.5 text-xs font-medium text-red-500 hover:bg-red-50 bg-white/70">
                    <Trash2 size={12} /> Delete
                  </button>
                </div>
              </div>
            </div>
          ))}
          {schedules.data?.length === 0 && (
            <EmptyState
              icon={<CalendarDays size={18} />}
              title="No schedules yet"
              description="Create a schedule to automate generation with the presets you already prepared."
              action={(
                <button
                  type="button"
                  onClick={openNew}
                  className="inline-flex items-center gap-1.5 rounded-md bg-emerald-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-800"
                >
                  <Plus size={14} /> New schedule
                </button>
              )}
            />
          )}
        </div>
      </div>
    </section>
  );
}
