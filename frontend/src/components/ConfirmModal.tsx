import { AlertTriangle, Info, X } from 'lucide-react';
import { useFocusTrap } from '../hooks/useFocusTrap';

interface ConfirmModalProps {
  isOpen: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onClose: () => void;
  variant?: 'danger' | 'warning' | 'info';
  isPending?: boolean;
}

export function ConfirmModal({
  isOpen,
  title,
  description,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  onConfirm,
  onClose,
  variant = 'warning',
  isPending = false,
}: ConfirmModalProps) {
  const trapRef = useFocusTrap(isOpen);

  if (!isOpen) return null;

  const getIconColor = () => {
    switch (variant) {
      case 'danger':
        return 'text-red-600 bg-red-100';
      case 'info':
        return 'text-blue-600 bg-blue-100';
      case 'warning':
      default:
        return 'text-amber-600 bg-amber-100';
    }
  };

  const getConfirmButtonColor = () => {
    switch (variant) {
      case 'danger':
        return 'bg-red-600 hover:bg-red-700';
      case 'info':
        return 'bg-blue-600 hover:bg-blue-700';
      case 'warning':
      default:
        return 'bg-amber-600 hover:bg-amber-700';
    }
  };

  return (
    <div
      ref={trapRef}
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
    >
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-modal-title"
        className="relative w-full max-w-sm rounded-2xl border border-stone-200 bg-white p-5 shadow-xl"
      >
        <button
          type="button"
          onClick={onClose}
          disabled={isPending}
          aria-label="Close"
          className="absolute right-3 top-3 rounded-lg p-1 text-stone-400 hover:bg-stone-100 hover:text-stone-600 transition"
        >
          <X size={16} />
        </button>

        <div className="flex items-start gap-3 mb-4">
          <div className={`shrink-0 rounded-xl p-2.5 ${getIconColor()}`}>
            {variant === 'info' ? (
              <Info size={18} />
            ) : (
              <AlertTriangle size={18} />
            )}
          </div>
          <div>
            <h3 id="confirm-modal-title" className="text-sm font-bold text-stone-900">{title}</h3>
            <p className="text-xs text-stone-500 mt-1 leading-relaxed">
              {description}
            </p>
          </div>
        </div>

        <div className="flex gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={isPending}
            className="flex-1 h-9 rounded-lg border border-stone-250 bg-stone-50 text-xs font-semibold text-stone-700 hover:bg-stone-100 transition active:scale-98 cursor-pointer disabled:opacity-50"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isPending}
            className={`flex-1 h-9 rounded-lg text-xs font-bold text-white transition active:scale-98 cursor-pointer disabled:opacity-50 ${getConfirmButtonColor()}`}
          >
            {isPending ? (
              <span className="inline-flex items-center gap-1.5">
                <span className="h-3 w-3 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                Processing...
              </span>
            ) : (
              confirmLabel
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
