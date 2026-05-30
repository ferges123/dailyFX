function parseDate(value: string | null | undefined): Date {
  if (!value || typeof value !== 'string') return new Date(NaN);
  // SQLite returns naive datetimes without timezone — treat as UTC
  const normalized = value.endsWith('Z') || /[+-]\d{2}:\d{2}$/.test(value) ? value : value + 'Z';
  return new Date(normalized);
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '';
  const parsed = parseDate(value);
  if (Number.isNaN(parsed.getTime())) return typeof value === 'string' ? value : '';
  return parsed.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '';
  const parsed = parseDate(value);
  if (Number.isNaN(parsed.getTime())) return typeof value === 'string' ? value : '';
  return parsed.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}
