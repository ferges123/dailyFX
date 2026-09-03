import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { request, ApiError, registerOnUnauthorized } from '../api/base';
import { getSettings, updateSettings } from '../api/settings';
import { getGenerationHistory } from '../api/generation';

describe('API Layer - Base', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
    localStorage.removeItem('dailyfx_token');
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('handles successful requests and returns JSON', async () => {
    const mockData = { success: true };
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(mockData), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    const result = await request('/test-endpoint');
    expect(result).toEqual(mockData);
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/test-endpoint'),
      expect.objectContaining({
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
        }),
      }),
    );
  });

  it('includes Authorization header if token exists in localStorage', async () => {
    localStorage.setItem('dailyfx_token', 'my-auth-token');
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({}), { status: 200 }),
    );

    await request('/auth-test');
    expect(fetch).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Bearer my-auth-token',
        }),
      }),
    );
  });

  it('throws ApiError with payload detail on response error', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: 'Invalid parameters' }), {
        status: 400,
      }),
    );

    try {
      await request('/bad-endpoint');
      throw new Error('Expected request to throw ApiError');
    } catch (error) {
      const apiErr = error as ApiError;
      expect(apiErr).toBeInstanceOf(ApiError);
      expect(apiErr.status).toBe(400);
      expect(apiErr.detail).toBe('Invalid parameters');
    }
  });

  it('triggers unauthorized callback on 401', async () => {
    const cb = vi.fn();
    registerOnUnauthorized(cb);
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: 'Unauthorized' }), { status: 401 }),
    );

    try {
      await request('/unauthorized');
      throw new Error('Expected request to throw');
    } catch {
      expect(cb).toHaveBeenCalled();
    }
  });

  it('throws timeout ApiError when fetch is aborted', async () => {
    const abortError = new Error('The user aborted a request.');
    abortError.name = 'AbortError';
    vi.mocked(fetch).mockRejectedValueOnce(abortError);

    try {
      await request('/timeout');
      throw new Error('Expected request to throw timeout error');
    } catch (error) {
      const apiErr = error as ApiError;
      expect(apiErr).toBeInstanceOf(ApiError);
      expect(apiErr.status).toBe(408);
      expect(apiErr.message).toContain('API request timed out');
    }
  });

  it('uses a caller-provided timeout', async () => {
    const timeoutSpy = vi.spyOn(globalThis, 'setTimeout');
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({}), { status: 200 }),
    );

    await request('/long-running-endpoint', { timeoutMs: 60_000 });

    expect(timeoutSpy).toHaveBeenCalledWith(expect.any(Function), 60_000);
  });

  it('fails fast with a clear error while the browser is offline', async () => {
    Object.defineProperty(navigator, 'onLine', {
      configurable: true,
      value: false,
    });

    await expect(request('/offline-endpoint')).rejects.toMatchObject({
      status: 0,
      detail: 'Offline: this action requires a connection',
    });
    expect(fetch).not.toHaveBeenCalled();

    Object.defineProperty(navigator, 'onLine', {
      configurable: true,
      value: true,
    });
  });

  it('does not lose default headers (Content-Type, Authorization) when custom headers are passed in init', async () => {
    localStorage.setItem('dailyfx_token', 'my-auth-token');
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({}), { status: 200 }),
    );

    await request('/custom-headers', {
      headers: { 'X-Custom-Header': 'custom-value' },
    });

    expect(fetch).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
          Authorization: 'Bearer my-auth-token',
          'X-Custom-Header': 'custom-value',
        }),
      }),
    );
  });
});

describe('API Layer - Settings', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('getSettings makes a GET request', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ immich_url: '' }), { status: 200 }),
    );
    await getSettings();
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/settings'),
      expect.any(Object),
    );
  });

  it('updateSettings makes a PUT request with body', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({}), { status: 200 }),
    );
    const fullPayload = {
      immich_url: 'http://test',
      local_ai_base_url: 'http://local-ai:11434/v1',
      ai_vision_hourly_limit: 10,
      ai_image_hourly_limit: 10,
      debug_mode: false,
      favorite_albums_json: null,
      ai_custom_prompt: null,
      retention_enabled: false,
      retention_rejected_files_days: null,
      retention_rejected_metadata_days: null,
      retention_failed_files_days: null,
      retention_failed_metadata_days: null,
      retention_uploaded_files_days: null,
      retention_uploaded_metadata_days: null,
      retention_task_days: null,
      retention_audit_days: null,
      retention_backup_count: 5,
    };
    await updateSettings(fullPayload);
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/settings'),
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify(fullPayload),
      }),
    );
  });
});

import { getImmichAssets } from '../api/immich';

describe('API Layer - Generation', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('getGenerationHistory appends status and search query parameters', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ items: [] }), { status: 200 }),
    );
    await getGenerationHistory('UPLOADED', 10, 'my-search');
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining(
        '/api/generation/history?status=UPLOADED&offset=10&search=my-search&limit=10',
      ),
      expect.anything(),
    );
  });

  it('getImmichAssets appends person_ids query parameters correctly', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(
        JSON.stringify({ items: [], total: 0, count: 0, next_page: null }),
        {
          status: 200,
        },
      ),
    );
    await getImmichAssets({
      mediaType: 'photo',
      personIds: ['person-1', 'person-2'],
      page: 1,
      size: 24,
    });
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/immich/assets?'),
      expect.anything(),
    );
    const calledUrl = vi.mocked(fetch).mock.calls[0][0] as string;
    expect(calledUrl).toContain('person_ids=person-1');
    expect(calledUrl).toContain('person_ids=person-2');
  });
});
