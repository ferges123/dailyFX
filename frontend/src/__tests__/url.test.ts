import { describe, expect, it } from 'vitest';
import { appendQueryParam } from '../utils/url';

describe('appendQueryParam', () => {
  it('uses & when the URL already has query parameters', () => {
    expect(appendQueryParam('/image?t=123', 'thumbnail', 'true')).toBe(
      '/image?t=123&thumbnail=true',
    );
  });

  it('uses ? when the URL has no query parameters', () => {
    expect(appendQueryParam('/image', 'thumbnail', 'true')).toBe(
      '/image?thumbnail=true',
    );
  });
});
