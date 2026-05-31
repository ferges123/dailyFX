import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Save, ShieldCheck, Sparkles } from 'lucide-react';
import { type Dispatch, type FormEvent, type ReactNode, type SetStateAction, useEffect, useState } from 'react';
import { InlineSpinner, ErrorBanner } from '../components/ErrorUI';
import {
  ApiError,
  getSettings,
  type SettingsUpdate,
  testImmichConnection,
  testGeminiConnection,
  testOpenAIConnection,
  testOpenRouterConnection,
  testBytePlusConnection,
  testLocalAIConnection,
  testXiaomiConnection,
  updateSettings,
} from '../api/client';
import { Field } from '../components/Field';

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

type TestState = { status: 'idle' | 'success' | 'error'; message: string | null };
type ConnectionTestStatus = {
  status: 'idle' | 'pending' | 'success' | 'error';
  provider: string;
  message: string | null;
};
type SettingsFieldErrorKey = 'immich_url' | 'local_ai_base_url' | 'ai_vision_hourly_limit' | 'ai_image_hourly_limit' | 'favorite_albums_json';
type SettingsFieldErrors = Partial<Record<SettingsFieldErrorKey, string>>;

type TestableInputRowProps = {
  label: string;
  value: string;
  placeholder?: string;
  error?: string;
  onChange: (value: string) => void;
  testButton?: ReactNode;
};

type SecretFieldConfig = {
  key: keyof SettingsUpdate;
  label: string;
  value: string;
  placeholder?: string;
  pending: boolean;
  onClick: () => void;
  icon: ReactNode;
};

type SecretFieldColumn = SecretFieldConfig[];

function createConnectionTestHandlers(
  provider: string,
  setTestResult: Dispatch<SetStateAction<ConnectionTestStatus>>,
) {
  return {
    onMutate: () => setTestResult({ status: 'pending', provider, message: 'Testing connection...' }),
    onSuccess: (data: { message: string }) => setTestResult({ status: 'success', provider, message: data.message }),
    onError: (err: unknown) => setTestResult({ status: 'error', provider, message: (err as Error).message }),
  };
}

function isHttpUrl(value: string) {
  try {
    const parsed = new URL(value);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:';
  } catch {
    return false;
  }
}

function validateSettingsForm(form: SettingsUpdate): SettingsFieldErrors {
  const errors: SettingsFieldErrors = {};

  if (form.immich_url && !isHttpUrl(form.immich_url)) {
    errors.immich_url = 'Immich URL must be an absolute http:// or https:// URL.';
  }
  if (form.local_ai_base_url && !isHttpUrl(form.local_ai_base_url)) {
    errors.local_ai_base_url = 'Local AI base URL must be an absolute http:// or https:// URL.';
  }
  if (!Number.isInteger(form.ai_vision_hourly_limit) || form.ai_vision_hourly_limit < 1 || form.ai_vision_hourly_limit > 1000) {
    errors.ai_vision_hourly_limit = 'Vision calls per hour must be between 1 and 1000.';
  }
  if (!Number.isInteger(form.ai_image_hourly_limit) || form.ai_image_hourly_limit < 1 || form.ai_image_hourly_limit > 1000) {
    errors.ai_image_hourly_limit = 'Image calls per hour must be between 1 and 1000.';
  }
  if (form.favorite_albums_json) {
    try {
      const parsed = JSON.parse(form.favorite_albums_json);
      if (!Array.isArray(parsed)) {
        errors.favorite_albums_json = 'favorite_albums_json must be a JSON array.';
      }
    } catch {
      errors.favorite_albums_json = 'favorite_albums_json must be valid JSON.';
    }
  }

  return errors;
}

function normalizeSettingsPayload(form: SettingsUpdate): SettingsUpdate {
  return {
    ...form,
    immich_url: form.immich_url || null,
    local_ai_base_url: form.local_ai_base_url || null,
    favorite_albums_json: form.favorite_albums_json || null,
    ai_custom_prompt: form.ai_custom_prompt || null,
    immich_api_key: form.immich_api_key || null,
    openai_api_key: form.openai_api_key || null,
    gemini_api_key: form.gemini_api_key || null,
    openrouter_api_key: form.openrouter_api_key || null,
    byteplus_api_key: form.byteplus_api_key || null,
    xiaomi_api_key: form.xiaomi_api_key || null,
    local_ai_api_key: form.local_ai_api_key || null,
  };
}

