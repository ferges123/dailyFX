import type { ReactNode } from 'react';

export function StatusTile({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-stone-200/80 bg-white/85 p-4 shadow-[0_8px_24px_rgba(36,29,16,0.04)] backdrop-blur-md">
      <div className="flex items-center gap-2 text-stone-500">
        {icon}
        <span className="text-xs font-semibold uppercase tracking-[0.2em]">{label}</span>
      </div>
      <div className="mt-2 text-base font-semibold text-stone-950">{value}</div>
    </div>
  );
}
