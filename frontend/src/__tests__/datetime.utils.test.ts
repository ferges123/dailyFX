import { describe, expect, it } from 'vitest';
import { formatDate, formatDateTime } from '../pages/datetime.utils';

describe('datetime utilities', () => {
  it('should format standard ISO datetime strings with the year', () => {
    const formatted = formatDateTime('2026-06-19T12:00:00Z');
    expect(formatted).toContain('2026');
    expect(formatted).not.toContain('T');
  });

  it('should format EXIF colon-separated datetime strings with the year', () => {
    const formatted = formatDateTime('2025:06:04 12:34:56');
    expect(formatted).toContain('2025');
    expect(formatted).not.toContain('2025:06:04');
  });

  it('should format EXIF colon-separated date only strings with the year', () => {
    const formatted = formatDate('2025:06:04');
    expect(formatted).toContain('2025');
    expect(formatted).not.toContain('2025:06:04');
    // Ensure it's not parsed incorrectly as Jan 1st 06:04
    const badFormatted = formatDate('2025-01-01T06:04:00Z');
    expect(formatted).not.toBe(badFormatted);
  });

  it('should handle null, undefined, or empty values', () => {
    expect(formatDate(null)).toBe('');
    expect(formatDate(undefined)).toBe('');
    expect(formatDateTime(null)).toBe('');
    expect(formatDateTime(undefined)).toBe('');
  });
});
