import type { ReactNode } from 'react';
import { HelpCircle } from 'lucide-react';
import type { GenerationModuleConfigField, GenerationModuleInfo } from '../api/client';
import { MODULE_PRESETS, type ModulePreset } from '../pages/automation.types';

export function FilterRow({
  title, icon, enabled, weight, config, onEnabledChange, onWeightChange,
}: {
  title: ReactNode; icon: ReactNode; enabled: boolean; weight: number;
  config: ReactNode; onEnabledChange: (v: boolean) => void; onWeightChange: (v: number) => void;
}) {
  return (
    <tr className={`group transition-colors duration-150 ${enabled ? 'bg-emerald-50/30 font-medium' : 'hover:bg-stone-50/50'}`}>
      <td className="py-2.5 px-3 align-top">
        <div className="flex min-w-0 items-start gap-1.5 text-stone-700">
          {icon && <span className="text-stone-400 mt-0.5 shrink-0">{icon}</span>}
          <div className="min-w-0">{title}</div>
        </div>
      </td>
      <td className="py-2.5 px-3 align-top text-center">
        <input type="checkbox" checked={enabled} onChange={(e) => onEnabledChange(e.target.checked)}
          className="h-4 w-4 accent-emerald-700 cursor-pointer rounded-sm border-stone-300 text-emerald-600 focus:ring-emerald-500" />
      </td>
      <td className="py-2.5 px-3 align-top text-center">
        <input type="number" min={0} value={weight} onChange={(e) => onWeightChange(Number(e.target.value) || 0)}
          className="w-12 rounded-sm border border-stone-300 bg-white px-1.5 py-0.5 text-xs text-center outline-hidden focus:border-emerald-700" />
      </td>
      <td className="py-2.5 px-3 align-top">
        <div className="text-xs text-stone-600">{config}</div>
      </td>
    </tr>
  );
}

export function ModuleConfigEditor({ module, config, onChange }: {
  module: GenerationModuleInfo; config: Record<string, unknown>; onChange: (key: string, value: unknown) => void;
}) {
  const schema: GenerationModuleConfigField[] = module.config_schema ?? [];
  if (schema.length === 0) {
    return (
      <span
        title={module.description}
        aria-label={module.description}
        className="inline-flex items-center text-stone-400 transition hover:text-stone-600"
      >
        <HelpCircle size={12} />
      </span>
    );
  }

  const presets = MODULE_PRESETS[module.name] ?? [];

  return (
    <div className="grid grid-cols-1 gap-2.5 w-full sm:flex sm:flex-wrap sm:items-center sm:gap-2">
      {presets.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {presets.map((preset: ModulePreset) => {
            const active = Object.entries(preset.config).every(([k, v]) => JSON.stringify(config[k]) === JSON.stringify(v));
            return (
              <button key={preset.label} type="button"
                onClick={() => Object.entries(preset.config).forEach(([k, v]) => onChange(k, v))}
                className={`rounded-full border px-2 py-0.5 text-[11px] ${active
                  ? 'border-emerald-500 bg-emerald-100 font-semibold text-emerald-900'
                  : 'border-stone-300 bg-white text-stone-600 hover:border-emerald-400 hover:bg-emerald-50 hover:text-emerald-800'}`}>
                {preset.label}
              </button>
            );
          })}
        </div>
      )}
      {schema.map((field) => {
        const value = config[field.key] ?? field.default;
        if (field.type === 'multiselect' && presets.length > 0) return null;
        if (field.type === 'number') {
          const numericValue = typeof value === 'number' ? value : Number(field.default ?? field.min ?? 0);
          return (
            <label key={field.key} className="flex items-center justify-between gap-2 text-xs w-full sm:inline-flex sm:w-auto sm:justify-start sm:gap-1.5">
              <span className="text-stone-500 font-medium sm:font-normal">{field.label}</span>
              <input type="number" min={field.min ?? undefined} max={field.max ?? undefined} step={field.step ?? 1}
                value={Number.isFinite(numericValue) ? numericValue : 0}
                onChange={(e) => { const v = Number(e.target.value); onChange(field.key, Number.isFinite(v) ? v : field.default ?? 0); }}
                className="h-7 w-20 rounded-sm border border-stone-300 bg-white px-2 text-sm outline-hidden focus:border-emerald-700 text-right sm:text-left" />
            </label>
          );
        }
        if (field.type === 'select') {
          const currentValue = typeof value === 'string' ? value : String(field.default ?? '');
          return (
            <label key={field.key} className="flex items-center justify-between gap-2 text-xs w-full sm:inline-flex sm:w-auto sm:justify-start sm:gap-1.5">
              <span className="text-stone-500 font-medium sm:font-normal">{field.label}</span>
              <select value={currentValue} onChange={(e) => onChange(field.key, e.target.value)}
                className="h-7 rounded-sm border border-stone-300 bg-white px-2 text-sm outline-hidden focus:border-emerald-700 text-right sm:text-left">
                {(field.options ?? []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </label>
          );
        }
        if (field.type === 'multiselect') {
          const selected = Array.isArray(value) ? value.filter((e): e is string => typeof e === 'string')
            : Array.isArray(field.default) ? field.default.filter((e): e is string => typeof e === 'string') : [];
          return (
            <div key={field.key} className="flex flex-col gap-1.5 w-full mt-0.5">
              <span className="text-[10px] font-bold uppercase tracking-wider text-stone-400 sm:hidden">{field.label}</span>
              <div className="flex flex-wrap gap-1">
                {(field.options ?? []).map((o) => {
                  const checked = selected.includes(o.value);
                  return (
                    <label key={o.value} className={`inline-flex cursor-pointer items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] ${checked ? 'border-emerald-300 bg-emerald-50 text-emerald-900' : 'border-stone-200 bg-white text-stone-700'}`}>
                      <input type="checkbox" checked={checked} className="h-3 w-3 accent-emerald-700"
                        onChange={(e) => onChange(field.key, e.target.checked ? [...selected, o.value] : selected.filter((x) => x !== o.value))} />
                      <span>{o.label}</span>
                    </label>
                  );
                })}
              </div>
            </div>
          );
        }
        const currentValue = typeof value === 'string' ? value : String(field.default ?? '');
        return (
          <label key={field.key} className="flex items-center justify-between gap-2 text-xs w-full sm:inline-flex sm:w-auto sm:justify-start sm:gap-1.5">
            <span className="text-stone-500 font-medium sm:font-normal">{field.label}</span>
            <input type="text" value={currentValue} placeholder={field.placeholder ?? ''}
              onChange={(e) => onChange(field.key, e.target.value)}
              className="h-7 rounded-sm border border-stone-300 bg-white px-2 text-sm outline-hidden focus:border-emerald-700 text-right sm:text-left" />
          </label>
        );
      })}
    </div>
  );
}
