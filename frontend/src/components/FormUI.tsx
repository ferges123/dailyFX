import type { ReactNode } from 'react';
import { AlertTriangle, Inbox } from 'lucide-react';
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
    <section className={`grid gap-3 rounded-lg border border-stone-200 bg-white p-3.5 ${className}`}>
      <div className="grid gap-0.5">
        <div className="text-sm font-semibold text-stone-900">{title}</div>
        {description && <p className="text-xs leading-5 text-stone-500">{description}</p>}
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
    <div className={`rounded-lg border border-dashed border-stone-200 bg-stone-50 px-4 py-6 text-center ${className}`}>
      <div className="mx-auto flex w-fit items-center justify-center rounded-full bg-white p-2 text-stone-400 shadow-sm ring-1 ring-stone-200">
        {icon ?? <Inbox size={18} />}
      </div>
      <div className="mt-3 text-sm font-semibold text-stone-900">{title}</div>
      <p className="mt-1 text-sm text-stone-500">{description}</p>
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
    <div className={`flex items-start gap-2 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-900 ${className}`}>
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
    <div className={`grid gap-2 rounded-lg border border-stone-200 bg-white p-3 ${className}`}>
      <div className="grid gap-1">
        <div className="text-xs font-semibold uppercase tracking-wide text-stone-500">{label}</div>
        {providerHelp && <p className="text-xs leading-5 text-stone-500">{providerHelp}</p>}
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
