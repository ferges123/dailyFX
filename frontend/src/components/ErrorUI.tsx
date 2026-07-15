import { AlertTriangle, Loader2, RotateCw } from 'lucide-react';
export { EmptyState } from './FormUI';

export function InlineSpinner({ className = '' }: { className?: string }) {
  return (
    <div
      className={`flex items-center justify-center gap-2 py-4 text-stone-500 ${className}`}
      role="status"
      aria-live="polite"
    >
      <Loader2 size={16} className="animate-spin text-emerald-700" />
      <span className="text-sm font-medium">Loading…</span>
    </div>
  );
}

export function RetryButton({
  onClick,
  label = 'Try again',
  className = '',
}: {
  onClick: () => void;
  label?: string;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`app-button-secondary px-3 py-1.5 text-xs ${className}`}
    >
      <RotateCw size={12} />
      {label}
    </button>
  );
}

export function ErrorBanner({
  error,
  title = 'Error occurred',
  onRetry,
  className = '',
}: {
  error: Error | string | null;
  title?: string;
  onRetry?: () => void;
  className?: string;
}) {
  if (!error) return null;
  const message = typeof error === 'string' ? error : error.message;

  return (
    <div
      className={`flex flex-col gap-3 rounded-2xl border border-rose-200/70 bg-rose-50/80 p-4 text-rose-950 shadow-[0_10px_24px_rgba(180,35,24,0.08)] backdrop-blur-sm md:flex-row md:items-center md:justify-between ${className}`}
    >
      <div className="flex items-start gap-3">
        <AlertTriangle size={18} className="mt-0.5 shrink-0 text-red-600" />
        <div className="text-sm">
          <p className="font-semibold">{title}</p>
          <p className="text-red-800">{message}</p>
        </div>
      </div>
      {onRetry && (
        <div className="self-end md:self-center">
          <button
            type="button"
            onClick={onRetry}
            className="inline-flex items-center gap-1.5 rounded-xl border border-rose-200 bg-white px-3 py-1.5 text-xs font-semibold text-rose-700 shadow-xs transition hover:bg-rose-50 hover:text-rose-900"
          >
            <RotateCw size={12} />
            Try again
          </button>
        </div>
      )}
    </div>
  );
}
