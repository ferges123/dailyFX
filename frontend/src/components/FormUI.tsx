import type { ReactNode } from 'react';
import { AlertTriangle, HelpCircle, Inbox } from 'lucide-react';
import { Field, SelectField } from './Field';

export function SectionCard({
  title,
  description,
  children,
  className = '',
}: {
  title: string;
  description?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`flex flex-col gap-2.5 md:gap-3 rounded-xl md:rounded-2xl border border-stone-200/80 bg-white/85 p-3 md:p-4 shadow-[0_8px_24px_rgba(36,29,16,0.04)] backdrop-blur-md ${className}`}>
      <div className="flex items-center gap-1.5">
        <div className="text-sm font-semibold text-stone-900">{title}</div>
        {description ? (
          <span title={description} aria-label={description} className="inline-flex items-center text-stone-400 transition hover:text-stone-600">
            <HelpCircle size={14} />
          </span>
        ) : null}
      </div>
      {children}
    </section>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className = '',
}: {
  icon?: ReactNode;
  title: string;
  description: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={`rounded-xl md:rounded-2xl border border-dashed border-stone-200/90 bg-white/60 px-3 py-5 md:px-4 md:py-7 text-center shadow-[0_8px_24px_rgba(36,29,16,0.03)] backdrop-blur-sm ${className}`}>
      <div className="mx-auto flex w-fit items-center justify-center rounded-full bg-white p-2.5 text-stone-400 shadow-xs ring-1 ring-stone-200">
        {icon ?? <Inbox size={18} />}
      </div>
      <div className="mt-3 text-sm font-semibold text-stone-900">{title}</div>
      <p className="mt-1 text-sm leading-6 text-stone-500">{description}</p>
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  );
}

export function InlineError({
  title,
  message,
  className = '',
}: {
  title: string;
  message: string;
  className?: string;
}) {
  return (
    <div className={`flex items-start gap-1.5 md:gap-2 rounded-lg md:rounded-xl border border-rose-200/70 bg-rose-50/80 px-2.5 py-2 md:px-3 md:py-2.5 text-sm text-rose-950 shadow-[0_8px_20px_rgba(180,35,24,0.05)] ${className}`}>
      <AlertTriangle size={16} className="mt-0.5 shrink-0 text-rose-500" />
      <div className="grid gap-0.5">
        <div className="font-semibold">{title}</div>
        <div className="text-rose-800">{message}</div>
      </div>
    </div>
  );
}

type ProviderOption = { label: string; value: string };

export function ProviderModelField({
  label,
  provider,
  providerOptions,
  onProviderChange,
  model,
  modelOptions,
  onModelChange,
  freeTextProviders = [],
  providerHelp,
  modelPlaceholder,
  className = '',
}: {
  label: string;
  provider: string;
  providerOptions: ProviderOption[];
  onProviderChange: (value: string) => void;
  model: string;
  modelOptions: ProviderOption[];
  onModelChange: (value: string) => void;
  freeTextProviders?: string[];
  providerHelp?: string;
  modelPlaceholder?: string;
  className?: string;
}) {
  const shouldUseFreeText = provider !== 'none' && freeTextProviders.includes(provider);
  const modelDisabled = provider === 'none';

  return (
    <div className={`grid gap-2.5 md:gap-3 rounded-xl md:rounded-2xl border border-stone-200/80 bg-white/85 p-3 md:p-4 shadow-[0_8px_24px_rgba(36,29,16,0.04)] backdrop-blur-md ${className}`}>
      <div className="flex items-center gap-1.5">
        <div className="text-xs font-semibold uppercase tracking-[0.2em] text-stone-500">{label}</div>
        {providerHelp ? (
          <span title={providerHelp} aria-label={providerHelp} className="inline-flex items-center text-stone-400 transition hover:text-stone-600">
            <HelpCircle size={12} />
          </span>
        ) : null}
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <SelectField label="Provider" value={provider} onChange={(e) => onProviderChange(e.target.value)}>
          <option value="none">None</option>
          {providerOptions.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </SelectField>
        {provider === 'none' ? (
          <Field label="Model" value="" disabled placeholder="Enable a provider first" optional />
        ) : shouldUseFreeText ? (
          <Field label="Model" value={model} onChange={(e) => onModelChange(e.target.value)} placeholder={modelPlaceholder} optional />
        ) : (
          <SelectField label="Model" value={model} onChange={(e) => onModelChange(e.target.value)} disabled={modelDisabled}>
            {modelOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </SelectField>
        )}
      </div>
    </div>
  );
}
