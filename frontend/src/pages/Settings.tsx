import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Save } from 'lucide-react';
import {
  type FormEvent,
  useEffect,
  useState,
} from 'react';
import { InlineSpinner, ErrorBanner } from '../components/ErrorUI';
import {
  getSettings,
  updateSettings,
  type SettingsUpdate,
} from '../api/client';
import { APP_VERSION } from '../version';

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
                  <a
                    href="/api/debug/log"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-emerald-700 hover:underline"
                  >
                    View log
                  </a>
                </>
              )}
            </span>
          </div>
        </label>
      </div>

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
        {saved.status === 'success' && (
          <span className="text-xs text-emerald-700">{saved.message}</span>
        )}
        {saved.status === 'error' && (
          <span className="text-xs text-red-700">{saved.message}</span>
        )}
      </div>

      {/* Version Footer for Mobile */}
      <div className="mt-6 border-t border-stone-200/50 pt-4 text-center text-[10px] text-stone-400 md:hidden">
        DailyFX {APP_VERSION} · PolyForm Noncommercial License 1.0.0
      </div>
    </form>
  );
}
