import type { ReactNode } from 'react';

type StatusTone = 'neutral' | 'success' | 'warning' | 'danger';

const toneClasses: Record<StatusTone, { shell: string; label: string; value: string }> = {
  neutral: {
    shell: 'border-stone-200/80 bg-white/85',
    label: 'text-stone-500',
    value: 'text-stone-950',
  },
  success: {
    shell: 'border-emerald-200/80 bg-emerald-50/85',
    label: 'text-emerald-700',
    value: 'text-emerald-950',
  },
  warning: {
    shell: 'border-amber-200/80 bg-amber-50/85',
    label: 'text-amber-700',
    value: 'text-amber-950',
  },
  danger: {
    shell: 'border-rose-200/80 bg-rose-50/85',
    label: 'text-rose-700',
    value: 'text-rose-950',
  },
};

export function StatusTile({
  icon,
  label,
  value,
  detail,
  tone = 'neutral',
}: {
  icon: ReactNode;
  label: string;
  value: string;
  detail?: string | null;
  tone?: StatusTone;
}) {
  const classes = toneClasses[tone];
  return (
    <div className={`rounded-2xl border p-3 shadow-[0_8px_24px_rgba(36,29,16,0.04)] backdrop-blur-md md:p-4 ${classes.shell}`}>
      <div className={`flex items-center gap-2 ${classes.label}`}>
        {icon}
        <span className="text-xs font-semibold uppercase tracking-[0.2em]">{label}</span>
      </div>
      <div className="mt-1.5 flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <div className={`text-base font-semibold ${classes.value}`}>{value}</div>
        {detail ? <div className="text-xs text-stone-500">{detail}</div> : null}
      </div>
    </div>
  );
}