function TestableInputRow({
  label,
  value,
  placeholder,
  error,
  onChange,
  testButton,
}: TestableInputRowProps) {
  return (
    <label className="grid gap-1.5 text-sm font-medium text-stone-800">
      <span className="flex items-center gap-1 text-xs font-semibold uppercase tracking-[0.18em] text-stone-500">
        <span>{label}</span>
      </span>
      <div className="flex gap-2">
        <input
          type="password"
          className={`app-control h-9 flex-1 min-w-0 text-xs ${error ? 'border-rose-300 focus:border-rose-500' : ''}`}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
        />
        {testButton}
      </div>
      {error ? <span className="text-xs text-rose-600">{error}</span> : null}
    </label>
  );
}

function SecretFieldGrid({ columns, onChange }: { columns: SecretFieldColumn[]; onChange: (key: keyof SettingsUpdate, value: string) => void }) {
  return (
    <div className="grid gap-2.5 md:gap-4 md:grid-cols-2 items-start">
      {columns.map((column, columnIndex) => (
        <div key={columnIndex} className="grid gap-2 md:gap-3">
          {column.map((item) => (
            <TestableInputRow
              key={item.key}
              label={item.label}
              value={item.value}
              placeholder={item.placeholder}
              onChange={(value) => onChange(item.key, value)}
              testButton={<TestButton icon={item.icon} label="Test" pending={item.pending} onClick={item.onClick} />}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

function shouldRetrySettingsQuery(failureCount: number, error: unknown) {
  if (failureCount >= 2) return false;
  if (error instanceof ApiError) {
    return error.status >= 500;
  }
  return true;
}

export function SettingsPage() {
  const queryClient = useQueryClient();
  const settings = useQuery({
    queryKey: ['settings'],
    queryFn: getSettings,
    retry: shouldRetrySettingsQuery,
    retryDelay: (attempt) => Math.min(150 * 2 ** attempt, 300),
    refetchOnWindowFocus: false,
  });
  const mutation = useMutation({
    mutationFn: updateSettings,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['settings'] }),
  });
  const immichTest = useMutation({ mutationFn: testImmichConnection });
  const [testResult, setTestResult] = useState<ConnectionTestStatus>({ status: 'idle', provider: '', message: null });
  const openaiTest = useMutation({ mutationFn: testOpenAIConnection, ...createConnectionTestHandlers('OpenAI', setTestResult) });
  const geminiTest = useMutation({ mutationFn: testGeminiConnection, ...createConnectionTestHandlers('Gemini', setTestResult) });
  const openrouterTest = useMutation({ mutationFn: testOpenRouterConnection, ...createConnectionTestHandlers('OpenRouter', setTestResult) });
  const byteplusTest = useMutation({ mutationFn: testBytePlusConnection, ...createConnectionTestHandlers('BytePlus', setTestResult) });
  const localAiTest = useMutation({ mutationFn: testLocalAIConnection, ...createConnectionTestHandlers('Local AI', setTestResult) });
  const xiaomiTest = useMutation({ mutationFn: testXiaomiConnection, ...createConnectionTestHandlers('Xiaomi MiMo', setTestResult) });
  const [form, setForm] = useState<SettingsUpdate>(defaults);
  const [saved, setSaved] = useState<TestState>({ status: 'idle', message: null });
  const [validationErrors, setValidationErrors] = useState<SettingsFieldErrors>({});

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
    return <ErrorBanner error={settings.error as Error | string | null} title="Could not load settings" onRetry={() => settings.refetch()} />;
  }

  function setValue<K extends keyof SettingsUpdate>(key: K, value: SettingsUpdate[K]) {
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
      setSaved({ status: 'error', message: 'Fix the highlighted settings before saving.' });
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
            <div className="text-sm font-semibold text-rose-900">Fix the highlighted settings</div>
            <div className="text-sm text-rose-800">
              {Object.values(validationErrors).join(' ')}
            </div>
          </div>
        </div>
      )}

      {/* Immich Connection */}
      <div className="app-panel grid gap-2 p-3 md:p-4">
        <div className="text-sm font-semibold text-stone-900">Immich Connection</div>
        <div className="flex flex-col md:flex-row gap-2.5 md:gap-3">
          <div className="flex-1 flex flex-col gap-0.5 md:gap-1">
            <Field
              label="Immich URL"
              type="url"
              value={form.immich_url ?? ''}
              onChange={(e) => setValue('immich_url', e.target.value)}
              placeholder="https://immich.example.com"
              error={validationErrors.immich_url}
              className="text-xs"
            />
          </div>
          <div className="flex-1 flex flex-col gap-1">
            <TestableInputRow
              label="API key"
              value={form.immich_api_key ?? ''}
              placeholder={settings.data?.immich_api_key_masked ?? ''}
              onChange={(value) => setValue('immich_api_key', value)}
              testButton={<TestButton icon={<ShieldCheck size={14} />} label="Test" pending={immichTest.isPending} onClick={() => immichTest.mutate()} />}
            />
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {immichTest.isSuccess && <span className="text-xs text-emerald-700">{immichTest.data.message}</span>}
          {immichTest.isError && <span className="text-xs text-red-700">{(immichTest.error as Error).message}</span>}
        </div>
      </div>

      {/* AI Budget Limits */}
      <div className="app-panel grid gap-2 p-3 md:p-4">
        <div className="text-sm font-semibold text-stone-900">AI Budget Limits</div>
        <div className="grid gap-1.5 md:gap-2 md:grid-cols-2">
          <Field
            label="Vision calls per hour"
            type="number"
            min={1}
            max={1000}
            step={1}
            value={form.ai_vision_hourly_limit}
            onChange={(e) => setValue('ai_vision_hourly_limit', Number(e.target.value || 0))}
            error={validationErrors.ai_vision_hourly_limit}
            className="text-xs"
          />
          <Field
            label="Image calls per hour"
            type="number"
            min={1}
            max={1000}
            step={1}
            value={form.ai_image_hourly_limit}
            onChange={(e) => setValue('ai_image_hourly_limit', Number(e.target.value || 0))}
            error={validationErrors.ai_image_hourly_limit}
            className="text-xs"
          />
        </div>
      </div>

      {/* AI API Keys */}
      <div className="app-panel grid gap-2.5 p-3 md:p-4">
        <div className="text-sm font-semibold text-stone-900">AI API Keys</div>
        <SecretFieldGrid
          columns={[
            [
              {
                key: 'openai_api_key',
                label: 'OpenAI key',
                value: form.openai_api_key ?? '',
                placeholder: settings.data?.openai_api_key_masked ?? '',
                pending: openaiTest.isPending,
                onClick: () => openaiTest.mutate(),
                icon: <Sparkles size={14} />,
              },
              {
                key: 'openrouter_api_key',
                label: 'OpenRouter key',
                value: form.openrouter_api_key ?? '',
                placeholder: settings.data?.openrouter_api_key_masked ?? '',
                pending: openrouterTest.isPending,
                onClick: () => openrouterTest.mutate(),
                icon: <Sparkles size={14} />,
              },
              {
                key: 'xiaomi_api_key',
                label: 'Xiaomi MiMo key',
                value: form.xiaomi_api_key ?? '',
                placeholder: settings.data?.xiaomi_api_key_masked ?? '',
                pending: xiaomiTest.isPending,
                onClick: () => xiaomiTest.mutate(),
                icon: <Sparkles size={14} />,
              },
            ],
            [
              {
                key: 'gemini_api_key',
                label: 'Gemini key',
                value: form.gemini_api_key ?? '',
                placeholder: settings.data?.gemini_api_key_masked ?? '',
                pending: geminiTest.isPending,
                onClick: () => geminiTest.mutate(),
                icon: <Sparkles size={14} />,
              },
              {
                key: 'byteplus_api_key',
                label: 'BytePlus key',
                value: form.byteplus_api_key ?? '',
                placeholder: settings.data?.byteplus_api_key_masked ?? '',
                pending: byteplusTest.isPending,
                onClick: () => byteplusTest.mutate(),
                icon: <Sparkles size={14} />,
              },
            ],
          ]}
          onChange={(key, value) => setValue(key, value)}
        />

        {/* Local AI */}
        <div className="border-t border-stone-100 pt-2.5 flex flex-col md:flex-row gap-2.5 md:gap-3">
          <div className="flex-1 flex flex-col gap-0.5 md:gap-1">
            <Field
              label="Local AI base URL"
              type="url"
              value={form.local_ai_base_url ?? ''}
              onChange={(e) => setValue('local_ai_base_url', e.target.value)}
              placeholder="http://localhost:11434/v1"
              error={validationErrors.local_ai_base_url}
              className="text-xs"
            />
          </div>
          <div className="flex-1 flex flex-col gap-1">
            <TestableInputRow
              label="Local AI key (optional)"
              value={form.local_ai_api_key ?? ''}
              placeholder={settings.data?.local_ai_api_key_masked ?? ''}
              onChange={(value) => setValue('local_ai_api_key', value)}
              testButton={<TestButton icon={<Sparkles size={14} />} label="Test" pending={localAiTest.isPending} onClick={() => localAiTest.mutate()} />}
            />
          </div>
        </div>

        {/* Unified test result at the bottom */}
        {testResult.status !== 'idle' && (
          <div className="mt-1 text-xs border-t border-stone-100 pt-2 flex items-center gap-1.5">
            <span className="font-semibold text-stone-700">{testResult.provider}:</span>
            {testResult.status === 'pending' && <span className="text-stone-500 animate-pulse">{testResult.message}</span>}
            {testResult.status === 'success' && <span className="text-emerald-700 font-medium">{testResult.message}</span>}
            {testResult.status === 'error' && <span className="text-red-700 font-medium">{testResult.message}</span>}
          </div>
        )}
      </div>

      {/* AI Custom Prompt */}
      <div className="app-panel grid gap-2 p-3 md:p-4">
        <div className="text-sm font-semibold text-stone-900">AI Custom Prompt</div>
        <Field
          label="Default AI prompt (for AI styles)"
          value={form.ai_custom_prompt ?? ''}
          maxLength={10000}
          onChange={(e) => setValue('ai_custom_prompt', e.target.value || null)}
          placeholder="Leave empty to use built-in prompt"
          className="text-xs"
        />
      </div>

      {/* Debug Mode */}
      <div className="app-panel p-3 md:p-4">
        <label className="flex items-center gap-1.5 md:gap-2 text-xs cursor-pointer">
          <input type="checkbox" checked={form.debug_mode} onChange={(e) => setValue('debug_mode', e.target.checked)} className="rounded border-stone-300" />
          <div>
            <span className="font-medium">Debug mode</span>
            <span className="text-stone-600">
              {' · '}Logs to /data/logs/debug_*.log
              {form.debug_mode && (
                <>{' · '}<a href="/api/debug/log" target="_blank" rel="noopener noreferrer" className="text-emerald-700 hover:underline">View log</a></>
              )}
            </span>
          </div>
        </label>
      </div>

      {/* Save */}
      <div className="flex flex-wrap items-center gap-2">
        <button type="submit" className="app-button-primary h-9 px-4 disabled:opacity-60 disabled:hover:bg-emerald-700" disabled={mutation.isPending}>
          <Save size={14} />
          Save
        </button>
        {saved.status === 'success' && <span className="text-xs text-emerald-700">{saved.message}</span>}
        {saved.status === 'error' && <span className="text-xs text-red-700">{saved.message}</span>}
      </div>
    </form>
  );
}

function TestButton({ icon, label, pending, onClick }: { icon: ReactNode; label: string; pending: boolean; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} disabled={pending} className="app-button-secondary h-9 px-3 text-xs disabled:opacity-60 shrink-0">
      {icon}
      {label}
    </button>
  );
}

export const OPENAI_VISION_MODELS = [{ label: 'gpt-4o-mini', value: 'gpt-4o-mini' }, { label: 'gpt-4o', value: 'gpt-4o' }];
export const GEMINI_VISION_MODELS = [
  { label: 'gemini-2.5-flash', value: 'gemini-2.5-flash' },
  { label: 'gemini-2.5-pro', value: 'gemini-2.5-pro' },
  { label: 'gemini-2.0-flash', value: 'gemini-2.0-flash' },
  { label: 'gemini-2.0-flash-lite', value: 'gemini-2.0-flash-lite' },
];
export const XIAOMI_VISION_MODELS = [
  { label: 'mimo-v2.5', value: 'mimo-v2.5' },
  { label: 'mimo-v2.5-pro', value: 'mimo-v2.5-pro' },
];
export function getVisionModelOptions(provider: string) {
  if (provider === 'openai') return OPENAI_VISION_MODELS;
  if (provider === 'gemini') return GEMINI_VISION_MODELS;
  if (provider === 'xiaomi') return XIAOMI_VISION_MODELS;
  return [];
}

export const OPENAI_IMAGE_MODELS = [{ label: 'gpt-image-1', value: 'gpt-image-1' }, { label: 'gpt-image-1-mini', value: 'gpt-image-1-mini' }];
export const GEMINI_IMAGE_MODELS = [
  { label: 'gemini-2.5-flash-image', value: 'gemini-2.5-flash-image' },
  { label: 'gemini-3.1-flash-image-preview', value: 'gemini-3.1-flash-image-preview' },
  { label: 'gemini-3-pro-image-preview', value: 'gemini-3-pro-image-preview' },
];
export function getImageModelOptions(provider: string) {
  if (provider === 'openai') return OPENAI_IMAGE_MODELS;
  if (provider === 'gemini') return GEMINI_IMAGE_MODELS;
  return [];
}
