import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Save, Trash2, Database } from 'lucide-react';
import { type FormEvent, useEffect, useState } from 'react';
import { InlineSpinner, ErrorBanner } from '../components/ErrorUI';
import {
  getSettings,
  updateSettings,
  clearHistoryByStatus,
  clearGenerationCache,
  getDebugLog,
  getRetentionPreview,
  runRetention,
  type SettingsUpdate,
} from '../api/client';
import { APP_VERSION } from '../version';
import { ConfirmDeleteModal } from './History/ConfirmDeleteModal';

import { RuntimeStatusSection } from './Settings/RuntimeStatusSection';
import { ConnectionTestsSection } from './Settings/ConnectionTestsSection';
import { AIProviderSettingsSection } from './Settings/AIProviderSettingsSection';
import {
  validateSettingsForm,
  normalizeSettingsPayload,
  type SettingsFieldErrors,
} from './Settings/settingsValidation';

export {
  OPENAI_VISION_MODELS,
  GEMINI_VISION_MODELS,
  XIAOMI_VISION_MODELS,
  getVisionModelOptions,
  OPENAI_IMAGE_MODELS,
  GEMINI_IMAGE_MODELS,
  getImageModelOptions,
} from './Settings/AIProviderSettingsSection';

const defaults: SettingsUpdate = {
  immich_url: '',
  local_ai_base_url: '',
  ai_vision_hourly_limit: 30,
  ai_image_hourly_limit: 10,
  debug_mode: false,
  favorite_albums_json: null,
  ai_custom_prompt: null,
  retention_enabled: true,
  retention_rejected_files_days: 7,
  retention_rejected_metadata_days: 90,
  retention_failed_files_days: 7,
  retention_failed_metadata_days: 90,
  retention_uploaded_files_days: 30,
  retention_uploaded_metadata_days: 30,
  retention_task_days: 30,
  retention_audit_days: 180,
  retention_backup_count: 7,
  immich_api_key: '',
  openai_api_key: '',
  gemini_api_key: '',
  openrouter_api_key: '',
  byteplus_api_key: '',
  xiaomi_api_key: '',
  local_ai_api_key: '',
};

type TestState = {
  status: 'idle' | 'success' | 'error';
  message: string | null;
};

