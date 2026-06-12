import { type ReactNode } from 'react';
import { Plus, Check, X } from 'lucide-react';

export function PresetHeader({
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

export function PresetFormActions({
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

export function PresetActionRow({ children }: { children: ReactNode }) {
  return (
    <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row sm:flex-wrap sm:gap-1.5 sm:shrink-0 sm:items-center">
      {children}
    </div>
  );
}
