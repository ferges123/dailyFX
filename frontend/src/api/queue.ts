import { request } from './base';

export interface QueueItem {
  task_id: string;
  status: 'queued' | 'running' | 'cancel_requested' | 'cancelled' | 'succeeded' | 'failed';
  step: string | null;
  progress: number | null;
  priority: 'high' | 'normal' | 'low';
  attempt: number;
  created_at: string;
}

export interface QueueListResponse {
  total: number;
  items: QueueItem[];
}

export async function getQueueList(params?: {
  status?: string;
  source?: string;
  limit?: number;
  offset?: number;
}): Promise<QueueListResponse> {
  const query = new URLSearchParams();
  if (params?.status) query.append('status', params.status);
  if (params?.source) query.append('source', params.source);
  if (params?.limit) query.append('limit', String(params.limit));
  if (params?.offset) query.append('offset', String(params.offset));
  
  const queryStr = query.toString() ? `?${query.toString()}` : '';
  return request<QueueListResponse>(`/api/queue${queryStr}`);
}

export async function cancelQueueTask(taskId: string): Promise<{ message: string }> {
  return request<{ message: string }>(`/api/queue/${taskId}/cancel`, {
    method: 'POST',
  });
}

export async function retryQueueTask(taskId: string): Promise<{ message: string; task_id: string }> {
  return request<{ message: string; task_id: string }>(`/api/queue/${taskId}/retry`, {
    method: 'POST',
  });
}
