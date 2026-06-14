import { request } from './base';
import { type NotificationPreset, type PushSubscriptionInfo } from './types';

export async function getVapidPublicKey(): Promise<string> {
  const data = await request<{ publicKey: string }>('/api/notifications/vapid-public-key');
  return data.publicKey;
}

export async function subscribeWebPush(subscription: PushSubscription): Promise<void> {
  const key = subscription.getKey('p256dh');
  const auth = subscription.getKey('auth');
  const userAgent = navigator.userAgent;
  const deviceLabel = buildPushSubscriptionLabel(userAgent);
  await request('/api/notifications/subscribe', {
    method: 'POST',
    body: JSON.stringify({
      endpoint: subscription.endpoint,
      p256dh: key ? btoa(String.fromCharCode(...new Uint8Array(key))) : '',
      auth: auth ? btoa(String.fromCharCode(...new Uint8Array(auth))) : '',
      device_label: deviceLabel,
      user_agent: userAgent,
    }),
  });
}

export async function unsubscribeWebPush(subscription: PushSubscription): Promise<void> {
  const key = subscription.getKey('p256dh');
  const auth = subscription.getKey('auth');
  await request('/api/notifications/unsubscribe', {
    method: 'POST',
    body: JSON.stringify({
      endpoint: subscription.endpoint,
      p256dh: key ? btoa(String.fromCharCode(...new Uint8Array(key))) : '',
      auth: auth ? btoa(String.fromCharCode(...new Uint8Array(auth))) : '',
    }),
  });
}

export async function getPushSubscriptions(): Promise<{ count: number; subscriptions: PushSubscriptionInfo[] }> {
  return request('/api/notifications/subscriptions');
}

export async function deletePushSubscription(id: number): Promise<void> {
  await request(`/api/notifications/subscriptions/${id}`, { method: 'DELETE' });
}

function buildPushSubscriptionLabel(userAgent: string): string {
  const platform = getPlatformLabel(userAgent);
  const browser = getBrowserLabel(userAgent);
  return `${platform} ${browser}`.trim();
}

function getPlatformLabel(userAgent: string): string {
  const ua = userAgent.toLowerCase();
  if (ua.includes('android')) {
    const match = userAgent.match(/Android\s+([0-9._]+)/i);
    return match?.[1] ? `Android ${match[1].split('.')[0]}` : 'Android';
  }
  if (ua.includes('iphone')) return 'iPhone';
  if (ua.includes('ipad')) return 'iPad';
  if (ua.includes('windows')) return 'Windows';
  if (ua.includes('mac os x')) return 'Mac';
  if (ua.includes('linux')) return 'Linux';
  if (ua.includes('cros')) return 'ChromeOS';
  return 'Device';
}

function getBrowserLabel(userAgent: string): string {
  const ua = userAgent.toLowerCase();
  if (ua.includes('edg/')) return 'Edge';
  if (ua.includes('opr/') || ua.includes('opera')) return 'Opera';
  if (ua.includes('firefox/')) return 'Firefox';
  if (ua.includes('samsungbrowser/')) return 'Samsung Internet';
  if (ua.includes('crios/')) return 'Chrome';
  if (ua.includes('chrome/')) return 'Chrome';
  if (ua.includes('safari/')) return 'Safari';
  return 'Browser';
}

// Notification presets
export const getNotificationPresets = () => request<NotificationPreset[]>('/api/presets/notifications');
export const createNotificationPreset = (body: {
  name: string;
  provider: string;
  url?: string | null;
  topic?: string | null;
  token?: string | null;
  webhook_url?: string | null;
  push_subscription_ids?: number[];
}) =>
  request<NotificationPreset>('/api/presets/notifications', { method: 'POST', body: JSON.stringify(body) });
export const updateNotificationPreset = (id: number, body: {
  name: string;
  provider: string;
  url?: string | null;
  topic?: string | null;
  token?: string | null;
  webhook_url?: string | null;
  push_subscription_ids?: number[];
}) =>
  request<NotificationPreset>(`/api/presets/notifications/${id}`, { method: 'PUT', body: JSON.stringify(body) });
export const deleteNotificationPreset = (id: number) =>
  request<void>(`/api/presets/notifications/${id}`, { method: 'DELETE' });
export const testNotificationPreset = (id: number) =>
  request<{ ok: boolean; sent: string[]; errors: string[] }>(`/api/presets/notifications/${id}/test`, { method: 'POST' });
export const testPushSubscription = (id: number) =>
  request<{ ok: boolean; subscription_id: number }>(`/api/notifications/subscriptions/${id}/test`, { method: 'POST' });

const NOTIFICATION_PROVIDER_LABELS: Record<string, string> = {
  web: 'Web Push',
  ntfy: 'ntfy',
  gotify: 'Gotify',
  telegram: 'Telegram',
  homeassistant: 'Home Assistant',
  apprise: 'Apprise',
  discord: 'Discord',
  slack: 'Slack',
};

export function splitNotificationProviders(provider: string) {
  return provider.split(',').map((s) => s.trim()).filter(Boolean);
}

export function formatNotificationProvider(provider: string) {
  return NOTIFICATION_PROVIDER_LABELS[provider] ?? provider;
}

export function formatNotificationProviders(provider: string) {
  return splitNotificationProviders(provider).map(formatNotificationProvider).join(' · ');
}
