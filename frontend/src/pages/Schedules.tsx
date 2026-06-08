import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  CalendarDays,
  Check,
  Clock3,
  HelpCircle,
  Pencil,
  Play,
  Plus,
  RefreshCw,
  Search,
  ToggleLeft,
  ToggleRight,
  Trash2,
  X,
} from 'lucide-react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import {
  getSchedules,
  createSchedule,
  updateSchedule,
  deleteSchedule,
  triggerScheduleNow,
  getFilterPresets,
  getEffectPresets,
  getNotificationPresets,
  type Schedule,
} from '../api/client';
import { Field, SelectField } from '../components/Field';
import { EmptyState, InlineError, ProviderModelField, SectionCard } from '../components/FormUI';
import { InlineSpinner, ErrorBanner } from '../components/ErrorUI';
import {
  parseAutomationSchedule,
  serializeAutomationSchedule,
  describeAutomationSchedule,
} from './automation.utils';
import { automationScheduleModeOptions, weekdayOptions, type AutomationScheduleMode } from './automation.types';
import { formatDateTime } from './datetime.utils';
import { getVisionModelOptions, getImageModelOptions } from './Settings';

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
  name: '',
  enabled: false,
  scheduleMode: 'daily',
  scheduleDays: [],
  scheduleTime: '08:00',
  filter_preset_id: '',
  effect_preset_id: '',
  notification_preset_ids: [],
  album_name: 'AI Photos',
  ai_vision_provider: 'none',
  ai_vision_model: 'gpt-4o-mini',
  ai_image_provider: 'none',
  ai_image_model: 'gpt-image-1',
  ai_prompt_enrichment: false,
};

function normalizeModelSelection(provider: string, model: string, options: { value: string }[], freeTextProviders: string[]) {
  if (provider === 'none' || freeTextProviders.includes(provider)) {
    return model;
  }
  if (options.some((opt) => opt.value === model)) {
    return model;
  }
  return options[0]?.value ?? model;
}

