import { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  CalendarDays,
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
import { EmptyState } from '../components/FormUI';
import { InlineSpinner, ErrorBanner } from '../components/ErrorUI';
import {
  parseAutomationSchedule,
  serializeAutomationSchedule,
  describeAutomationSchedule,
} from './automation.utils';
import { formatDateTime } from './datetime.utils';
import { type FormState, emptyForm } from './Schedules/types';
import { ScheduleSummaryCard } from './Schedules/ScheduleSummaryCard';
import { ScheduleForm } from './Schedules/ScheduleForm';
import { ConfirmModal } from '../components/ConfirmModal';

function normalizeModelSelection(provider: string, model: string) {
  if (provider === 'none') {
    return '';
  }
  return model;
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
    ),
    ai_image_provider: aiImageProvider,
    ai_image_model: normalizeModelSelection(
      aiImageProvider,
      schedule.ai_image_model ?? 'gpt-image-1',
    ),
    ai_prompt_enrichment: schedule.ai_prompt_enrichment ?? false,
    ai_photo_selection_enabled: schedule.ai_photo_selection_enabled ?? false,
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
    <span
      className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${colors[status] ?? 'bg-stone-100 text-stone-600'}`}
    >
      {status}
    </span>
  );
}

function scheduleEnabledClass(enabled: boolean) {
  return enabled
    ? 'border-emerald-200 bg-emerald-50/40'
    : 'border-stone-200 bg-white';
}

function tickSummary(status: string | null, reason: string | null) {
  if (!status) return 'No runs yet';
  return reason ? `${status} · ${reason}` : status;
}

function countByStatus(
  schedules: Schedule[],
  predicate: (schedule: Schedule) => boolean,
) {
  return schedules.reduce(
    (count, schedule) => count + (predicate(schedule) ? 1 : 0),
    0,
  );
}

function isFailedSchedule(schedule: Schedule) {
  return (
    schedule.last_tick_status === 'error' ||
    schedule.last_tick_status === 'failed'
  );
}

export function SchedulesPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { scheduleId } = useParams<{ scheduleId?: string }>();
  const qc = useQueryClient();

  const schedules = useQuery({
    queryKey: ['schedules'],
    queryFn: getSchedules,
  });
  const filterPresets = useQuery({
    queryKey: ['filter-presets'],
    queryFn: getFilterPresets,
  });
  const effectPresets = useQuery({
    queryKey: ['effect-presets'],
    queryFn: getEffectPresets,
  });
  const notifPresets = useQuery({
    queryKey: ['notification-presets'],
    queryFn: getNotificationPresets,
  });

  const [editing, setEditing] = useState<Schedule | null>(null);
  const [isNew, setIsNew] = useState(false);
  const [form, setForm] = useState<FormState>(emptyForm);
  const [error, setError] = useState<string | null>(null);
  const [runningId, setRunningId] = useState<number | null>(null);
  const [confirmConfig, setConfirmConfig] = useState<{
    isOpen: boolean;
    title: string;
    description: string;
    confirmLabel?: string;
    onConfirm: () => void;
    variant?: 'danger' | 'warning' | 'info';
  } | null>(null);

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
        ai_photo_selection_enabled: form.ai_photo_selection_enabled,
      };
      return editing && !isNew
        ? updateSchedule(editing.id, body)
        : createSchedule(body);
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
        ai_photo_selection_enabled:
          schedule.ai_photo_selection_enabled ?? false,
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
    setError(null);
    navigate(`/schedules/${schedule.id}/edit`);
  }

  function closeForm() {
    setEditing(null);
    setIsNew(false);
    setError(null);
    navigate('/schedules');
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

  const validationIssues: string[] = [];
  if (!form.name.trim()) validationIssues.push('Schedule name is required.');
  if (form.filter_preset_id === '')
    validationIssues.push('Choose a filter preset.');
  if (form.effect_preset_id === '')
    validationIssues.push('Choose an effect preset.');
  if (form.scheduleMode === 'custom' && form.scheduleDays.length === 0) {
    validationIssues.push('Custom schedules need at least one weekday.');
  }
  const canSave = validationIssues.length === 0;

  const anyLoading =
    schedules.isLoading ||
    filterPresets.isLoading ||
    effectPresets.isLoading ||
    notifPresets.isLoading;
  const anyError =
    schedules.error ||
    filterPresets.error ||
    effectPresets.error ||
    notifPresets.error;

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
      const leftTime = left.next_run_at
        ? Date.parse(left.next_run_at)
        : Number.POSITIVE_INFINITY;
      const rightTime = right.next_run_at
        ? Date.parse(right.next_run_at)
        : Number.POSITIVE_INFINITY;
      return leftTime - rightTime;
    });

    return sorted;
  }, [search, scheduleItems]);
  const noSchedules = scheduleItems.length === 0;

  useEffect(() => {
    if (!showForm) return;
    if (typeof window === 'undefined') return;
    if (!window.matchMedia?.('(max-width: 1023px)').matches) return;
    formPanelRef.current?.scrollIntoView?.({
      behavior: 'smooth',
      block: 'start',
    });
  }, [showForm]);

  const activeCount = countByStatus(
    scheduleItems,
    (schedule) => schedule.enabled,
  );
  const disabledCount = countByStatus(
    scheduleItems,
    (schedule) => !schedule.enabled,
  );
  const failedCount = countByStatus(scheduleItems, isFailedSchedule);
  const nextRunItem = [...scheduleItems]
    .filter((schedule) => schedule.next_run_at)
    .sort(
      (left, right) =>
        Date.parse(left.next_run_at!) - Date.parse(right.next_run_at!),
    )[0];

  if (anyLoading) {
    return <InlineSpinner />;
  }

  if (anyError) {
    const errorMsg =
      schedules.error ||
      filterPresets.error ||
      effectPresets.error ||
      notifPresets.error;
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
              <span>
                Manage automated generation schedules with preset
                configurations.
              </span>
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

        {!showForm && (
          <>
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
                description={
                  failedCount > 0
                    ? 'Review the last result on the schedule cards'
                    : 'No errors'
                }
                tone="red"
                icon={<X size={18} />}
              />
              <ScheduleSummaryCard
                title="Next run"
                value={nextRunItem ? nextRunItem.name : 'None'}
                description={
                  nextRunItem?.next_run_at
                    ? formatDateTime(nextRunItem.next_run_at)
                    : 'Not scheduled'
                }
                tone="blue"
                icon={<Clock3 size={18} />}
              />
            </div>

            <div className="grid gap-2 rounded-2xl border border-stone-200/70 bg-white/70 p-2 md:flex md:flex-wrap md:items-center md:gap-2 md:p-2.5">
              <div className="relative min-w-0 w-full md:flex-1">
                <Search
                  size={13}
                  className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-stone-400"
                />
                <input
                  type="text"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search schedules..."
                  className="app-control app-control-muted h-9 pl-8 pr-3 text-xs"
                />
              </div>
            </div>
          </>
        )}

        {error && (
          <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {error}
          </div>
        )}

        <div className="grid gap-2.5 lg:items-start">
          {!showForm && (
            <div
              aria-label="Schedules list"
              className="grid gap-2 lg:grid-cols-2"
            >
              {filteredSchedules.map((schedule) => {
                return (
                  <article
                    key={schedule.id}
                    className={`group w-full rounded-xl border px-2.5 py-2 text-left transition ${scheduleEnabledClass(schedule.enabled)} hover:border-emerald-500/30`}
                  >
                    <div className="flex flex-col gap-2.5 sm:flex-row sm:items-start sm:justify-between">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <span className="text-sm font-semibold text-stone-900">
                            {schedule.name}
                          </span>
                          <span
                            className={`app-chip px-1.5 py-0.5 text-[10px] font-medium ${schedule.enabled ? 'border-emerald-100 bg-emerald-50 text-emerald-800' : 'text-stone-500'}`}
                          >
                            {schedule.enabled ? 'enabled' : 'disabled'}
                          </span>
                          {statusBadge(schedule.last_tick_status)}
                        </div>
                        <div className="mt-0.5 text-xs text-stone-500">
                          {describeAutomationSchedule(
                            parseAutomationSchedule(schedule.schedule_expr),
                          )}
                          {' · '}
                          Album:{' '}
                          <span className="font-medium">
                            {schedule.album_name}
                          </span>
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
                            schedule.enabled
                              ? 'text-emerald-700'
                              : 'text-stone-500'
                          }`}
                        >
                          {schedule.enabled ? (
                            <ToggleRight size={14} />
                          ) : (
                            <ToggleLeft size={14} />
                          )}
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
                            setConfirmConfig({
                              isOpen: true,
                              title: 'Delete Schedule',
                              description: `Are you sure you want to delete "${schedule.name}"?`,
                              confirmLabel: 'Delete',
                              variant: 'danger',
                              onConfirm: () =>
                                deleteMutation.mutate(schedule.id),
                            });
                          }}
                          className="app-button-secondary items-center justify-center px-2 py-1 text-[11px] font-medium text-rose-700"
                          title="Delete schedule"
                        >
                          <Trash2 size={12} />
                        </button>
                      </div>
                    </div>

                    <div className="mt-2 grid gap-1.5 text-xs text-stone-600 sm:grid-cols-3">
                      <CompactMeta
                        label="Next"
                        value={
                          schedule.next_run_at
                            ? formatDateTime(schedule.next_run_at)
                            : 'Not scheduled'
                        }
                      />
                      <CompactMeta
                        label="Last"
                        value={
                          schedule.last_run_at
                            ? formatDateTime(schedule.last_run_at)
                            : 'No runs yet'
                        }
                      />
                      <CompactMeta
                        label="Result"
                        value={tickSummary(
                          schedule.last_tick_status,
                          schedule.last_tick_reason,
                        )}
                      />
                    </div>

                    <div className="mt-1.5 flex flex-wrap gap-1 text-[10px] text-stone-500">
                      {schedule.filter_preset_name && (
                        <span className="app-chip px-2 py-0.5">
                          Filter: {schedule.filter_preset_name}
                        </span>
                      )}
                      {schedule.effect_preset_name && (
                        <span className="app-chip px-2 py-0.5">
                          Effect: {schedule.effect_preset_name}
                        </span>
                      )}
                      {schedule.notification_preset_names &&
                        schedule.notification_preset_names.length > 0 && (
                          <span className="app-chip px-2 py-0.5">
                            Notifications:{' '}
                            {schedule.notification_preset_names.join(', ')}
                          </span>
                        )}
                      {schedule.ai_vision_provider !== 'none' && (
                        <span className="app-chip px-2 py-0.5">
                          Vision: {schedule.ai_vision_provider} (
                          {schedule.ai_vision_model})
                        </span>
                      )}
                      {schedule.ai_image_provider !== 'none' && (
                        <span className="app-chip px-2 py-0.5">
                          Image: {schedule.ai_image_provider} (
                          {schedule.ai_image_model})
                        </span>
                      )}
                      {schedule.ai_prompt_enrichment && (
                        <span className="app-chip px-2 py-0.5">
                          Prompt enrichment on
                        </span>
                      )}
                      {schedule.ai_photo_selection_enabled && (
                        <span className="app-chip px-2 py-0.5">
                          AI photo selection on
                        </span>
                      )}
                    </div>
                  </article>
                );
              })}

              {filteredSchedules.length === 0 && (
                <EmptyState
                  icon={<CalendarDays size={18} />}
                  title={
                    noSchedules
                      ? 'No schedules yet'
                      : 'No schedules match your search'
                  }
                  description={
                    noSchedules
                      ? 'Create a schedule to automate generation with the presets you already prepared.'
                      : 'Try widening the search to see more schedules.'
                  }
                  action={
                    <button
                      type="button"
                      onClick={openNew}
                      className="app-button-primary px-3 py-1.5 text-sm"
                    >
                      <Plus size={14} />
                      New schedule
                    </button>
                  }
                />
              )}
            </div>
          )}

          {showForm && (
            <ScheduleForm
              formPanelRef={formPanelRef}
              isNew={isNew}
              editing={editing}
              form={form}
              setForm={setForm}
              validationIssues={validationIssues}
              filterPresets={filterPresets.data ?? []}
              effectPresets={effectPresets.data ?? []}
              notificationPresets={notifPresets.data ?? []}
              canSave={canSave}
              isSaving={saveMutation.isPending}
              onSave={() => saveMutation.mutate()}
              onCancel={closeForm}
            />
          )}
        </div>
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
    </section>
  );
}

function CompactMeta({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <span className="font-semibold text-stone-900">{label}: </span>
      <span className="text-stone-600">{value}</span>
    </div>
  );
}

export default SchedulesPage;
