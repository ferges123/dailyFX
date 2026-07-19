import { type ReactNode, memo } from 'react';
import { SlidersHorizontal, X } from 'lucide-react';

type FilterBarProps = {
  title?: string;
  activeCount?: number;
  onClear?: () => void;
  clearLabel?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
};

export const FilterBar = memo(function FilterBar({
  title = 'Filters',
  activeCount = 0,
  onClear,
  clearLabel = 'Clear filters',
  actions,
  children,
  className = '',
  bodyClassName = 'grid gap-3',
}: FilterBarProps) {
  const hasActive = activeCount > 0 && onClear;
  return (
    <div className={`app-panel grid gap-3 p-3 md:p-4 ${className}`}>
      {(title || actions) && (
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.18em] text-stone-500">
            <SlidersHorizontal size={13} />
            <span>{title}</span>
            {hasActive ? (
              <span className="ml-1 inline-flex items-center justify-center rounded-full bg-emerald-100 px-1.5 py-0.5 text-[10px] font-bold text-emerald-800">
                {activeCount}
              </span>
            ) : null}
          </div>
          <div className="flex items-center gap-2">
            {hasActive ? (
              <button
                type="button"
                onClick={onClear}
                className="inline-flex h-7 items-center gap-1 rounded-lg border border-stone-200 bg-stone-50 px-2 text-[11px] font-semibold text-stone-600 transition hover:border-stone-300 hover:bg-stone-100 hover:text-stone-900"
              >
                <X size={12} />
                {clearLabel}
              </button>
            ) : null}
            {actions}
          </div>
        </div>
      )}
      <div className={bodyClassName}>{children}</div>
    </div>
  );
});
