import { type ReactNode } from 'react';
import { HelpCircle } from 'lucide-react';

export function ScheduleSummaryCard({
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
    <article className="rounded-2xl border border-stone-200/70 bg-white/75 p-2.5">
      <div className="flex items-center gap-2">
        <div
          className={`flex h-8 w-8 items-center justify-center rounded-xl border ${toneClass}`}
        >
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
          <div className="text-lg font-semibold text-stone-950">{value}</div>
        </div>
      </div>
    </article>
  );
}
