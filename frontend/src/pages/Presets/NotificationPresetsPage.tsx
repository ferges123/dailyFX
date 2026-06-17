import { useState, useEffect, useRef } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Bell,
  BellOff,
  Monitor,
  Plus,
  Trash2,
  Smartphone,
} from 'lucide-react';
import { InlineSpinner, ErrorBanner } from '../../components/ErrorUI';
import { EmptyState, InlineError, SectionCard } from '../../components/FormUI';
import {
  getNotificationPresets,
  createNotificationPreset,
  updateNotificationPreset,
  deleteNotificationPreset,
  testNotificationPreset,
  testPushSubscription,
  getVapidPublicKey,
  subscribeWebPush,
  unsubscribeWebPush,
  getPushSubscriptions,
  deletePushSubscription,
  splitNotificationProviders,
  type NotificationPreset,
} from '../../api/client';
import { Field } from '../../components/Field';
import { ConfirmModal } from '../../components/ConfirmModal';
import { logger } from '../../utils/logger';
import { PresetHeader, PresetFormActions } from './PresetHeader';

import { NotificationPresetCard } from './NotificationPresetsPage/NotificationPresetCard';
import { getPushDiagnostics } from './NotificationPresetsPage/utils';

export function NotificationPresetsTab() {
  const qc = useQueryClient();
  const presets = useQuery({
    queryKey: ['notification-presets'],
    queryFn: getNotificationPresets,
  });

  const [editing, setEditing] = useState<NotificationPreset | null>(null);
  const [isNew, setIsNew] = useState(false);
  const [form, setForm] = useState({
    name: '',
    channels: ['web'] as string[],
    url: '',
    topic: '',
    token: '',
    webhook_url: '',
    push_subscription_ids: [] as number[],
  });
  const [error, setError] = useState<string | null>(null);

  const CHANNELS = [
    'web',
    'ntfy',
    'gotify',
    'telegram',
    'homeassistant',
    'apprise',
    'discord',
    'slack',
  ] as const;
  const CHANNEL_LABELS: Record<(typeof CHANNELS)[number], string> = {
    web: 'Web Push',
    ntfy: 'ntfy',
    gotify: 'Gotify',
    telegram: 'Telegram',
    homeassistant: 'Home Assistant',
    apprise: 'Apprise',
    discord: 'Discord',
    slack: 'Slack',
  };

  const saveMutation = useMutation({
    mutationFn: () => {
      const body = {
        name: form.name,
        provider: form.channels.join(','),
        url: form.url || null,
        topic: form.topic || null,
        token: form.token || null,
        webhook_url: form.webhook_url || null,
        push_subscription_ids: form.push_subscription_ids,
      };
      return editing && !isNew
        ? updateNotificationPreset(editing.id, body)
        : createNotificationPreset(body);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['notification-presets'] });
      closeForm();
    },
    onError: (e: Error) => setError(e.message),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteNotificationPreset(id),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ['notification-presets'] }),
    onError: (e: Error) => setError(e.message),
  });

  const [testResult, setTestResult] = useState<{
    id: number;
    msg: string;
    ok: boolean;
  } | null>(null);
  const testMutation = useMutation({
    mutationFn: (id: number) => testNotificationPreset(id),
    onSuccess: (data, id) =>
      setTestResult({
        id,
        msg: data.sent.join(', ') || data.errors.join(', '),
        ok: data.ok,
      }),
    onError: (e: Error, id) => setTestResult({ id, msg: e.message, ok: false }),
  });
  const testingId = testMutation.isPending
    ? (testMutation.variables ?? null)
    : null;

  function openNew() {
    setForm({
      name: '',
      channels: ['web'],
      url: '',
      topic: '',
      token: '',
      webhook_url: '',
      push_subscription_ids: [],
    });
    setEditing(null);
    setIsNew(true);
    setError(null);
  }

  function openEdit(p: NotificationPreset) {
    const channels = splitNotificationProviders(p.provider);
    setForm({
      name: p.name,
      channels,
      url: p.url ?? '',
      topic: p.topic ?? '',
      token: '',
      webhook_url: p.webhook_url ?? '',
      push_subscription_ids: p.push_subscription_ids ?? [],
    });
    setEditing(p);
    setIsNew(false);
    setError(null);
  }

  function closeForm() {
    setEditing(null);
    setIsNew(false);
    setError(null);
  }

  function toggleChannel(ch: string) {
    setForm((f) => ({
      ...f,
      channels: f.channels.includes(ch)
        ? f.channels.filter((c) => c !== ch)
        : [...f.channels, ch],
    }));
  }

  const showForm = isNew || editing !== null;
  const hasWeb = form.channels.includes('web');
  const hasNtfy = form.channels.includes('ntfy');
  const hasGotify = form.channels.includes('gotify');
  const hasTelegram = form.channels.includes('telegram');
  const hasHomeAssistant = form.channels.includes('homeassistant');
  const hasApprise = form.channels.includes('apprise');
  const hasDiscord = form.channels.includes('discord');
  const hasSlack = form.channels.includes('slack');
  const needsUrl = hasNtfy || hasGotify || hasHomeAssistant || hasApprise;
  const validationIssues: string[] = [];
  if (!form.name.trim()) validationIssues.push('Preset name is required.');
  if (form.channels.length === 0)
    validationIssues.push('Select at least one channel.');
  if (needsUrl && !form.url.trim())
    validationIssues.push(
      'A server URL is required for the selected channels.',
    );
  if (hasNtfy && !form.topic.trim())
    validationIssues.push('ntfy topic is required.');
  if (hasTelegram && !form.topic.trim())
    validationIssues.push('Telegram chat ID is required.');
  if (hasHomeAssistant && !form.token.trim() && !editing?.token_masked)
    validationIssues.push('Home Assistant access token is required.');
  if (hasDiscord && !form.webhook_url.trim())
    validationIssues.push('Discord Webhook URL is required.');
  if (hasSlack && !form.webhook_url.trim())
    validationIssues.push('Slack Webhook URL is required.');
  const canSave = validationIssues.length === 0;

  // Web Push state
  const subscriptions = useQuery({
    queryKey: ['push-subscriptions'],
    queryFn: getPushSubscriptions,
    enabled: hasWeb,
  });
  const deleteSubMutation = useMutation({
    mutationFn: deletePushSubscription,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['push-subscriptions'] }),
  });
  const [pushSub, setPushSub] = useState<PushSubscription | null>(null);
  const [pushStatus, setPushStatus] = useState<
    'idle' | 'pending' | 'subscribed' | 'error'
  >('idle');
  const [pushError, setPushError] = useState<string | null>(null);
  const formPanelRef = useRef<HTMLDivElement | null>(null);
  const [confirmConfig, setConfirmConfig] = useState<{
    isOpen: boolean;
    title: string;
    description: string;
    confirmLabel?: string;
    onConfirm: () => void;
    variant?: 'danger' | 'warning' | 'info';
  } | null>(null);

  const webPushSupport = {
    hasNotification: typeof window !== 'undefined' && 'Notification' in window,
    hasServiceWorker: typeof navigator !== 'undefined' && 'serviceWorker' in navigator,
    hasPushManager: typeof window !== 'undefined' && 'PushManager' in window,
    isSecureContext: typeof window !== 'undefined' && window.isSecureContext,
  };

  const [notificationPermission, setNotificationPermission] = useState<string>(
    webPushSupport.hasNotification ? Notification.permission : 'unsupported'
  );

  const requestNotificationPermission = async () => {
    if (!webPushSupport.hasNotification) return;
    try {
      const permission = await Notification.requestPermission();
      setNotificationPermission(permission);
    } catch (err) {
      logger.error('Failed to request permission', err);
    }
  };

  const canSubscribeToPush =
    webPushSupport.hasNotification &&
    webPushSupport.hasServiceWorker &&
    webPushSupport.hasPushManager &&
    webPushSupport.isSecureContext &&
    notificationPermission !== 'denied';

  const { diagnosticsText, diagnosticsColor, showPermissionButton } = getPushDiagnostics(
    webPushSupport,
    notificationPermission
  );

  const [testSubResult, setTestSubResult] = useState<{ id: number; ok: boolean; msg: string } | null>(null);

  const testSubMutation = useMutation({
    mutationFn: (subId: number) => testPushSubscription(subId),
    onSuccess: (data, subId) => {
      setTestSubResult({ id: subId, ok: true, msg: 'Test sent' });
      setTimeout(() => setTestSubResult(null), 5000);
    },
    onError: (e: Error, subId) => {
      setTestSubResult({ id: subId, ok: false, msg: `Error: ${e.message}` });
      setTimeout(() => setTestSubResult(null), 5000);
    },
  });

  function togglePushSubscriptionTarget(id: number, checked: boolean) {
    setForm((prev) => {
      const current = prev.push_subscription_ids ?? [];
      return {
        ...prev,
        push_subscription_ids: checked
          ? Array.from(new Set([...current, id]))
          : current.filter((item) => item !== id),
      };
    });
  }

  useEffect(() => {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) return;
    navigator.serviceWorker.ready.then((reg) => {
      reg.pushManager.getSubscription().then((sub) => {
        if (sub) {
          setPushSub(sub);
          setPushStatus('subscribed');
        }
      });
    });
  }, []);

  async function handlePushToggle() {
    if (pushStatus === 'pending') return;
    setPushStatus('pending');
    setPushError(null);
    try {
      const reg = await navigator.serviceWorker.ready;
      if (pushSub) {
        await unsubscribeWebPush(pushSub);
        await pushSub.unsubscribe();
        setPushSub(null);
        setPushStatus('idle');
        qc.invalidateQueries({ queryKey: ['push-subscriptions'] });
      } else {
        const vapidKey = await getVapidPublicKey();
        const sub = await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: vapidKey,
        });
        await subscribeWebPush(sub);
        setPushSub(sub);
        setPushStatus('subscribed');
        qc.invalidateQueries({ queryKey: ['push-subscriptions'] });
      }
    } catch (err) {
      setPushStatus('error');
      let errMsg = 'An unknown error occurred.';
      if (err instanceof Error) {
        errMsg = err.message;
      } else if (typeof err === 'string') {
        errMsg = err;
      }

      if (errMsg.includes('Permission denied') || errMsg.includes('permission')) {
        errMsg = 'Permission denied. Please enable notifications for this site in your browser settings.';
      } else if (errMsg.includes('is not secure') || (typeof window !== 'undefined' && !window.isSecureContext)) {
        errMsg = 'Web Push requires a secure context (HTTPS) or a local localhost context.';
      } else if (errMsg.includes('VAPID') || errMsg.includes('applicationServerKey')) {
        errMsg = 'Invalid or missing VAPID public key. Please check your server configuration.';
      }

      setPushError(errMsg);
    }
  }

  const isLoading = presets.isLoading && !presets.data;
  const isError = presets.isError && !presets.data;

  useEffect(() => {
    if (!showForm) return;
    formPanelRef.current?.scrollIntoView?.({
      behavior: 'smooth',
      block: 'start',
    });
  }, [showForm, isNew, editing?.id]);

  if (isLoading) {
    return <InlineSpinner />;
  }

  if (isError) {
    return (
      <ErrorBanner
        title="Could not load notification presets"
        error={presets.error}
        onRetry={() => presets.refetch()}
      />
    );
  }

  return (
    <div className="grid gap-3">
      <PresetHeader count={presets.data?.length ?? 0} onCreate={openNew} />

      {error && (
        <InlineError
          title="Could not save notification preset"
          message={error}
        />
      )}

      {showForm && (
        <div ref={formPanelRef} className="app-panel grid gap-4 p-4">
          <div className="grid gap-0.5 md:gap-1">
            <div className="text-sm font-semibold text-stone-900">
              {isNew ? 'New notification preset' : `Editing: ${editing?.name}`}
            </div>
            <div className="text-sm text-stone-500">
              Channels are stored as a single preset, but each one keeps its own
              connection details.
            </div>
          </div>

          {validationIssues.length > 0 && (
            <InlineError
              title="Fix the highlighted fields"
              message={validationIssues.join(' ')}
            />
          )}

          <SectionCard
            title="Basics"
            description="Name the preset and choose where notifications go."
          >
            <div className="grid gap-3">
              <Field
                label="Name"
                required
                value={form.name}
                maxLength={255}
                onChange={(e) =>
                  setForm((f) => ({ ...f, name: e.target.value }))
                }
              />
              <div className="grid gap-2">
                <div className="text-sm font-semibold text-stone-800">
                  Channels <span className="text-rose-500">*</span>
                </div>
                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {CHANNELS.map((ch) => (
                    <label
                      key={ch}
                      className={`flex items-start gap-2 rounded-2xl border px-3 py-2 text-sm transition-colors ${form.channels.includes(ch) ? 'border-emerald-200 bg-emerald-50/50 text-emerald-900' : 'border-stone-200 bg-white text-stone-700'}`}
                    >
                      <input
                        type="checkbox"
                        checked={form.channels.includes(ch)}
                        onChange={() => toggleChannel(ch)}
                        className="mt-0.5 h-4 w-4 accent-emerald-700"
                      />
                      <div className="grid gap-0.5">
                        <span className="font-medium">
                          {CHANNEL_LABELS[ch]}
                        </span>
                        <span className="text-xs text-stone-500">
                          {ch === 'web'
                            ? 'Browser push notifications.'
                            : ch === 'telegram'
                              ? 'Telegram bot delivery.'
                              : 'External notification provider.'}
                        </span>
                      </div>
                    </label>
                  ))}
                </div>
              </div>
            </div>
          </SectionCard>

          {hasWeb && (
            <SectionCard
              title="Web Push"
              description="Manage browser subscriptions and device targets for this preset."
            >
              <div className="grid gap-4">
                {/* Diagnostics Status Badge */}
                <div className="flex flex-wrap items-center gap-2">
                   <div className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${diagnosticsColor}`}>
                    <span className="h-1.5 w-1.5 rounded-full bg-current" />
                    Status: {diagnosticsText}
                  </div>
                  {showPermissionButton && (
                    <button
                      type="button"
                      onClick={requestNotificationPermission}
                      className="app-button-secondary h-6 px-2.5 text-[10px] font-semibold"
                    >
                      Grant permission
                    </button>
                  )}
                </div>

                {/* Local Browser Subscription Controls */}
                <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
                  <button
                    type="button"
                    onClick={handlePushToggle}
                    disabled={
                      pushStatus === 'pending' || !canSubscribeToPush
                    }
                    className="app-button-secondary h-8 w-full px-3 text-xs disabled:opacity-50 sm:w-auto"
                  >
                    {pushStatus === 'subscribed' ? (
                      <BellOff size={12} />
                    ) : (
                      <Bell size={12} />
                    )}
                    {pushStatus === 'subscribed'
                      ? 'Unsubscribe this browser'
                      : pushStatus === 'pending'
                        ? 'Wait…'
                        : 'Subscribe this browser'}
                  </button>
                  {pushStatus === 'subscribed' && (
                    <span className="text-xs font-medium text-emerald-700">
                      Subscribed
                    </span>
                  )}
                </div>

                {pushError && (
                  <div className="rounded-xl bg-rose-50 border border-rose-200 p-2.5 text-xs text-rose-800">
                    <strong>Failed to update subscription:</strong> {pushError}
                  </div>
                )}

                {/* Warn if no device is targeted */}
                {(form.push_subscription_ids ?? []).length === 0 && (
                  <div className="rounded-xl bg-amber-50 border border-amber-200 p-2.5 text-xs text-amber-800">
                    This preset will not send Web Push notifications until you select at least one device.
                  </div>
                )}

                {/* Subscriptions List with Checkboxes */}
                {subscriptions.data &&
                  subscriptions.data.subscriptions.length > 0 ? (
                    <div className="grid gap-2">
                      <div className="text-xs font-semibold text-stone-500">
                        Select devices to target with this preset:
                      </div>
                      {subscriptions.data.subscriptions.map((sub) => {
                        const label =
                          sub.device_label ||
                          sub.user_agent ||
                          'Unknown browser';
                        const isMobile = /mobile|android|iphone|ipad/i.test(
                          label,
                        );
                        const isChecked = (form.push_subscription_ids ?? []).includes(sub.id);
                        const isTesting = testSubMutation.isPending && testSubMutation.variables === sub.id;
                        const testStatus = testSubResult && testSubResult.id === sub.id ? testSubResult : null;

                        return (
                          <div
                            key={sub.id}
                            className="flex items-center gap-3 rounded-2xl border border-stone-200 bg-stone-50 px-3 py-2 hover:bg-stone-100 transition-colors"
                          >
                            <input
                              type="checkbox"
                              id={`push-sub-${sub.id}`}
                              checked={isChecked}
                              onChange={(e) => togglePushSubscriptionTarget(sub.id, e.target.checked)}
                              className="h-4 w-4 rounded border-stone-300 text-stone-900 focus:ring-stone-900"
                            />
                            <label
                              htmlFor={`push-sub-${sub.id}`}
                              className="flex flex-1 items-center gap-2 cursor-pointer"
                            >
                              {isMobile ? (
                                <Smartphone
                                  size={14}
                                  className="shrink-0 text-stone-400"
                                />
                              ) : (
                                <Monitor
                                  size={14}
                                  className="shrink-0 text-stone-400"
                                />
                              )}
                              <span className="flex-1 truncate text-xs text-stone-700 font-medium">
                                {label}
                              </span>
                            </label>

                            {testStatus && (
                              <span className={`text-[10px] font-medium transition-opacity duration-300 ${testStatus.ok ? 'text-emerald-600' : 'text-rose-600'}`}>
                                {testStatus.msg}
                              </span>
                            )}

                            <button
                              type="button"
                              onClick={() => testSubMutation.mutate(sub.id)}
                              disabled={isTesting}
                              className="shrink-0 text-[10px] font-semibold text-stone-600 hover:text-stone-900 bg-stone-200 hover:bg-stone-300 px-2.5 py-0.5 rounded-full transition-colors disabled:opacity-50"
                            >
                              {isTesting ? 'Testing...' : 'Test'}
                            </button>

                            <button
                              type="button"
                              onClick={() => {
                                setConfirmConfig({
                                  isOpen: true,
                                  title: 'Delete Subscription Globally',
                                  description: 'Deleting this subscription will remove it from all preset targets. Continue?',
                                  confirmLabel: 'Delete',
                                  variant: 'danger',
                                  onConfirm: () => {
                                    deleteSubMutation.mutate(sub.id);
                                    setForm((f) => ({
                                      ...f,
                                      push_subscription_ids: (f.push_subscription_ids ?? []).filter((id) => id !== sub.id),
                                    }));
                                  },
                                });
                              }}
                              disabled={deleteSubMutation.isPending}
                              className="shrink-0 text-stone-400 hover:text-rose-600 disabled:opacity-50 transition-colors"
                              title="Delete globally"
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="text-xs text-stone-500 italic">
                      No registered devices found. Register this browser above.
                    </div>
                  )}
              </div>
            </SectionCard>
          )}

          <SectionCard
            title="Provider settings"
            description="Fill in the fields required by the selected channels."
          >
            <div className="grid gap-3">
              {needsUrl && (
                <Field
                  label={
                    hasApprise ? 'Apprise endpoint URL(s)' : 'Endpoint URL'
                  }
                  required
                  type={hasApprise ? 'text' : 'url'}
                  maxLength={2048}
                  value={form.url}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, url: e.target.value }))
                  }
                  placeholder={
                    hasApprise
                      ? 'tgram://bot_token/chat_id, mailto://user:pass@gmail.com'
                      : hasHomeAssistant
                        ? 'http://homeassistant.local:8123'
                        : 'https://ntfy.sh'
                  }
                  hint={
                    hasApprise
                      ? 'Required for Apprise.'
                      : hasHomeAssistant
                        ? 'Use the Home Assistant base URL, including port if needed.'
                        : hasNtfy
                          ? 'Use your ntfy server URL, such as https://ntfy.sh or your self-hosted instance.'
                          : 'Required for the selected provider(s).'
                  }
                />
              )}
              {hasNtfy && (
                <Field
                  label="Topic"
                  required
                  value={form.topic}
                  maxLength={255}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, topic: e.target.value }))
                  }
                  hint="The ntfy topic name. Add a token only if the topic is protected."
                />
              )}
              {hasTelegram && (
                <Field
                  label="Telegram Chat ID"
                  required
                  value={form.topic}
                  maxLength={255}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, topic: e.target.value }))
                  }
                  placeholder="-10012345678 or @channelname"
                  hint="Use the chat ID for a private chat or group, or an @channelname for a channel."
                />
              )}
              {hasHomeAssistant && (
                <Field
                  label="Notify service name"
                  optional
                  value={form.topic}
                  maxLength={255}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, topic: e.target.value }))
                  }
                  placeholder="e.g. notify or mobile_app_phone"
                  hint="Leave blank to use the default notify service. Use persistent_notification for a sidebar notice."
                />
              )}
              {(hasNtfy || hasGotify || hasTelegram || hasHomeAssistant) && (
                <Field
                  label={
                    hasTelegram
                      ? 'Telegram Bot Token'
                      : hasHomeAssistant
                        ? 'Home Assistant Access Token (LLAT)'
                        : 'Token'
                  }
                  required={hasTelegram || hasHomeAssistant}
                  optional={!hasTelegram && !hasHomeAssistant}
                  type="password"
                  value={form.token}
                  placeholder={editing?.token_masked ?? ''}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, token: e.target.value }))
                  }
                />
              )}
              <Field
                label="Webhook URL"
                required={hasDiscord || hasSlack}
                optional={!hasDiscord && !hasSlack}
                type="url"
                maxLength={2048}
                value={form.webhook_url}
                onChange={(e) =>
                  setForm((f) => ({ ...f, webhook_url: e.target.value }))
                }
                placeholder={
                  hasDiscord
                    ? 'https://discord.com/api/webhooks/...'
                    : hasSlack
                      ? 'https://hooks.slack.com/services/...'
                      : 'https://example.com/webhook'
                }
              />
              {(hasNtfy ||
                hasTelegram ||
                hasHomeAssistant ||
                hasDiscord ||
                hasSlack) && (
                <div className="rounded-2xl border border-stone-200 bg-stone-50/80 p-3 text-xs text-stone-600">
                  <div className="mb-1.5 text-[10px] font-bold uppercase tracking-[0.18em] text-stone-500">
                    Provider tips
                  </div>
                  <div className="grid gap-1.5 leading-relaxed">
                    {hasNtfy && (
                      <p>
                        <span className="font-semibold text-stone-800">
                          ntfy:
                        </span>{' '}
                        messages include a click target and image attachment
                        when your DailyFX external URL is configured, so the
                        phone notification can open the review page and preview
                        the image.
                      </p>
                    )}
                    {hasTelegram && (
                      <p>
                        <span className="font-semibold text-stone-800">
                          Telegram:
                        </span>{' '}
                        the bot sends the image directly with Accept / Reject
                        buttons, so the chat ID and bot token are the only
                        required values.
                      </p>
                    )}
                    {hasHomeAssistant && (
                      <p>
                        <span className="font-semibold text-stone-800">
                          Home Assistant:
                        </span>{' '}
                        use a long-lived access token and a notify service such
                        as{' '}
                        <code className="rounded-sm bg-white px-1 py-0.5 text-[11px] text-stone-700">
                          mobile_app_phone
                        </code>{' '}
                        or{' '}
                        <code className="rounded-sm bg-white px-1 py-0.5 text-[11px] text-stone-700">
                          persistent_notification
                        </code>
                        .
                      </p>
                    )}
                    {hasDiscord && (
                      <p>
                        <span className="font-semibold text-stone-800">
                          Discord:
                        </span>{' '}
                        messages are delivered directly to the configured
                        channel webhook with image preview embeds when your
                        DailyFX external URL is configured.
                      </p>
                    )}
                    {hasSlack && (
                      <p>
                        <span className="font-semibold text-stone-800">
                          Slack:
                        </span>{' '}
                        messages are delivered directly to the configured
                        channel webhook using Slack's rich block kit, including
                        image preview and review action buttons.
                      </p>
                    )}
                  </div>
                </div>
              )}
            </div>
          </SectionCard>

          <PresetFormActions
            onSave={() => saveMutation.mutate()}
            onCancel={closeForm}
            canSave={canSave}
            pending={saveMutation.isPending}
          />
        </div>
      )}

      <div aria-label="Notification presets list" className="grid gap-2 lg:grid-cols-2">
        {presets.data?.map((p) => (
          <NotificationPresetCard
            key={p.id}
            preset={p}
            testResult={testResult}
            testingId={testingId}
            onTest={(id) => testMutation.mutate(id)}
            onEdit={openEdit}
            onDelete={(id, name) => {
              setConfirmConfig({
                isOpen: true,
                title: 'Delete Notification Preset',
                description: `Are you sure you want to delete "${name}"?`,
                confirmLabel: 'Delete',
                variant: 'danger',
                onConfirm: () => deleteMutation.mutate(id),
              });
            }}
          />
        ))}
        {presets.data?.length === 0 && (
          <div className="xl:col-span-2">
            <EmptyState
              title="No notification presets yet"
              description="Create a notification preset to wire one or more delivery channels into schedules."
              action={
                <button
                  type="button"
                  onClick={openNew}
                  className="app-button-primary px-3 py-1.5 text-sm"
                >
                  <Plus size={14} /> New preset
                </button>
              }
            />
          </div>
        )}
      </div>

      {confirmConfig && (
        <ConfirmModal
          isOpen={confirmConfig.isOpen}
          title={confirmConfig.title}
          description={confirmConfig.description}
          confirmLabel={confirmConfig.confirmLabel}
          variant={confirmConfig.variant}
          onConfirm={() => {
            confirmConfig.onConfirm();
            setConfirmConfig(null);
          }}
          onClose={() => setConfirmConfig(null)}
        />
      )}
    </div>
  );
}

export function NotificationPresetsPage() {
  return (
    <section className="grid gap-4">
      <div className="app-panel grid gap-4 p-4">
        <NotificationPresetsTab />
      </div>
    </section>
  );
}
