function resolveApiBase(): string {
  const configured = import.meta.env.VITE_API_BASE_URL?.trim();
  if (configured) return configured.replace(/\/$/, '');
  return '';
}

export const apiBase = resolveApiBase();

export function getAuthToken(): string | null {
  return localStorage.getItem('dailyfx_token');
}

export function getAuthHeader(): Record<string, string> {
  const token = getAuthToken();
  return token ? { 'Authorization': `Bearer ${token}` } : {};
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

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(`${apiBase}${path}`, {
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeader(),
        ...init?.headers,
      },
      ...init,
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
      throw new ApiError(408, 'API request timed out (15s limit)');
    }
    throw error;
  }
}
