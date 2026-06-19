import { AlertTriangle, Trash2, X } from 'lucide-react';
import { useFocusTrap } from '../../hooks/useFocusTrap';

interface ConfirmDeleteModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  variant: 'rejected' | 'failed' | 'pending' | 'accepted' | 'all';
  isPending: boolean;
}

export function ConfirmDeleteModal({
  isOpen,
  onClose,
  onConfirm,
  variant,
  isPending,
}: ConfirmDeleteModalProps) {
  const trapRef = useFocusTrap(isOpen);

  if (!isOpen) return null;

  const getModalConfig = () => {
    switch (variant) {
      case 'all':
        return {
          title: 'Clear all history?',
          desc: 'This will permanently delete all generated images, thumbnails, and history records. This action cannot be undone.',
          btnText: 'Clear All',
          isDanger: true,
        };
      case 'rejected':
        return {
          title: 'Delete rejected items?',
          desc: 'This will permanently delete all rejected items and their generated images. This action cannot be undone.',
          btnText: 'Delete Rejected',
          isDanger: false,
        };
      case 'failed':
        return {
          title: 'Delete failed items?',
          desc: 'This will permanently delete all failed items. This action cannot be undone.',
          btnText: 'Delete Failed',
          isDanger: true,
        };
      case 'pending':
        return {
          title: 'Delete pending items?',
          desc: 'This will permanently delete all pending items. This action cannot be undone.',
          btnText: 'Delete Pending',
          isDanger: false,
        };
      case 'accepted':
        return {
          title: 'Delete accepted items?',
          desc: 'This will permanently delete all accepted items. This action cannot be undone.',
          btnText: 'Delete Accepted',
          isDanger: true,
        };
      default:
        return {
          title: 'Confirm deletion?',
          desc: 'This action cannot be undone.',
          btnText: 'Delete',
          isDanger: true,
        };
    }
  };

  const config = getModalConfig();
  const isDanger = config.isDanger;

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
        aria-labelledby="delete-modal-title"
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
          <div
            className={`shrink-0 rounded-xl p-2.5 ${isDanger ? 'bg-red-100' : 'bg-amber-100'}`}
          >
            <AlertTriangle
              size={18}
              className={isDanger ? 'text-red-600' : 'text-amber-600'}
            />
          </div>
          <div>
            <h3 id="delete-modal-title" className="text-sm font-bold text-stone-900">{config.title}</h3>
            <p className="text-xs text-stone-500 mt-1 leading-relaxed">
              {config.desc}
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
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isPending}
            className={`flex-1 h-9 rounded-lg text-xs font-bold text-white transition active:scale-98 cursor-pointer disabled:opacity-50 ${
              isDanger
                ? 'bg-red-600 hover:bg-red-700'
                : 'bg-amber-600 hover:bg-amber-700'
            }`}
          >
            {isPending ? (
              <span className="inline-flex items-center gap-1.5">
                <span className="h-3 w-3 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                Deleting...
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5">
                <Trash2 size={13} />
                {config.btnText}
              </span>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
