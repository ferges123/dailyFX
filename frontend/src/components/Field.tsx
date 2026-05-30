import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from 'react';

type FieldProps = {
  label: string;
  hint?: ReactNode;
  icon?: ReactNode;
  required?: boolean;
  optional?: boolean;
} & InputHTMLAttributes<HTMLInputElement>;

export function Field({ label, hint, icon, required, optional, className = '', ...props }: FieldProps) {
  return (
    <label className="grid gap-1 text-sm font-medium text-stone-800">
      <span className="flex items-center gap-1">
        <span>{label}</span>
        {required && <span className="text-rose-500">*</span>}
        {optional && !required && <span className="text-xs font-medium text-stone-400">optional</span>}
      </span>
      <div className="relative">
        {icon ? <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-stone-400">{icon}</span> : null}
        <input
          className={`h-9 w-full min-w-0 rounded-md border border-stone-300 bg-white text-sm outline-none focus:border-emerald-700 ${icon ? 'pl-9 pr-3' : 'px-3'} ${className}`}
          {...props}
        />
      </div>
      {hint ? <span className="text-xs font-normal text-stone-500">{hint}</span> : null}
    </label>
  );
}

type SelectFieldProps = {
  label: string;
  children: ReactNode;
  required?: boolean;
  optional?: boolean;
} & SelectHTMLAttributes<HTMLSelectElement>;

export function SelectField({ label, children, required, optional, className = '', ...props }: SelectFieldProps) {
  return (
    <label className="grid gap-1 text-sm font-medium text-stone-800">
      <span className="flex items-center gap-1">
        <span>{label}</span>
        {required && <span className="text-rose-500">*</span>}
        {optional && !required && <span className="text-xs font-medium text-stone-400">optional</span>}
      </span>
      <select
        className={`h-9 w-full min-w-0 rounded-md border border-stone-300 bg-white px-3 text-sm outline-none focus:border-emerald-700 ${className}`}
        {...props}
      >
        {children}
      </select>
    </label>
  );
}