export function SettingsPage() {
  const queryClient = useQueryClient();
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState<
    'rejected' | 'failed' | 'pending' | 'accepted' | 'running' | 'all' | null
  >(null);

  const clearHistoryMutation = useMutation({
    mutationFn: (
      status: 'rejected' | 'failed' | 'pending' | 'accepted' | 'running',
    ) => clearHistoryByStatus(status),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['generation-history'] });
      setConfirmDeleteOpen(null);
    },
  });

  const clearAllMutation = useMutation({
    mutationFn: clearGenerationCache,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['generation-history'] });
      setConfirmDeleteOpen(null);
    },
  });
  const settings = useQuery({
    queryKey: ['settings'],
    queryFn: getSettings,
    refetchOnWindowFocus: false,
  });

  const mutation = useMutation({
    mutationFn: updateSettings,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['settings'] }),
  });

  const [form, setForm] = useState<SettingsUpdate>(defaults);
  const [saved, setSaved] = useState<TestState>({
    status: 'idle',
    message: null,
  });
  const [validationErrors, setValidationErrors] = useState<SettingsFieldErrors>(
    {},
  );
  const [logLoading, setLogLoading] = useState(false);
  const [retentionMessage, setRetentionMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!settings.data) return;
    setForm((current) => ({
      ...current,
      immich_url: settings.data.immich_url ?? '',
      local_ai_base_url: settings.data.local_ai_base_url ?? '',
      ai_vision_hourly_limit: settings.data.ai_vision_hourly_limit,
      ai_image_hourly_limit: settings.data.ai_image_hourly_limit,
      debug_mode: settings.data.debug_mode,
      favorite_albums_json: settings.data.favorite_albums_json,
      ai_custom_prompt: settings.data.ai_custom_prompt,
      retention_enabled: settings.data.retention_enabled,
      retention_rejected_files_days: settings.data.retention_rejected_files_days,
      retention_rejected_metadata_days: settings.data.retention_rejected_metadata_days,
      retention_failed_files_days: settings.data.retention_failed_files_days,
      retention_failed_metadata_days: settings.data.retention_failed_metadata_days,
      retention_uploaded_files_days: settings.data.retention_uploaded_files_days,
      retention_uploaded_metadata_days: settings.data.retention_uploaded_metadata_days,
      retention_task_days: settings.data.retention_task_days,
      retention_audit_days: settings.data.retention_audit_days,
      retention_backup_count: settings.data.retention_backup_count,
    }));
  }, [settings.data]);

  const hasSettings = !!settings.data;
  const isInitialLoad = settings.isLoading && !hasSettings;
  const showInlineLoadError = settings.isError && hasSettings;

  if (isInitialLoad) {
    return <InlineSpinner />;
  }

  if (settings.isError && !hasSettings) {
    return (
      <ErrorBanner
        error={settings.error as Error | string | null}
        title="Could not load settings"
        onRetry={() => settings.refetch()}
      />
    );
  }

  function setValue<K extends keyof SettingsUpdate>(
    key: K,
    value: SettingsUpdate[K],
  ) {
    setForm((current) => ({ ...current, [key]: value }));
    setValidationErrors({});
    setSaved({ status: 'idle', message: null });
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaved({ status: 'idle', message: null });
    const nextValidationErrors = validateSettingsForm(form);
    setValidationErrors(nextValidationErrors);
    if (Object.keys(nextValidationErrors).length > 0) {
      setSaved({
        status: 'error',
        message: 'Fix the highlighted settings before saving.',
      });
      return;
    }

    mutation.mutate(normalizeSettingsPayload(form), {
      onSuccess: () => {
        setSaved({ status: 'success', message: 'Saved' });
        setValidationErrors({});
      },
      onError: () => setSaved({ status: 'error', message: 'Save failed' }),
    });
  }

  const handleViewLog = async () => {
    if (logLoading) return;
    setLogLoading(true);
    try {
      const text = await getDebugLog();
      const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      window.open(url, '_blank');
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (err) {
      console.error('Failed to load debug log:', err);
      alert(
        'Failed to load debug log. Check if debug mode is active and logs exist.',
      );
    } finally {
      setLogLoading(false);
    }
  };

  const handleRetentionPreview = async () => {
    try {
      const result = await getRetentionPreview();
      setRetentionMessage(`Preview: ${result.files} files, ${result.metadata} metadata records, ${Math.round(result.bytes / 1024)} KiB.`);
    } catch {
      setRetentionMessage('Retention preview failed.');
    }
  };

  const handleRetentionRun = async () => {
    if (!window.confirm('Run retention cleanup now?')) return;
    try {
      const result = await runRetention(false);
      setRetentionMessage(`Cleanup complete: ${result.files} files scheduled, ${result.metadata} metadata records.`);
    } catch {
      setRetentionMessage('Retention cleanup failed.');
    }
  };

  return (
    <form onSubmit={submit} className="grid gap-2.5 md:gap-3">
      {showInlineLoadError && (
        <ErrorBanner
          error={settings.error as Error | string | null}
          title="Settings refresh failed"
          onRetry={() => settings.refetch()}
        />
      )}
      {Object.keys(validationErrors).length > 0 && (
        <div className="app-panel p-3 md:p-4">
          <div className="grid gap-0.5 md:gap-1">
            <div className="text-sm font-semibold text-rose-900">
              Fix the highlighted settings
            </div>
            <div className="text-sm text-rose-800">
              {Object.values(validationErrors).join(' ')}
            </div>
          </div>
        </div>
      )}

      {/* Runtime Status */}
      <RuntimeStatusSection />

      {/* Immich Connection */}
      <ConnectionTestsSection
        immichUrl={form.immich_url ?? ''}
        immichApiKey={(form.immich_api_key as string) ?? ''}
        immichApiKeyMasked={settings.data?.immich_api_key_masked ?? ''}
        onChange={setValue}
        validationError={validationErrors.immich_url}
      />

      {/* AI Budget Limits & AI API Keys */}
      <AIProviderSettingsSection
        form={form}
        settingsData={settings.data}
        onChange={setValue}
        validationErrors={validationErrors}
      />

      {/* Debug Mode */}
      <div className="app-panel p-3 md:p-4">
        <label className="flex items-start gap-1.5 md:items-center md:gap-2 text-xs cursor-pointer">
          <input
            type="checkbox"
            checked={form.debug_mode}
            onChange={(e) => setValue('debug_mode', e.target.checked)}
            className="rounded-sm border-stone-300"
          />
          <div>
            <span className="font-medium">Debug mode</span>
            <span className="text-stone-600">
              {' · '}Logs to /data/logs/debug_*.log
              {form.debug_mode && (
                <>
                  {' · '}
                  <button
                    type="button"
                    onClick={handleViewLog}
                    disabled={logLoading}
                    className="text-emerald-700 hover:underline cursor-pointer bg-transparent border-0 p-0 font-inherit disabled:opacity-50"
                  >
                    {logLoading ? 'Loading log...' : 'View log'}
                  </button>
                </>
              )}
            </span>
          </div>
        </label>
      </div>

      {/* Data Retention */}
      <div className="app-panel p-3 md:p-4">
        <div className="flex items-center gap-2 mb-3">
          <Database size={16} className="text-emerald-700" />
          <h3 className="text-xs font-bold uppercase tracking-[0.22em] text-stone-700">Data retention</h3>
        </div>
        <label className="flex items-center gap-2 text-xs font-medium">
          <input type="checkbox" checked={form.retention_enabled} onChange={(e) => setValue('retention_enabled', e.target.checked)} />
          Enable automatic cleanup
        </label>
        <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-4">
          {([
            ['retention_rejected_files_days', 'Rejected files'],
            ['retention_rejected_metadata_days', 'Rejected metadata'],
            ['retention_failed_files_days', 'Failed files'],
            ['retention_failed_metadata_days', 'Failed metadata'],
            ['retention_uploaded_files_days', 'Uploaded files'],
            ['retention_uploaded_metadata_days', 'Uploaded metadata'],
            ['retention_task_days', 'Task metadata'],
            ['retention_audit_days', 'Audit log'],
            ['retention_backup_count', 'DB backups'],
          ] as const).map(([key, label]) => (
            <label key={key} className="text-xs text-stone-600">
              {label} ({key === 'retention_backup_count' ? 'copies' : 'days'})
              <input type="number" min={1} value={form[key] ?? ''} onChange={(e) => setValue(key, e.target.value === '' ? null : Number(e.target.value))} className="mt-1 h-8 w-full rounded-lg border border-stone-200 px-2" />
            </label>
          ))}
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button type="button" onClick={handleRetentionPreview} className="inline-flex h-8 items-center rounded-lg border border-stone-300 bg-white px-2.5 text-xs font-semibold text-stone-700 hover:bg-stone-50">Preview cleanup</button>
          <button type="button" onClick={handleRetentionRun} disabled={!form.retention_enabled} className="inline-flex h-8 items-center rounded-lg border border-rose-300 bg-white px-2.5 text-xs font-semibold text-rose-700 hover:bg-rose-50 disabled:opacity-50">Run cleanup now</button>
          {retentionMessage && <span className="text-xs text-stone-500">{retentionMessage}</span>}
        </div>
      </div>

      {/* Danger Zone */}
      <div className="app-panel border border-red-200/50 bg-red-50/10 p-3 md:p-4 rounded-2xl">
        <h3 className="text-xs font-bold uppercase tracking-[0.22em] text-red-800 mb-2">
          Danger Zone
        </h3>
        <p className="text-xs text-stone-500 mb-4 leading-relaxed">
          The following actions will permanently delete history records and
          their associated files from disk. These actions cannot be undone.
        </p>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setConfirmDeleteOpen('rejected')}
            className="inline-flex h-8 items-center rounded-lg border border-amber-300 bg-white px-2.5 text-xs font-semibold text-amber-700 hover:bg-amber-50 transition active:scale-98 cursor-pointer"
          >
            <Trash2 size={12} className="mr-1.5" />
            Delete Rejected
          </button>
          <button
            type="button"
            onClick={() => setConfirmDeleteOpen('failed')}
            className="inline-flex h-8 items-center rounded-lg border border-red-300 bg-white px-2.5 text-xs font-semibold text-red-700 hover:bg-red-50 transition active:scale-98 cursor-pointer"
          >
            <Trash2 size={12} className="mr-1.5" />
            Delete Failed
          </button>
          <button
            type="button"
            onClick={() => setConfirmDeleteOpen('pending')}
            className="inline-flex h-8 items-center rounded-lg border border-amber-300 bg-white px-2.5 text-xs font-semibold text-amber-700 hover:bg-amber-50 transition active:scale-98 cursor-pointer"
          >
            <Trash2 size={12} className="mr-1.5" />
            Delete Pending
          </button>
          <button
            type="button"
            onClick={() => setConfirmDeleteOpen('running')}
            className="inline-flex h-8 items-center rounded-lg border border-amber-300 bg-white px-2.5 text-xs font-semibold text-amber-700 hover:bg-amber-50 transition active:scale-98 cursor-pointer"
          >
            <Trash2 size={12} className="mr-1.5" />
            Delete Running
          </button>
          <button
            type="button"
            onClick={() => setConfirmDeleteOpen('accepted')}
            className="inline-flex h-8 items-center rounded-lg border border-red-300 bg-white px-2.5 text-xs font-semibold text-red-700 hover:bg-red-50 transition active:scale-98 cursor-pointer"
          >
            <Trash2 size={12} className="mr-1.5" />
            Delete Accepted
          </button>
          <button
            type="button"
            onClick={() => setConfirmDeleteOpen('all')}
            className="inline-flex h-8 items-center rounded-lg bg-red-650 hover:bg-red-700 text-white px-2.5 text-xs font-bold transition active:scale-98 cursor-pointer"
          >
            <Trash2 size={12} className="mr-1.5" />
            Clear All History
          </button>
        </div>
      </div>

      <ConfirmDeleteModal
        isOpen={confirmDeleteOpen !== null}
        onClose={() => setConfirmDeleteOpen(null)}
        onConfirm={() => {
          if (confirmDeleteOpen === 'all') {
            clearAllMutation.mutate();
          } else if (confirmDeleteOpen !== null) {
            clearHistoryMutation.mutate(confirmDeleteOpen);
          }
        }}
        variant={confirmDeleteOpen ?? 'rejected'}
        isPending={clearAllMutation.isPending || clearHistoryMutation.isPending}
      />

      {/* Save */}
      <div className="sticky bottom-20 z-10 flex flex-col gap-2 rounded-2xl border border-stone-200/70 bg-[rgba(248,246,239,0.96)] p-2 shadow-sm sm:flex-row sm:items-center md:static md:border-0 md:bg-transparent md:p-0 md:shadow-none">
        <button
          type="submit"
          className="app-button-primary h-9 w-full justify-center px-4 disabled:opacity-60 disabled:hover:bg-emerald-700 sm:w-auto"
          disabled={mutation.isPending}
        >
          <Save size={14} />
          Save
        </button>
        <div
          aria-live="polite"
          className="flex items-center"
          data-testid="save-status-container"
        >
          {saved.status === 'success' && (
            <span className="text-xs text-emerald-700">{saved.message}</span>
          )}
          {saved.status === 'error' && (
            <span className="text-xs text-red-700">{saved.message}</span>
          )}
        </div>
      </div>

      {/* Version Footer for Mobile */}
      <div className="mt-6 border-t border-stone-200/50 pt-4 text-center text-[10px] text-stone-400 md:hidden">
        DailyFX {APP_VERSION} · PolyForm Noncommercial License 1.0.0
      </div>
    </form>
  );
}
