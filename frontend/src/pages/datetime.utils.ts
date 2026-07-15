function parseDate(value: string | null | undefined): Date {
  if (!value || typeof value !== 'string') return new Date(NaN);
  
  // Convert standard EXIF colons in date (YYYY:MM:DD HH:MM:SS) to ISO format (YYYY-MM-DD HH:MM:SS)
  let cleanValue = value;
  if (/^\d{4}:\d{2}:\d{2}/.test(cleanValue)) {
    cleanValue = cleanValue.replace(/^(\d{4}):(\d{2}):(\d{2})/, '$1-$2-$3');
  }

  // SQLite returns naive datetimes without timezone — treat as UTC
  const normalized =
    cleanValue.endsWith('Z') || /[+-]\d{2}:\d{2}$/.test(cleanValue) ? cleanValue : cleanValue + 'Z';
  return new Date(normalized);
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '';
  const parsed = parseDate(value);
  if (Number.isNaN(parsed.getTime()))
    return typeof value === 'string' ? value : '';
  return parsed.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '';
  const parsed = parseDate(value);
  if (Number.isNaN(parsed.getTime()))
    return typeof value === 'string' ? value : '';
  return parsed.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}
