import React from 'react';
import { AlertTriangle, Loader2, RotateCw } from 'lucide-react';
export { EmptyState } from './FormUI';

export function InlineSpinner({ className = '' }: { className?: string }) {
  return (
    <div className={`flex items-center justify-center gap-2 text-stone-500 py-4 ${className}`}>
      <Loader2 size={16} className="animate-spin text-emerald-700" />
      <span className="text-sm font-medium">Loading...</span>
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
      className={`inline-flex items-center gap-1.5 rounded bg-stone-100 hover:bg-stone-200 text-stone-700 hover:text-stone-900 border border-stone-300 py-1 px-3 text-xs font-semibold shadow-sm transition-colors ${className}`}
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
    <div className={`flex flex-col gap-3 rounded-lg border border-red-200 bg-red-50/70 p-4 text-red-900 shadow-sm md:flex-row md:items-center md:justify-between ${className}`}>
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
            className="inline-flex items-center gap-1.5 rounded border border-red-300 bg-white hover:bg-red-50 text-red-700 hover:text-red-900 py-1 px-3 text-xs font-semibold shadow-sm transition-all"
          >
            <RotateCw size={12} />
            Try again
          </button>
        </div>
      )}
    </div>
  );
}
