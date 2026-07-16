import { memo } from 'react';
import {
  ToggleLeft,
  ToggleRight,
  Play,
  RefreshCw,
  Pencil,
  Trash2,
} from 'lucide-react';
import { type Schedule } from '../../api/client';
import {
  parseAutomationSchedule,
  describeAutomationSchedule,
} from '../automation.utils';
import { formatDateTime } from '../datetime.utils';
import { ScheduleDiagnostics } from './ScheduleDiagnostics';

interface ScheduleItemCardProps {
  schedule: Schedule;
  runningId: number | null;
  togglePending: boolean;
  onToggle: (schedule: Schedule) => void;
  onRunNow: (id: number) => void;
  onEdit: (schedule: Schedule) => void;
  onDelete: (schedule: Schedule) => void;
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

function CompactMeta({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <span className="font-semibold text-stone-900">{label}: </span>
      <span className="text-stone-600">{value}</span>
    </div>
  );
}

export const ScheduleItemCard = memo(function ScheduleItemCard({
  schedule,
  runningId,
  togglePending,
  onToggle,
  onRunNow,
  onEdit,
  onDelete,
}: ScheduleItemCardProps) {
  return (
    <article
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
            Album: <span className="font-medium">{schedule.album_name}</span>
          </div>
        </div>
        <div className="flex flex-wrap gap-1 sm:justify-end">
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              onToggle(schedule);
            }}
            disabled={togglePending}
            title={schedule.enabled ? 'Disable' : 'Enable'}
            className={`app-button-secondary items-center gap-1 px-2 py-1 text-[11px] font-medium disabled:opacity-50 ${
              schedule.enabled ? 'text-emerald-700' : 'text-stone-500'
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
              onRunNow(schedule.id);
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
              onEdit(schedule);
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
              onDelete(schedule);
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
        {schedule.people_preset_name && (
          <span className="app-chip px-2 py-0.5">
            People: {schedule.people_preset_name}
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
        {schedule.ai_prompt_enrichment && (
          <span className="app-chip px-2 py-0.5">Prompt enrichment on</span>
        )}
        {schedule.ai_photo_selection_enabled && (
          <span className="app-chip px-2 py-0.5">AI photo selection on</span>
        )}
      </div>

      {schedule.ai_photo_selection_enabled && (
        <details className="mt-2 text-stone-700 bg-stone-50/30 rounded-lg border border-stone-200/60 px-2 py-1.5 text-[11px] transition">
          <summary className="cursor-pointer font-bold uppercase text-[8px] text-stone-400 hover:text-stone-600 select-none tracking-wider">
            Photo selection diagnostics
          </summary>
          <ScheduleDiagnostics scheduleId={schedule.id} />
        </details>
      )}
    </article>
  );
});
