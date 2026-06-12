import { type ReactNode } from 'react';

type TestableInputRowProps = {
  label: string;
  value: string;
  placeholder?: string;
  error?: string;
  onChange: (value: string) => void;
  testButton?: ReactNode;
};

export function TestButton({
  icon,
  label,
  pending,
  onClick,
}: {
  icon: ReactNode;
  label: string;
  pending: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={pending}
      className="app-button-secondary h-11 w-[84px] shrink-0 justify-center px-3 text-xs disabled:opacity-60"
    >
      {icon}
      {label}
    </button>
  );
}

export function TestableInputRow({
  label,
  value,
  placeholder,
  error,
  onChange,
  testButton,
}: TestableInputRowProps) {
  return (
    <label className="grid gap-1.5 text-sm font-medium text-stone-800">
      <span className="flex items-center gap-1 text-xs font-semibold uppercase tracking-[0.18em] text-stone-500">
        <span>{label}</span>
      </span>
      <div className="flex items-stretch gap-2">
        <input
          type="password"
          className={`app-control h-11 flex-1 min-w-0 text-xs ${error ? 'border-rose-300 focus:border-rose-500' : ''}`}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          autoComplete="new-password"
        />
        {testButton}
      </div>
      {error ? <span className="text-xs text-rose-600">{error}</span> : null}
    </label>
  );
}
