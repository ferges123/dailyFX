import { type InputHTMLAttributes, memo } from 'react';
import { Search, X } from 'lucide-react';

type SearchInputProps = Omit<
  InputHTMLAttributes<HTMLInputElement>,
  'onChange'
> & {
  value: string;
  onClear: () => void;
  onSearch: (v: string) => void;
  iconSize?: number;
  inputClassName?: string;
};

export const SearchInput = memo(function SearchInput({
  value,
  onClear,
  onSearch,
  iconSize = 13,
  placeholder = 'Search...',
  inputClassName = 'app-control app-control-muted h-8 pl-8 pr-7 text-xs',
  ...props
}: SearchInputProps) {
  return (
    <div className="relative w-full min-w-0 flex-1">
      <span className="pointer-events-none absolute inset-y-0 left-2.5 flex items-center text-stone-400">
        <Search size={iconSize} />
      </span>
      <input
        type="text"
        value={value}
        onChange={(e) => onSearch(e.target.value)}
        placeholder={placeholder}
        className={inputClassName}
        {...props}
      />
      {value ? (
        <button
          type="button"
          onClick={onClear}
          aria-label="Clear search"
          className="absolute right-2 top-1/2 -translate-y-1/2 text-stone-400 transition hover:text-stone-700"
        >
          <X size={14} />
        </button>
      ) : null}
    </div>
  );
});
