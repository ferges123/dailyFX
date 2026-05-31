import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from 'react';

type FieldProps = {
  label: string;
  hint?: ReactNode;
  icon?: ReactNode;
  error?: string;
  required?: boolean;
  optional?: boolean;
} & InputHTMLAttributes<HTMLInputElement>;

export function Field({ label, hint, icon, error, required, optional, className = '', ...props }: FieldProps) {
  return (
    <label className="grid gap-1.5 text-sm font-medium text-stone-800">
      <span className="flex items-center gap-1 text-xs font-semibold uppercase tracking-[0.18em] text-stone-500">
        <span>{label}</span>
        {required && <span className="text-rose-500">*</span>}
        {optional && !required && <span className="text-xs font-medium text-stone-400">optional</span>}
      </span>
      <div className="relative">
        {icon ? <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-stone-400">{icon}</span> : null}
        <input
          className={`app-control ${error ? 'border-rose-300 focus:border-rose-500' : ''} ${icon ? 'pl-9 pr-3' : ''} ${className}`}
          {...props}
        />
      </div>
      {error ? <span className="text-xs font-normal leading-5 text-rose-600">{error}</span> : null}
      {hint ? <span className="text-xs font-normal leading-5 text-stone-500">{hint}</span> : null}
    </label>
  );
}

type SelectFieldProps = {
  label: string;
  children: ReactNode;
  error?: string;
  required?: boolean;
  optional?: boolean;
} & SelectHTMLAttributes<HTMLSelectElement>;

export function SelectField({ label, children, error, required, optional, className = '', ...props }: SelectFieldProps) {
  return (
    <label className="grid gap-1.5 text-sm font-medium text-stone-800">
      <span className="flex items-center gap-1 text-xs font-semibold uppercase tracking-[0.18em] text-stone-500">
        <span>{label}</span>
        {required && <span className="text-rose-500">*</span>}
        {optional && !required && <span className="text-xs font-medium text-stone-400">optional</span>}
      </span>
      <select
        className={`app-control ${error ? 'border-rose-300 focus:border-rose-500' : ''} ${className}`}
        {...props}
      >
        {children}
      </select>
      {error ? <span className="text-xs font-normal leading-5 text-rose-600">{error}</span> : null}
    </label>
  );
}
