import { Bell, Pencil, Trash2 } from 'lucide-react';
import {
  type NotificationPreset,
  formatNotificationProviders,
} from '../../../api/client';
import { PresetActionRow } from '../PresetHeader';

export function NotificationPresetCard({
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
