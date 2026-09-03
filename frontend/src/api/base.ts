function resolveApiBase(): string {
  const configured = import.meta.env.VITE_API_BASE_URL?.trim();
  if (configured) return configured.replace(/\/$/, '');
  return '';
}

export const apiBase = resolveApiBase();
export const DEFAULT_REQUEST_TIMEOUT_MS = 15_000;

export type ApiRequestOptions = RequestInit & {
  timeoutMs?: number;
};

export function getAuthToken(): string | null {
  return localStorage.getItem('dailyfx_token');
}

export function getAuthHeader(): Record<string, string> {
  const token = getAuthToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
    this.name = 'ApiError';
  }
}

let onUnauthorizedCallback: (() => void) | null = null;
export function registerOnUnauthorized(cb: () => void) {
  onUnauthorizedCallback = cb;
}

export function getApiUrl(path: string) {
  return `${apiBase}${path}`;
}

export async function handleResponseError(response: Response): Promise<never> {
  let detail = `API request failed: ${response.status}`;
  try {
    const payload = (await response.json()) as { detail?: string };
    if (payload.detail) {
      detail = payload.detail;
    }
  } catch {
    // ignore
  }
  if (response.status === 401) {
    onUnauthorizedCallback?.();
  }
  throw new ApiError(response.status, detail);
}

export async function request<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  if (typeof navigator !== 'undefined' && navigator.onLine === false) {
    throw new ApiError(0, 'Offline: this action requires a connection');
  }
  const { headers: initHeaders, timeoutMs = DEFAULT_REQUEST_TIMEOUT_MS, ...restInit } = options;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${apiBase}${path}`, {
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeader(),
        ...initHeaders,
      },
      ...restInit,
    });
    clearTimeout(timeoutId);
    if (!response.ok) {
      await handleResponseError(response);
    }
    if (response.status === 204) {
      return {} as T;
    }
    return response.json() as Promise<T>;
  } catch (error) {
    clearTimeout(timeoutId);
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiError(408, `API request timed out (${timeoutMs / 1000}s limit)`);
    }
    throw error;
  }
}

export async function requestText(
  path: string,
  options: ApiRequestOptions = {},
): Promise<string> {
  if (typeof navigator !== 'undefined' && navigator.onLine === false) {
    throw new ApiError(0, 'Offline: this action requires a connection');
  }
  const { headers: initHeaders, timeoutMs = DEFAULT_REQUEST_TIMEOUT_MS, ...restInit } = options;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${apiBase}${path}`, {
      signal: controller.signal,
      headers: {
        ...getAuthHeader(),
        ...initHeaders,
      },
      ...restInit,
    });
    clearTimeout(timeoutId);
    if (!response.ok) {
      await handleResponseError(response);
    }
    return response.text();
  } catch (error) {
    clearTimeout(timeoutId);
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiError(408, `API request timed out (${timeoutMs / 1000}s limit)`);
    }
    throw error;
  }
}