function scheduleToForm(schedule: Schedule): FormState {
  const parsed = parseAutomationSchedule(schedule.schedule_expr);
  const aiVisionProvider = schedule.ai_vision_provider ?? 'none';
  const aiImageProvider = schedule.ai_image_provider ?? 'none';
  return {
    name: schedule.name,
    enabled: schedule.enabled,
    scheduleMode: parsed.mode,
    scheduleDays: parsed.days,
    scheduleTime: parsed.time,
    filter_preset_id: schedule.filter_preset_id,
    effect_preset_id: schedule.effect_preset_id,
    notification_preset_ids: schedule.notification_preset_ids ?? [],
    album_name: schedule.album_name,
    ai_vision_provider: aiVisionProvider,
    ai_vision_model: normalizeModelSelection(
      aiVisionProvider,
      schedule.ai_vision_model ?? 'gpt-4o-mini',
      getVisionModelOptions(aiVisionProvider),
      ['openrouter', 'local'],
    ),
    ai_image_provider: aiImageProvider,
    ai_image_model: normalizeModelSelection(
      aiImageProvider,
      schedule.ai_image_model ?? 'gpt-image-1',
      getImageModelOptions(aiImageProvider),
      ['openrouter', 'byteplus', 'local'],
    ),
    ai_prompt_enrichment: schedule.ai_prompt_enrichment ?? false,
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

function countByStatus(schedules: Schedule[], predicate: (schedule: Schedule) => boolean) {
  return schedules.reduce((count, schedule) => count + (predicate(schedule) ? 1 : 0), 0);
}

function isFailedSchedule(schedule: Schedule) {
  return schedule.last_tick_status === 'error' || schedule.last_tick_status === 'failed';
}

function ScheduleSummaryCard({
  title,
  value,
  description,
  tone = 'default',
  icon,
}: {
  title: string;
  value: string;
  description: string;
  tone?: 'default' | 'green' | 'red' | 'blue';
  icon: ReactNode;
}) {
  const toneClass =
    tone === 'green'
      ? 'bg-emerald-50 text-emerald-700 border-emerald-100'
      : tone === 'red'
      ? 'bg-rose-50 text-rose-700 border-rose-100'
      : tone === 'blue'
      ? 'bg-blue-50 text-blue-700 border-blue-100'
      : 'bg-stone-50 text-stone-700 border-stone-200';

  return (
    <article className="app-panel grid gap-2 p-2.5 md:p-3">
      <div className="flex items-center gap-2">
        <div className={`flex h-10 w-10 items-center justify-center rounded-2xl border ${toneClass}`}>
          {icon}
        </div>
        <div>
          <div className="flex items-center gap-1 text-xs font-medium text-stone-500">
            <span>{title}</span>
            {description ? (
              <span
                title={description}
                aria-label={description}
                className="inline-flex items-center text-stone-400 transition hover:text-stone-600"
              >
                <HelpCircle size={10} />
              </span>
            ) : null}
          </div>
          <div className="text-xl font-semibold text-stone-950">{value}</div>
        </div>
      </div>
    </article>
  );
}

export function SchedulesPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { scheduleId } = useParams<{ scheduleId?: string }>();
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
  const [selectedScheduleId, setSelectedScheduleId] = useState<number | null>(null);
  const [search, setSearch] = useState('');
  const formPanelRef = useRef<HTMLElement | null>(null);

  const saveMutation = useMutation({
    mutationFn: () => {
      const schedule_expr = serializeAutomationSchedule({
        mode: form.scheduleMode,
        days: form.scheduleDays,
        time: form.scheduleTime,
      });
      const body = {
        name: form.name,
        enabled: form.enabled,
        schedule_expr,
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
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['schedules'] });
      navigate('/schedules');
    },
    onError: (e: Error) => setError(e.message),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteSchedule(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['schedules'] }),
    onError: (e: Error) => setError(e.message),
  });

  const toggleMutation = useMutation({
    mutationFn: (schedule: Schedule) =>
      updateSchedule(schedule.id, {
        name: schedule.name,
        enabled: !schedule.enabled,
        schedule_expr: schedule.schedule_expr,
        filter_preset_id: schedule.filter_preset_id,
        effect_preset_id: schedule.effect_preset_id,
        notification_preset_ids: schedule.notification_preset_ids ?? [],
        album_name: schedule.album_name,
        ai_vision_provider: schedule.ai_vision_provider,
        ai_vision_model: schedule.ai_vision_model,
        ai_image_provider: schedule.ai_image_provider,
        ai_image_model: schedule.ai_image_model,
        ai_prompt_enrichment: schedule.ai_prompt_enrichment ?? false,
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
    onSettled: () => {
      setRunningId(null);
      qc.invalidateQueries({ queryKey: ['schedules'] });
    },
    onError: (e: Error) => setError(e.message),
  });

  function openNew() {
    setForm(emptyForm);
    setEditing(null);
    setIsNew(true);
    setError(null);
    navigate('/schedules/new');
  }

  function openEdit(schedule: Schedule) {
    setSelectedScheduleId(schedule.id);
    setError(null);
    navigate(`/schedules/${schedule.id}/edit`);
  }

  function closeForm() {
    setEditing(null);
    setIsNew(false);
    setError(null);
    navigate('/schedules');
  }

  function toggleDay(day: number) {
    setForm((current) => ({
      ...current,
      scheduleMode: 'custom',
      scheduleDays: current.scheduleDays.includes(day)
        ? current.scheduleDays.filter((existing) => existing !== day)
        : [...current.scheduleDays, day].sort((a, b) => a - b),
    }));
  }

  const routeIsNew = location.pathname.endsWith('/new');
  const routeEditId = scheduleId ? Number(scheduleId) : null;
  const showForm = isNew || editing !== null;

  useEffect(() => {
    if (routeIsNew) {
      if (!isNew) {
        setForm(emptyForm);
        setEditing(null);
        setIsNew(true);
        setError(null);
      }
      return;
    }

    if (routeEditId && !Number.isNaN(routeEditId)) {
      const found = schedules.data?.find((item) => item.id === routeEditId);
      if (found) {
        if (!editing || editing.id !== found.id || isNew) {
          setForm(scheduleToForm(found));
          setEditing(found);
          setIsNew(false);
          setError(null);
        }
        setSelectedScheduleId(found.id);
      } else if (schedules.data) {
        setEditing(null);
        setIsNew(false);
        setError(`Schedule ${routeEditId} was not found.`);
      }
      return;
    }

    if (!routeIsNew && editing) {
      closeForm();
    }
  }, [editing, isNew, routeEditId, routeIsNew, schedules.data]);

  useEffect(() => {
    if (routeIsNew || routeEditId) return;
    if (selectedScheduleId !== null) return;
    if (schedules.data?.length) {
      setSelectedScheduleId(schedules.data[0].id);
    }
  }, [routeEditId, routeIsNew, schedules.data, selectedScheduleId]);

  const validationIssues: string[] = [];
  if (!form.name.trim()) validationIssues.push('Schedule name is required.');
  if (form.filter_preset_id === '') validationIssues.push('Choose a filter preset.');
  if (form.effect_preset_id === '') validationIssues.push('Choose an effect preset.');
  if (form.scheduleMode === 'custom' && form.scheduleDays.length === 0) {
    validationIssues.push('Custom schedules need at least one weekday.');
  }
  const canSave = validationIssues.length === 0;

  const anyLoading =
    schedules.isLoading || filterPresets.isLoading || effectPresets.isLoading || notifPresets.isLoading;
  const anyError =
    schedules.error || filterPresets.error || effectPresets.error || notifPresets.error;

  const scheduleItems = schedules.data ?? [];
  const filteredSchedules = useMemo(() => {
    const query = search.trim().toLowerCase();
    const filtered = scheduleItems.filter((schedule) => {
      const matchesSearch =
        !query ||
        [
          schedule.name,
          schedule.album_name,
          schedule.filter_preset_name ?? '',
          schedule.effect_preset_name ?? '',
          schedule.notification_preset_names?.join(' ') ?? '',
        ]
          .join(' ')
          .toLowerCase()
          .includes(query);
      return matchesSearch;
    });

    const sorted = [...filtered];
    sorted.sort((left, right) => {
      const leftTime = left.next_run_at ? Date.parse(left.next_run_at) : Number.POSITIVE_INFINITY;
      const rightTime = right.next_run_at ? Date.parse(right.next_run_at) : Number.POSITIVE_INFINITY;
      return leftTime - rightTime;
    });

    return sorted;
  }, [search, scheduleItems]);
  const noSchedules = scheduleItems.length === 0;

  const selectedSchedule = useMemo(() => {
    if (!scheduleItems.length) return null;
    if (selectedScheduleId !== null) {
      const found = scheduleItems.find((schedule) => schedule.id === selectedScheduleId);
      if (found) return found;
    }
    return filteredSchedules[0] ?? scheduleItems[0] ?? null;
  }, [filteredSchedules, scheduleItems, selectedScheduleId]);

  useEffect(() => {
    if (!selectedSchedule && scheduleItems.length > 0) {
      setSelectedScheduleId(scheduleItems[0].id);
    }
  }, [scheduleItems, selectedSchedule]);

  useEffect(() => {
    if (!showForm) return;
    if (typeof window === 'undefined') return;
    if (!window.matchMedia?.('(max-width: 1023px)').matches) return;
    formPanelRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
  }, [showForm]);

  const activeCount = countByStatus(scheduleItems, (schedule) => schedule.enabled);
  const disabledCount = countByStatus(scheduleItems, (schedule) => !schedule.enabled);
  const failedCount = countByStatus(scheduleItems, isFailedSchedule);
  const nextRunItem = [...scheduleItems]
    .filter((schedule) => schedule.next_run_at)
    .sort((left, right) => Date.parse(left.next_run_at!) - Date.parse(right.next_run_at!))[0];

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
      <div className="app-panel grid gap-4 p-3 md:p-4">
      <div className="flex flex-col gap-2.5 lg:flex-row lg:items-start lg:justify-between">
          <div className="grid gap-1">
            <h2 className="text-2xl font-semibold text-stone-950">Schedules</h2>
            <div className="inline-flex items-center gap-1 text-sm leading-6 text-stone-500">
              <span>Manage automated generation schedules with preset configurations.</span>
              <span
                title="Manage automated generation schedules with preset configurations."
                aria-label="Manage automated generation schedules with preset configurations."
                className="inline-flex items-center text-stone-400 transition hover:text-stone-600"
              >
                <HelpCircle size={11} />
              </span>
            </div>
          </div>
          <button
            type="button"
            onClick={openNew}
            className="app-button-primary w-full px-4 py-2 text-sm lg:w-auto"
          >
            <Plus size={14} />
            New schedule
          </button>
        </div>

        <div className="grid grid-cols-2 gap-2.5 xl:grid-cols-4">
          <ScheduleSummaryCard
            title="Active schedules"
            value={String(activeCount)}
            description={`of ${scheduleItems.length} total`}
            tone="green"
            icon={<CalendarDays size={18} />}
          />
          <ScheduleSummaryCard
            title="Disabled"
            value={String(disabledCount)}
            description={`of ${scheduleItems.length} total`}
            tone="default"
            icon={<ToggleLeft size={18} />}
          />
          <ScheduleSummaryCard
            title="Failed last run"
            value={String(failedCount)}
            description={failedCount > 0 ? 'Review the last result on the schedule cards' : 'No errors'}
            tone="red"
            icon={<X size={18} />}
          />
          <ScheduleSummaryCard
            title="Next run"
            value={nextRunItem ? nextRunItem.name : 'None'}
            description={nextRunItem?.next_run_at ? formatDateTime(nextRunItem.next_run_at) : 'Not scheduled'}
            tone="blue"
            icon={<Clock3 size={18} />}
          />
        </div>

        <div className="grid gap-2 rounded-2xl border border-stone-200/70 bg-white/70 p-2 md:flex md:flex-wrap md:items-center md:gap-2 md:p-2.5">
          <div className="relative min-w-0 w-full md:flex-1">
            <Search size={13} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-stone-400" />
            <input
              type="text"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search schedules..."
              className="app-control app-control-muted h-9 pl-8 pr-3 text-xs"
            />
          </div>
        </div>

        {error && <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>}

        <div
          className={`grid gap-2.5 lg:items-start ${
            showForm
              ? 'lg:grid-cols-[minmax(18rem,0.8fr)_minmax(28rem,1.2fr)]'
              : 'lg:grid-cols-[minmax(0,1.35fr)_minmax(20rem,0.85fr)]'
          }`}
        >
          <div className="grid gap-2">
            {filteredSchedules.map((schedule) => {
              const isSelected = selectedSchedule?.id === schedule.id;
              return (
                <article
                  key={schedule.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => setSelectedScheduleId(schedule.id)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      setSelectedScheduleId(schedule.id);
                    }
                  }}
                  className={`group w-full cursor-pointer rounded-2xl border p-2.5 text-left shadow-xs transition ${scheduleEnabledClass(schedule.enabled)} ${
                    isSelected ? 'ring-2 ring-emerald-500/30' : 'hover:border-emerald-500/30'
                  } md:p-3`}
                >
                  <div className="flex flex-col gap-2.5 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="text-sm font-semibold text-stone-900">{schedule.name}</span>
                        <span className={`app-chip px-1.5 py-0.5 text-[10px] font-medium ${schedule.enabled ? 'border-emerald-100 bg-emerald-50 text-emerald-800' : 'text-stone-500'}`}>
                          {schedule.enabled ? 'enabled' : 'disabled'}
                        </span>
                        {statusBadge(schedule.last_tick_status)}
                      </div>
                      <div className="mt-0.5 text-xs text-stone-500">
                        {describeAutomationSchedule(parseAutomationSchedule(schedule.schedule_expr))}
                        {' · '}
                        Album: <span className="font-medium">{schedule.album_name}</span>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-1 sm:justify-end">
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          toggleMutation.mutate(schedule);
                        }}
                        disabled={toggleMutation.isPending}
                        title={schedule.enabled ? 'Disable' : 'Enable'}
                        className={`app-button-secondary items-center gap-1 px-2 py-1 text-[11px] font-medium disabled:opacity-50 ${
                          schedule.enabled ? 'text-emerald-700' : 'text-stone-500'
                        }`}
                      >
                        {schedule.enabled ? <ToggleRight size={14} /> : <ToggleLeft size={14} />}
                        {schedule.enabled ? 'On' : 'Off'}
                      </button>
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          runMutation.mutate(schedule.id);
                        }}
                        disabled={runningId === schedule.id}
                        title="Run now"
                        className="app-button-secondary items-center gap-1 px-2 py-1 text-[11px] font-medium text-emerald-700 disabled:opacity-50"
                      >
                        {runningId === schedule.id ? (
                          <RefreshCw size={12} className="animate-spin" />
                        ) : (
                          <Play size={12} />
                        )}
                        Run now
                      </button>
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          openEdit(schedule);
                        }}
                        className="app-button-secondary items-center gap-1 px-2 py-1 text-[11px] font-medium text-stone-500"
                      >
                        <Pencil size={12} />
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          if (confirm(`Delete "${schedule.name}"?`)) deleteMutation.mutate(schedule.id);
                        }}
                        className="app-button-secondary items-center justify-center px-2 py-1 text-[11px] font-medium text-rose-700"
                        title="Delete schedule"
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  </div>

                  <div className="mt-2 grid gap-2 sm:grid-cols-3">
                    <InfoTile
                      label="Next run"
                      value={schedule.next_run_at ? formatDateTime(schedule.next_run_at) : 'Not scheduled'}
                    />
                    <InfoTile
                      label="Last run"
                      value={schedule.last_run_at ? formatDateTime(schedule.last_run_at) : 'No runs yet'}
                    />
                    <InfoTile
                      label="Last result"
                      value={tickSummary(schedule.last_tick_status, schedule.last_tick_reason)}
                    />
                  </div>

                  <div className="mt-1.5 flex flex-wrap gap-1 md:gap-1.5 text-[10px] md:text-[11px] text-stone-500">
                    {schedule.filter_preset_name && <span className="app-chip px-2 py-0.5">Filter: {schedule.filter_preset_name}</span>}
                    {schedule.effect_preset_name && <span className="app-chip px-2 py-0.5">Effect: {schedule.effect_preset_name}</span>}
                    {schedule.notification_preset_names && schedule.notification_preset_names.length > 0 && (
                      <span className="app-chip px-2 py-0.5">
                        Notifications: {schedule.notification_preset_names.join(', ')}
                      </span>
                    )}
                    {schedule.ai_vision_provider !== 'none' && (
                      <span className="app-chip px-2 py-0.5">
                        Vision: {schedule.ai_vision_provider} ({schedule.ai_vision_model})
                      </span>
                    )}
                    {schedule.ai_image_provider !== 'none' && (
                      <span className="app-chip px-2 py-0.5">
                        Image: {schedule.ai_image_provider} ({schedule.ai_image_model})
                      </span>
                    )}
                    {schedule.ai_prompt_enrichment && <span className="app-chip px-2 py-0.5">Prompt enrichment on</span>}
                  </div>
                </article>
              );
            })}

            {filteredSchedules.length === 0 && (
              <EmptyState
                icon={<CalendarDays size={18} />}
                title={noSchedules ? 'No schedules yet' : 'No schedules match your search'}
                description={
                  noSchedules
                    ? 'Create a schedule to automate generation with the presets you already prepared.'
                    : 'Try widening the search to see more schedules.'
                }
                action={
                  <button type="button" onClick={openNew} className="app-button-primary px-3 py-1.5 text-sm">
                    <Plus size={14} />
                    New schedule
                  </button>
                }
              />
            )}
          </div>

          {showForm ? (
            <aside ref={formPanelRef} aria-label="Schedule form panel" className="app-panel grid gap-2 p-2 md:gap-2.5 md:p-2.5">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div className="flex items-center gap-1.5">
                  <div className="text-sm font-semibold text-stone-900">
                    {isNew ? 'New schedule' : `Editing: ${editing?.name}`}
                  </div>
                  <span
                    title="Required fields are marked with an asterisk."
                    aria-label="Required fields are marked with an asterisk."
                    className="inline-flex items-center text-stone-400 transition hover:text-stone-600"
                  >
                    <HelpCircle size={14} />
                  </span>
                </div>
                <div className="rounded-xl border border-stone-200 bg-stone-50 px-2 py-1 text-[10px] leading-4 text-stone-500">
                  {describeAutomationSchedule({
                    mode: form.scheduleMode,
                    days: form.scheduleDays,
                    time: form.scheduleTime,
                  })}
                </div>
              </div>

              {validationIssues.length > 0 && (
                <InlineError
                  title="Fix the highlighted fields"
                  message={validationIssues.join(' ')}
                />
              )}

              <div className="grid gap-2 xl:grid-cols-2 xl:items-start">
                <div className="grid gap-2">
                  <SectionCard title="Basics" description="Choose the schedule name and target album." className="gap-1.5 p-2 md:p-2.5">
                    <div className="grid gap-1.5 sm:grid-cols-2">
                      <Field
                        label="Name"
                        required
                        value={form.name}
                        maxLength={255}
                        onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                        className="text-xs"
                        hint="Shown in the schedules list."
                      />
                      <Field
                        label="Album name"
                        required
                        value={form.album_name}
                        maxLength={255}
                        onChange={(event) => setForm((current) => ({ ...current, album_name: event.target.value }))}
                        className="text-xs"
                        hint="The album created or updated on run."
                      />
                    </div>
                  </SectionCard>

                  <SectionCard title="Schedule" description="Pick when the job runs and how much control you need." className="gap-1.5 p-2 md:p-2.5">
                    <div className="grid gap-1.5 md:gap-2">
                      <div className="grid gap-1 sm:flex sm:flex-wrap">
                        {automationScheduleModeOptions.map((option) => (
                          <button
                            key={option.value}
                            type="button"
                            onClick={() => {
                              const days =
                                option.value === 'weekdays'
                                  ? [0, 1, 2, 3, 4]
                                  : option.value === 'weekends'
                                  ? [5, 6]
                                  : [];
                              setForm((current) => ({
                                ...current,
                                scheduleMode: option.value,
                                scheduleDays: days,
                              }));
                            }}
                            className={`rounded-full border px-3 py-2 text-xs font-medium transition-colors sm:py-1 ${
                              form.scheduleMode === option.value
                                ? 'border-emerald-500 bg-emerald-50 text-emerald-800'
                                : 'border-stone-300 bg-white text-stone-700 hover:border-emerald-300'
                            }`}
                          >
                            {option.label}
                          </button>
                        ))}
                      </div>
                      {form.scheduleMode === 'custom' && (
                        <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap">
                          {weekdayOptions.map((day) => (
                            <button
                              key={day.value}
                              type="button"
                              onClick={() => toggleDay(day.value)}
                              className={`rounded-full border px-2.5 py-2 text-xs font-medium transition-colors sm:py-1 ${
                                form.scheduleDays.includes(day.value)
                                  ? 'border-emerald-500 bg-emerald-50 text-emerald-800'
                                  : 'border-stone-300 bg-white text-stone-600 hover:border-emerald-300'
                              }`}
                            >
                              {day.label}
                            </button>
                          ))}
                        </div>
                      )}
                      <div className="grid gap-1.5 sm:grid-cols-[120px_1fr] sm:items-end">
                        <label className="grid gap-0.5 text-sm font-medium text-stone-800">
                          <span className="flex items-center gap-1">
                            <span>Time</span>
                            <span className="text-rose-500">*</span>
                          </span>
                          <input
                            type="time"
                            value={form.scheduleTime}
                            onChange={(event) => setForm((current) => ({ ...current, scheduleTime: event.target.value }))}
                            className="app-control h-9 w-full min-w-0"
                          />
                        </label>
                        <div className="rounded-xl border border-stone-200 bg-stone-50 px-2 py-1 text-[10px] leading-4 text-stone-600">
                          {describeAutomationSchedule({
                            mode: form.scheduleMode,
                            days: form.scheduleDays,
                            time: form.scheduleTime,
                          })}
                        </div>
                      </div>
                    </div>
                  </SectionCard>
                </div>

                <div className="grid gap-2">
                  <SectionCard title="Presets" description="Link the filter, effect, and notification presets used by the run." className="gap-1.5 p-2 md:p-2.5">
                    <div className="grid gap-1.5 md:gap-2 lg:grid-cols-3">
                      <SelectField
                        label="Filter preset"
                        value={String(form.filter_preset_id)}
                        required
                        className="text-xs"
                        onChange={(event) =>
                          setForm((current) => ({
                            ...current,
                            filter_preset_id: event.target.value ? Number(event.target.value) : '',
                          }))
                        }
                      >
                        <option value="">Select a filter preset</option>
                        {filterPresets.data?.map((preset) => (
                          <option key={preset.id} value={preset.id}>
                            {preset.name}
                          </option>
                        ))}
                      </SelectField>
                      <SelectField
                        label="Effect preset"
                        value={String(form.effect_preset_id)}
                        required
                        className="text-xs"
                        onChange={(event) =>
                          setForm((current) => ({
                            ...current,
                            effect_preset_id: event.target.value ? Number(event.target.value) : '',
                          }))
                        }
                      >
                        <option value="">Select an effect preset</option>
                        {effectPresets.data?.map((preset) => (
                          <option key={preset.id} value={preset.id}>
                            {preset.name}
                          </option>
                        ))}
                      </SelectField>
                      <div className="grid gap-0.5">
                        <div className="text-sm font-medium text-stone-800">
                          Notification presets <span className="text-rose-500">*</span>
                        </div>
                        <div className="rounded-2xl border border-stone-200 bg-white p-2.5 shadow-xs">
                          <div className="flex flex-wrap gap-1">
                            {notifPresets.data
                              ?.filter((preset) => form.notification_preset_ids.includes(preset.id))
                              .map((preset) => (
                                <span
                                  key={preset.id}
                                  className="app-chip inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-medium text-stone-800"
                                >
                                  {preset.name}
                                  <button
                                    type="button"
                                    onClick={() =>
                                      setForm((current) => ({
                                        ...current,
                                        notification_preset_ids: current.notification_preset_ids.filter(
                                          (id) => id !== preset.id,
                                        ),
                                      }))
                                    }
                                    className="rounded-xs p-0.5 text-stone-400 hover:text-stone-700"
                                  >
                                    <X size={10} />
                                  </button>
                                </span>
                              ))}
                            {form.notification_preset_ids.length === 0 && (
                              <span
                                title="No notification presets selected."
                                aria-label="No notification presets selected."
                                className="inline-flex items-center text-stone-400 transition hover:text-stone-600"
                              >
                                <HelpCircle size={12} />
                              </span>
                            )}
                          </div>
                          <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                            <select
                              value=""
                              onChange={(event) => {
                                const id = Number(event.target.value);
                                if (id && !form.notification_preset_ids.includes(id)) {
                                  setForm((current) => ({
                                    ...current,
                                    notification_preset_ids: [...current.notification_preset_ids, id],
                                  }));
                                }
                              }}
                              className="app-control h-9 px-2 text-xs"
                            >
                              <option value="">Add notification preset</option>
                              {notifPresets.data
                                ?.filter((preset) => !form.notification_preset_ids.includes(preset.id))
                                .map((preset) => (
                                  <option key={preset.id} value={preset.id}>
                                    {preset.name}
                                  </option>
                                ))}
                            </select>
                            <span
                              title="You can attach more than one channel preset."
                              aria-label="You can attach more than one channel preset."
                              className="inline-flex items-center text-stone-400 transition hover:text-stone-600"
                            >
                              <HelpCircle size={12} />
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </SectionCard>

                  <SectionCard title="AI settings" description="Optional. Enable one or both providers to enrich prompts." className="gap-1.5 p-2 md:p-2.5">
                    <div className="grid gap-2">
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
                        onProviderChange={(provider) => {
                          setForm((current) => {
                            const next = { ...current, ai_vision_provider: provider };
                            if (provider !== 'openrouter') {
                              const opts = getVisionModelOptions(provider);
                              if (!opts.some((opt) => opt.value === current.ai_vision_model)) {
                                next.ai_vision_model = opts[0]?.value ?? current.ai_vision_model;
                              }
                            }
                            return next;
                          });
                        }}
                        model={form.ai_vision_model}
                        modelOptions={getVisionModelOptions(form.ai_vision_provider)}
                        onModelChange={(value) => setForm((current) => ({ ...current, ai_vision_model: value }))}
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
                        onProviderChange={(provider) => {
                          setForm((current) => {
                            const next = { ...current, ai_image_provider: provider };
                            if (provider !== 'openrouter' && provider !== 'byteplus') {
                              const opts = getImageModelOptions(provider);
                              if (!opts.some((opt) => opt.value === current.ai_image_model)) {
                                next.ai_image_model = opts[0]?.value ?? current.ai_image_model;
                              }
                            }
                            return next;
                          });
                        }}
                        model={form.ai_image_model}
                        modelOptions={getImageModelOptions(form.ai_image_provider)}
                        onModelChange={(value) => setForm((current) => ({ ...current, ai_image_model: value }))}
                        freeTextProviders={['openrouter', 'byteplus', 'local']}
                        providerHelp="Set this only when you want a separate image-generation provider."
                        modelPlaceholder="e.g. your-local-model"
                      />
                      <label
                        className={`flex items-center gap-2 rounded-2xl border border-stone-200 bg-white px-2 py-1.5 text-sm font-medium text-stone-800 shadow-xs ${
                          form.ai_vision_provider === 'none' || form.ai_image_provider === 'none' ? 'opacity-60' : ''
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={form.ai_prompt_enrichment}
                          onChange={(event) =>
                            setForm((current) => ({ ...current, ai_prompt_enrichment: event.target.checked }))
                          }
                          disabled={form.ai_vision_provider === 'none' || form.ai_image_provider === 'none'}
                          className="h-4 w-4 rounded-sm border-stone-300 text-emerald-600 focus:ring-emerald-500"
                        />
                        <div className="grid gap-0.5">
                          <span>AI prompt enrichment</span>
                          <span
                            title={
                              form.ai_vision_provider === 'none' || form.ai_image_provider === 'none'
                                ? 'Enable both providers before turning this on.'
                                : 'Combine vision output with the effect prompt.'
                            }
                            aria-label={
                              form.ai_vision_provider === 'none' || form.ai_image_provider === 'none'
                                ? 'Enable both providers before turning this on.'
                                : 'Combine vision output with the effect prompt.'
                            }
                            className="inline-flex items-center text-stone-400 transition hover:text-stone-600"
                          >
                            <HelpCircle size={12} />
                          </span>
                        </div>
                      </label>
                    </div>
                  </SectionCard>
                </div>
              </div>

              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => saveMutation.mutate()}
                  disabled={!canSave || saveMutation.isPending}
                  className="app-button-primary flex-1 justify-center px-3 py-2 text-sm font-semibold disabled:opacity-50 sm:flex-none sm:w-auto"
                >
                  <Check size={14} />
                  Save
                </button>
                <button
                  type="button"
                  onClick={closeForm}
                  className="app-button-secondary flex-1 justify-center px-3 py-2 text-sm font-semibold sm:flex-none sm:w-auto"
                >
                  <X size={14} />
                  Cancel
                </button>
              </div>
            </aside>
          ) : (
            <ScheduleDetailPanel
              schedule={selectedSchedule}
              onCreate={openNew}
              onEdit={() => {
                if (selectedSchedule) openEdit(selectedSchedule);
              }}
              onRunNow={() => {
                if (selectedSchedule) runMutation.mutate(selectedSchedule.id);
              }}
              onToggle={() => {
                if (selectedSchedule) toggleMutation.mutate(selectedSchedule);
              }}
              onDelete={() => {
                if (selectedSchedule && confirm(`Delete "${selectedSchedule.name}"?`)) {
                  deleteMutation.mutate(selectedSchedule.id);
                }
              }}
              running={selectedSchedule ? runningId === selectedSchedule.id : false}
              togglePending={toggleMutation.isPending}
            />
          )}
        </div>
      </div>
    </section>
  );
}

function InfoTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-stone-200 bg-white/80 px-2.5 py-2 text-xs text-stone-600">
      <div className="font-semibold text-stone-900">{label}</div>
      <div className="mt-0.5">{value}</div>
    </div>
  );
}

function ScheduleDetailPanel({
  schedule,
  onCreate,
  onEdit,
  onRunNow,
  onToggle,
  onDelete,
  running,
  togglePending,
}: {
  schedule: Schedule | null;
  onCreate: () => void;
  onEdit: () => void;
  onRunNow: () => void;
  onToggle: () => void;
  onDelete: () => void;
  running: boolean;
  togglePending: boolean;
}) {
  if (!schedule) {
    return (
      <div className="app-panel-soft flex min-h-96 flex-col items-center justify-center gap-3 border-dashed border-stone-200 p-6 text-center text-stone-500">
        <CalendarDays size={34} className="text-stone-300" />
        <div className="grid gap-1">
          <h3 className="text-base font-semibold text-stone-900">Select a schedule</h3>
          <p className="max-w-xs text-sm leading-6 text-stone-500">
            Choose any item from the list to inspect its configuration, run history, and actions.
          </p>
        </div>
        <button type="button" onClick={onCreate} className="app-button-primary px-4 py-2 text-sm">
          <Plus size={14} />
          New schedule
        </button>
      </div>
    );
  }

  return (
    <aside className="app-panel grid gap-4 p-3 md:p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="grid gap-1">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-xl font-semibold text-stone-950">{schedule.name}</h3>
            <span className={`app-chip px-2.5 py-0.5 text-[11px] font-medium ${schedule.enabled ? 'border-emerald-100 bg-emerald-50 text-emerald-800' : 'text-stone-500'}`}>
              {schedule.enabled ? 'Active' : 'Disabled'}
            </span>
          </div>
          <p className="text-sm leading-6 text-stone-500">
            {describeAutomationSchedule(parseAutomationSchedule(schedule.schedule_expr))}
            {' · '}
            Album: {schedule.album_name}
          </p>
        </div>
        <button
          type="button"
          onClick={onToggle}
          disabled={togglePending}
          className="inline-flex h-10 items-center gap-2 rounded-xl border border-stone-200 bg-white px-3 text-sm font-semibold text-stone-700 shadow-xs transition hover:border-stone-300 hover:bg-stone-50 disabled:opacity-50"
        >
          {schedule.enabled ? <ToggleRight size={16} /> : <ToggleLeft size={16} />}
          {schedule.enabled ? 'On' : 'Off'}
        </button>
      </div>

      <div className="grid gap-3">
        <div className="grid gap-2 rounded-2xl border border-stone-200/70 bg-white/80 p-3">
          <DetailRow label="Schedule" value={describeAutomationSchedule(parseAutomationSchedule(schedule.schedule_expr))} />
          <DetailRow label="Album" value={schedule.album_name} />
          <DetailRow label="Filter" value={schedule.filter_preset_name ?? 'Not selected'} />
          <DetailRow label="Effect" value={schedule.effect_preset_name ?? 'Not selected'} />
          <DetailRow
            label="Vision model"
            value={schedule.ai_vision_provider !== 'none' ? `${schedule.ai_vision_provider} (${schedule.ai_vision_model})` : 'Disabled'}
          />
          <DetailRow
            label="Image model"
            value={schedule.ai_image_provider !== 'none' ? `${schedule.ai_image_provider} (${schedule.ai_image_model})` : 'Disabled'}
          />
          <DetailRow
            label="Prompt enrichment"
            value={schedule.ai_prompt_enrichment ? 'On' : 'Off'}
          />
          <DetailRow
            label="Notifications"
            value={schedule.notification_preset_names?.length ? schedule.notification_preset_names.join(', ') : 'None'}
          />
          <DetailRow
            label="Created"
            value={schedule.created_at ? formatDateTime(schedule.created_at) : 'Unknown'}
          />
          {schedule.last_run_at && (
            <DetailRow label="Last run" value={formatDateTime(schedule.last_run_at)} />
          )}
          {schedule.next_run_at && (
            <DetailRow label="Next run" value={formatDateTime(schedule.next_run_at)} />
          )}
        </div>

        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={onRunNow} disabled={running} className="app-button-primary px-4 py-2 text-sm disabled:opacity-50">
            {running ? <RefreshCw size={14} className="animate-spin" /> : <Play size={14} />}
            Run now
          </button>
          <button type="button" onClick={onEdit} className="app-button-secondary px-4 py-2 text-sm">
            <Pencil size={14} />
            Edit schedule
          </button>
          <button type="button" onClick={onDelete} className="app-button-secondary px-4 py-2 text-sm text-rose-700">
            <Trash2 size={14} />
            Delete
          </button>
        </div>

        <div className="rounded-2xl border border-blue-100 bg-blue-50/60 p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-blue-800">
            <HelpCircle size={15} />
            Tip
          </div>
          <p className="mt-2 text-sm leading-6 text-blue-900">
            Run a schedule now to verify the configuration before waiting for the next automatic run.
          </p>
        </div>

        <div className="grid gap-2 sm:grid-cols-3">
          <InfoTile label="Next run" value={schedule.next_run_at ? formatDateTime(schedule.next_run_at) : 'Not scheduled'} />
          <InfoTile label="Last run" value={schedule.last_run_at ? formatDateTime(schedule.last_run_at) : 'No runs yet'} />
          <InfoTile label="Last result" value={tickSummary(schedule.last_tick_status, schedule.last_tick_reason)} />
        </div>
      </div>
    </aside>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[10rem_minmax(0,1fr)] gap-3 border-b border-stone-100 py-2 text-sm last:border-b-0">
      <span className="text-stone-500">{label}</span>
      <span className="min-w-0 font-medium text-stone-900">{value}</span>
    </div>
  );
}

export default SchedulesPage;
