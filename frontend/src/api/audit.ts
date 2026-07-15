import { request, getAuthHeader, apiBase } from './base';

export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

export interface AuditEvent {
  event_id: string;
  occurred_at: string;
  action: string;
  category: string;
  outcome: string;
  actor_type: string;
  request_id?: string;
  source_ip_hash?: string;
  target_type?: string;
  target_id?: string;
  task_id?: string;
  schedule_id?: number;
  summary: string;
  changes?: Record<string, { from: JsonValue; to: JsonValue; changed?: boolean }>;
  metadata?: Record<string, JsonValue>;
  error_code?: string;
}

export interface AuditLogPage {
  events: AuditEvent[];
  total: number;
  limit: number;
  offset: number;
}

export interface AuditQueryParams {
  action?: string;
  category?: string;
  outcome?: string;
  actor_type?: string;
  task_id?: string;
  schedule_id?: number;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}

export function getAuditLogs(params: AuditQueryParams = {}): Promise<AuditLogPage> {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, val]) => {
    if (val !== undefined && val !== null && val !== '') {
      query.append(key, String(val));
    }
  });
  const queryString = query.toString();
  const path = `/api/audit${queryString ? `?${queryString}` : ''}`;
  return request<AuditLogPage>(path);
}

export async function downloadAuditExport(params: AuditQueryParams & { format: 'json' | 'csv' }): Promise<void> {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, val]) => {
    if (val !== undefined && val !== null && val !== '') {
      query.append(key, String(val));
    }
  });
  const queryString = query.toString();
  const path = `/api/audit/export${queryString ? `?${queryString}` : ''}`;

  const response = await fetch(`${apiBase}${path}`, {
    headers: {
      ...getAuthHeader(),
    },
  });

  if (!response.ok) {
    throw new Error(`Export failed: ${response.status}`);
  }

  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `audit-log-${new Date().toISOString().split('T')[0]}.${params.format}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}
