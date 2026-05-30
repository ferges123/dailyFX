import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Save, ShieldCheck, Sparkles } from 'lucide-react';
import { type ReactNode, FormEvent, useEffect, useState } from 'react';
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
  const [testResult, setTestResult] = useState<{ status: 'idle' | 'pending' | 'success' | 'error'; provider: string; message: string | null }>({ status: 'idle', provider: '', message: null });
  const openaiTest = useMutation({
    mutationFn: testOpenAIConnection,
    onMutate: () => setTestResult({ status: 'pending', provider: 'OpenAI', message: 'Testing connection...' }),
    onSuccess: (data) => setTestResult({ status: 'success', provider: 'OpenAI', message: data.message }),
    onError: (err) => setTestResult({ status: 'error', provider: 'OpenAI', message: (err as Error).message }),
  });
  const geminiTest = useMutation({
    mutationFn: testGeminiConnection,
    onMutate: () => setTestResult({ status: 'pending', provider: 'Gemini', message: 'Testing connection...' }),
    onSuccess: (data) => setTestResult({ status: 'success', provider: 'Gemini', message: data.message }),
    onError: (err) => setTestResult({ status: 'error', provider: 'Gemini', message: (err as Error).message }),
  });
  const openrouterTest = useMutation({
    mutationFn: testOpenRouterConnection,
    onMutate: () => setTestResult({ status: 'pending', provider: 'OpenRouter', message: 'Testing connection...' }),
    onSuccess: (data) => setTestResult({ status: 'success', provider: 'OpenRouter', message: data.message }),
    onError: (err) => setTestResult({ status: 'error', provider: 'OpenRouter', message: (err as Error).message }),
  });
  const byteplusTest = useMutation({
    mutationFn: testBytePlusConnection,
    onMutate: () => setTestResult({ status: 'pending', provider: 'BytePlus', message: 'Testing connection...' }),
    onSuccess: (data) => setTestResult({ status: 'success', provider: 'BytePlus', message: data.message }),
    onError: (err) => setTestResult({ status: 'error', provider: 'BytePlus', message: (err as Error).message }),
  });
  const localAiTest = useMutation({
    mutationFn: testLocalAIConnection,
    onMutate: () => setTestResult({ status: 'pending', provider: 'Local AI', message: 'Testing connection...' }),
    onSuccess: (data) => setTestResult({ status: 'success', provider: 'Local AI', message: data.message }),
    onError: (err) => setTestResult({ status: 'error', provider: 'Local AI', message: (err as Error).message }),
  });
  const xiaomiTest = useMutation({
    mutationFn: testXiaomiConnection,
    onMutate: () => setTestResult({ status: 'pending', provider: 'Xiaomi MiMo', message: 'Testing connection...' }),
    onSuccess: (data) => setTestResult({ status: 'success', provider: 'Xiaomi MiMo', message: data.message }),
    onError: (err) => setTestResult({ status: 'error', provider: 'Xiaomi MiMo', message: (err as Error).message }),
  });
  const [form, setForm] = useState<SettingsUpdate>(defaults);
  const [saved, setSaved] = useState<TestState>({ status: 'idle', message: null });

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
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaved({ status: 'idle', message: null });
    mutation.mutate(
      {
        ...form,
        immich_url: form.immich_url || null,
        local_ai_base_url: form.local_ai_base_url || null,
        immich_api_key: form.immich_api_key || null,
        openai_api_key: form.openai_api_key || null,
        gemini_api_key: form.gemini_api_key || null,
        openrouter_api_key: form.openrouter_api_key || null,
        byteplus_api_key: form.byteplus_api_key || null,
        xiaomi_api_key: form.xiaomi_api_key || null,
        local_ai_api_key: form.local_ai_api_key || null,
      },
      {
        onSuccess: () => setSaved({ status: 'success', message: 'Saved' }),
        onError: () => setSaved({ status: 'error', message: 'Save failed' }),
      },
    );
  }

  return (
    <form onSubmit={submit} className="grid gap-3">
      {showInlineLoadError && (
        <ErrorBanner
          error={settings.error as Error | string | null}
          title="Settings refresh failed"
          onRetry={() => settings.refetch()}
        />
      )}

      {/* Immich Connection */}
      <div className="grid gap-2 rounded-lg border border-stone-200 bg-white p-3">
        <div className="text-xs font-semibold text-stone-900">Immich Connection</div>
        <div className="flex flex-col md:flex-row gap-3">
          <div className="flex-1 flex flex-col gap-1">
            <span className="text-sm font-medium text-stone-800">Immich URL</span>
            <input
              type="url"
              className="h-9 w-full rounded-md border border-stone-300 bg-white text-sm outline-none focus:border-emerald-700 px-3"
              value={form.immich_url ?? ''}
              onChange={(e) => setValue('immich_url', e.target.value)}
              placeholder="https://immich.example.com"
            />
          </div>
          <div className="flex-1 flex flex-col gap-1">
            <span className="text-sm font-medium text-stone-800">API key</span>
            <div className="flex gap-2">
              <input
                type="password"
                className="h-9 flex-1 min-w-0 rounded-md border border-stone-300 bg-white text-sm outline-none focus:border-emerald-700 px-3"
                value={form.immich_api_key ?? ''}
                onChange={(e) => setValue('immich_api_key', e.target.value)}
                placeholder={settings.data?.immich_api_key_masked ?? ''}
              />
              <TestButton icon={<ShieldCheck size={14} />} label="Test" pending={immichTest.isPending} onClick={() => immichTest.mutate()} />
            </div>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {immichTest.isSuccess && <span className="text-xs text-emerald-700">{immichTest.data.message}</span>}
          {immichTest.isError && <span className="text-xs text-red-700">{(immichTest.error as Error).message}</span>}
        </div>
      </div>

      {/* AI Budget Limits */}
      <div className="grid gap-2 rounded-lg border border-stone-200 bg-white p-3">
        <div className="text-xs font-semibold text-stone-900">AI Budget Limits</div>
        <div className="grid gap-2 md:grid-cols-2">
          <Field
            label="Vision calls per hour"
            type="number"
            min={1}
            max={1000}
            step={1}
            value={form.ai_vision_hourly_limit}
            onChange={(e) => setValue('ai_vision_hourly_limit', Number(e.target.value || 0))}
          />
          <Field
            label="Image calls per hour"
            type="number"
            min={1}
            max={1000}
            step={1}
            value={form.ai_image_hourly_limit}
            onChange={(e) => setValue('ai_image_hourly_limit', Number(e.target.value || 0))}
          />
        </div>
      </div>

      {/* AI API Keys */}
      <div className="grid gap-3 rounded-lg border border-stone-200 bg-white p-3">
        <div className="text-xs font-semibold text-stone-900">AI API Keys</div>
        <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_1px_minmax(0,1fr)] md:items-start">
          <div className="grid gap-3">
            {/* OpenAI */}
            <div className="flex flex-col gap-1">
              <span className="text-sm font-medium text-stone-800">OpenAI key</span>
              <div className="flex gap-2">
                <input
                  type="password"
                  className="h-9 flex-1 min-w-0 rounded-md border border-stone-300 bg-white text-sm outline-none focus:border-emerald-700 px-3"
                  value={form.openai_api_key ?? ''}
                  onChange={(e) => setValue('openai_api_key', e.target.value)}
                  placeholder={settings.data?.openai_api_key_masked ?? ''}
                />
                <TestButton icon={<Sparkles size={14} />} label="Test" pending={openaiTest.isPending} onClick={() => openaiTest.mutate()} />
              </div>
            </div>

            {/* OpenRouter */}
            <div className="flex flex-col gap-1">
              <span className="text-sm font-medium text-stone-800">OpenRouter key</span>
              <div className="flex gap-2">
                <input
                  type="password"
                  className="h-9 flex-1 min-w-0 rounded-md border border-stone-300 bg-white text-sm outline-none focus:border-emerald-700 px-3"
                  value={form.openrouter_api_key ?? ''}
                  onChange={(e) => setValue('openrouter_api_key', e.target.value)}
                  placeholder={settings.data?.openrouter_api_key_masked ?? ''}
                />
                <TestButton icon={<Sparkles size={14} />} label="Test" pending={openrouterTest.isPending} onClick={() => openrouterTest.mutate()} />
              </div>
            </div>

            {/* Xiaomi MiMo */}
            <div className="flex flex-col gap-1">
              <span className="text-sm font-medium text-stone-800">Xiaomi MiMo key</span>
              <div className="flex gap-2">
                <input
                  type="password"
                  className="h-9 flex-1 min-w-0 rounded-md border border-stone-300 bg-white text-sm outline-none focus:border-emerald-700 px-3"
                  value={form.xiaomi_api_key ?? ''}
                  onChange={(e) => setValue('xiaomi_api_key', e.target.value)}
                  placeholder={settings.data?.xiaomi_api_key_masked ?? ''}
                />
                <TestButton icon={<Sparkles size={14} />} label="Test" pending={xiaomiTest.isPending} onClick={() => xiaomiTest.mutate()} />
              </div>
            </div>
          </div>

          <div className="hidden md:block bg-stone-200 self-stretch" />

          <div className="grid gap-3">
            {/* Gemini */}
            <div className="flex flex-col gap-1">
              <span className="text-sm font-medium text-stone-800">Gemini key</span>
              <div className="flex gap-2">
                <input
                  type="password"
                  className="h-9 flex-1 min-w-0 rounded-md border border-stone-300 bg-white text-sm outline-none focus:border-emerald-700 px-3"
                  value={form.gemini_api_key ?? ''}
                  onChange={(e) => setValue('gemini_api_key', e.target.value)}
                  placeholder={settings.data?.gemini_api_key_masked ?? ''}
                />
                <TestButton icon={<Sparkles size={14} />} label="Test" pending={geminiTest.isPending} onClick={() => geminiTest.mutate()} />
              </div>
            </div>

            {/* BytePlus */}
            <div className="flex flex-col gap-1">
              <span className="text-sm font-medium text-stone-800">BytePlus key</span>
              <div className="flex gap-2">
                <input
                  type="password"
                  className="h-9 flex-1 min-w-0 rounded-md border border-stone-300 bg-white text-sm outline-none focus:border-emerald-700 px-3"
                  value={form.byteplus_api_key ?? ''}
                  onChange={(e) => setValue('byteplus_api_key', e.target.value)}
                  placeholder={settings.data?.byteplus_api_key_masked ?? ''}
                />
                <TestButton icon={<Sparkles size={14} />} label="Test" pending={byteplusTest.isPending} onClick={() => byteplusTest.mutate()} />
              </div>
            </div>
          </div>
        </div>

        {/* Local AI */}
        <div className="border-t border-stone-100 pt-3 flex flex-col md:flex-row gap-3">
          <div className="flex-1 flex flex-col gap-1">
            <span className="text-sm font-medium text-stone-800">Local AI base URL</span>
            <input
              type="url"
              className="h-9 w-full rounded-md border border-stone-300 bg-white text-sm outline-none focus:border-emerald-700 px-3"
              value={form.local_ai_base_url ?? ''}
              onChange={(e) => setValue('local_ai_base_url', e.target.value)}
              placeholder="http://localhost:11434/v1"
            />
          </div>
          <div className="flex-1 flex flex-col gap-1">
            <span className="text-sm font-medium text-stone-800">Local AI key (optional)</span>
            <div className="flex gap-2">
              <input
                type="password"
                className="h-9 flex-1 min-w-0 rounded-md border border-stone-300 bg-white text-sm outline-none focus:border-emerald-700 px-3"
                value={form.local_ai_api_key ?? ''}
                onChange={(e) => setValue('local_ai_api_key', e.target.value)}
                placeholder={settings.data?.local_ai_api_key_masked ?? ''}
              />
              <TestButton icon={<Sparkles size={14} />} label="Test" pending={localAiTest.isPending} onClick={() => localAiTest.mutate()} />
            </div>
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
      <div className="rounded-lg border border-stone-200 bg-white p-3 grid gap-2">
        <div className="text-xs font-semibold text-stone-900">AI Custom Prompt</div>
        <Field
          label="Default AI prompt (for AI styles)"
          value={form.ai_custom_prompt ?? ''}
          maxLength={10000}
          onChange={(e) => setValue('ai_custom_prompt', e.target.value || null)}
          placeholder="Leave empty to use built-in prompt"
        />
      </div>

      {/* Debug Mode */}
      <div className="rounded-lg border border-stone-200 bg-white p-3">
        <label className="flex items-center gap-2 text-xs cursor-pointer">
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
        <button type="submit" className="inline-flex h-8 items-center gap-2 rounded-md bg-emerald-800 px-3 text-sm font-semibold text-white hover:bg-emerald-900 disabled:opacity-60" disabled={mutation.isPending}>
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
    <button type="button" onClick={onClick} disabled={pending} className="inline-flex h-9 items-center gap-2 rounded-md border border-stone-300 bg-white px-3.5 text-sm font-semibold text-stone-800 hover:bg-stone-50 disabled:opacity-60 shrink-0">
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
