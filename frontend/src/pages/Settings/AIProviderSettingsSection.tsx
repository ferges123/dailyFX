import { useState, type ReactNode, type Dispatch, type SetStateAction } from 'react';
import { Sparkles } from 'lucide-react';
import { useMutation } from '@tanstack/react-query';
import {
  type SettingsUpdate,
  testOpenAIConnection,
  testGeminiConnection,
  testOpenRouterConnection,
  testBytePlusConnection,
  testLocalAIConnection,
  testXiaomiConnection,
} from '../../api/client';
import { Field } from '../../components/Field';
import { TestableInputRow, TestButton } from './TestableInputRow';
import { type SettingsFieldErrors } from './settingsValidation';

type ConnectionTestStatus = {
  status: 'idle' | 'pending' | 'success' | 'error';
  provider: string;
  message: string | null;
};

function createConnectionTestHandlers(
  provider: string,
  setTestResult: Dispatch<SetStateAction<ConnectionTestStatus>>,
) {
  return {
    onMutate: () =>
      setTestResult({
        status: 'pending',
        provider,
        message: 'Testing connection...',
      }),
    onSuccess: (data: { message: string }) =>
      setTestResult({ status: 'success', provider, message: data.message }),
    onError: (err: unknown) =>
      setTestResult({
        status: 'error',
        provider,
        message: (err as Error).message,
      }),
  };
}

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

function SecretFieldGrid({
  columns,
  onChange,
}: {
  columns: SecretFieldColumn[];
  onChange: (key: keyof SettingsUpdate, value: string) => void;
}) {
  return (
    <div className="grid gap-2.5 md:grid-cols-2 md:gap-4 items-start">
      {columns.map((column, columnIndex) => (
        <div key={columnIndex} className="grid gap-2 md:gap-3">
          {column.map((item) => (
            <TestableInputRow
              key={item.key}
              label={item.label}
              value={item.value}
              placeholder={item.placeholder}
              onChange={(value) => onChange(item.key, value)}
              testButton={
                <TestButton
                  icon={item.icon}
                  label="Test"
                  pending={item.pending}
                  onClick={item.onClick}
                />
              }
            />
          ))}
        </div>
      ))}
    </div>
  );
}

type AIProviderSettingsSectionProps = {
  form: SettingsUpdate;
  settingsData?: {
    openai_api_key_masked: string | null;
    gemini_api_key_masked: string | null;
    openrouter_api_key_masked: string | null;
    byteplus_api_key_masked: string | null;
    xiaomi_api_key_masked: string | null;
    local_ai_api_key_masked: string | null;
  } | null;
  onChange: (key: keyof SettingsUpdate, value: string | number) => void;
  validationErrors: SettingsFieldErrors;
};

export function AIProviderSettingsSection({
  form,
  settingsData,
  onChange,
  validationErrors,
}: AIProviderSettingsSectionProps) {
  const [testResult, setTestResult] = useState<ConnectionTestStatus>({
    status: 'idle',
    provider: '',
    message: null,
  });

  const openaiTest = useMutation({
    mutationFn: testOpenAIConnection,
    ...createConnectionTestHandlers('OpenAI', setTestResult),
  });
  const geminiTest = useMutation({
    mutationFn: testGeminiConnection,
    ...createConnectionTestHandlers('Gemini', setTestResult),
  });
  const openrouterTest = useMutation({
    mutationFn: testOpenRouterConnection,
    ...createConnectionTestHandlers('OpenRouter', setTestResult),
  });
  const byteplusTest = useMutation({
    mutationFn: testBytePlusConnection,
    ...createConnectionTestHandlers('BytePlus', setTestResult),
  });
  const localAiTest = useMutation({
    mutationFn: testLocalAIConnection,
    ...createConnectionTestHandlers('Local AI', setTestResult),
  });
  const xiaomiTest = useMutation({
    mutationFn: testXiaomiConnection,
    ...createConnectionTestHandlers('Xiaomi MiMo', setTestResult),
  });

  const handleKeyChange = (key: keyof SettingsUpdate, value: string) => {
    onChange(key, value);
    setTestResult({ status: 'idle', provider: '', message: null });
  };

  return (
    <div className="grid gap-2.5 md:gap-3">
      {/* AI Budget Limits */}
      <div className="app-panel grid gap-2 p-3 md:p-4">
        <div className="text-sm font-semibold text-stone-900">
          AI Budget Limits
        </div>
        <div className="grid gap-1.5 md:gap-2 md:grid-cols-2">
          <Field
            label="Vision calls per hour"
            type="number"
            min={1}
            max={1000}
            step={1}
            value={form.ai_vision_hourly_limit}
            onChange={(e) =>
              onChange('ai_vision_hourly_limit', Number(e.target.value || 0))
            }
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
            onChange={(e) =>
              onChange('ai_image_hourly_limit', Number(e.target.value || 0))
            }
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
                value: (form.openai_api_key as string) ?? '',
                placeholder: settingsData?.openai_api_key_masked ?? '',
                pending: openaiTest.isPending,
                onClick: () => openaiTest.mutate(),
                icon: <Sparkles size={14} />,
              },
              {
                key: 'openrouter_api_key',
                label: 'OpenRouter key',
                value: (form.openrouter_api_key as string) ?? '',
                placeholder: settingsData?.openrouter_api_key_masked ?? '',
                pending: openrouterTest.isPending,
                onClick: () => openrouterTest.mutate(),
                icon: <Sparkles size={14} />,
              },
              {
                key: 'xiaomi_api_key',
                label: 'Xiaomi MiMo key',
                value: (form.xiaomi_api_key as string) ?? '',
                placeholder: settingsData?.xiaomi_api_key_masked ?? '',
                pending: xiaomiTest.isPending,
                onClick: () => xiaomiTest.mutate(),
                icon: <Sparkles size={14} />,
              },
            ],
            [
              {
                key: 'gemini_api_key',
                label: 'Gemini key',
                value: (form.gemini_api_key as string) ?? '',
                placeholder: settingsData?.gemini_api_key_masked ?? '',
                pending: geminiTest.isPending,
                onClick: () => geminiTest.mutate(),
                icon: <Sparkles size={14} />,
              },
              {
                key: 'byteplus_api_key',
                label: 'BytePlus key',
                value: (form.byteplus_api_key as string) ?? '',
                placeholder: settingsData?.byteplus_api_key_masked ?? '',
                pending: byteplusTest.isPending,
                onClick: () => byteplusTest.mutate(),
                icon: <Sparkles size={14} />,
              },
            ],
          ]}
          onChange={handleKeyChange}
        />

        {/* Local AI */}
        <div className="border-t border-stone-100 pt-2.5 flex flex-col md:flex-row gap-2.5 md:gap-3">
          <div className="flex-1 flex flex-col gap-0.5 md:gap-1">
            <Field
              label="Local AI base URL"
              type="url"
              value={(form.local_ai_base_url as string) ?? ''}
              onChange={(e) => onChange('local_ai_base_url', e.target.value)}
              placeholder="http://localhost:11434/v1"
              error={validationErrors.local_ai_base_url}
              className="text-xs"
            />
          </div>
          <div className="flex-1 flex flex-col gap-1">
            <TestableInputRow
              label="Local AI key (optional)"
              value={(form.local_ai_api_key as string) ?? ''}
              placeholder={settingsData?.local_ai_api_key_masked ?? ''}
              onChange={(value) => handleKeyChange('local_ai_api_key', value)}
              testButton={
                <TestButton
                  icon={<Sparkles size={14} />}
                  label="Test"
                  pending={localAiTest.isPending}
                  onClick={() => localAiTest.mutate()}
                />
              }
            />
          </div>
        </div>

        {/* Unified test result at the bottom */}
        {testResult.status !== 'idle' && (
          <div className="mt-1 text-xs border-t border-stone-100 pt-2 flex items-center gap-1.5">
            <span className="font-semibold text-stone-700">
              {testResult.provider}:
            </span>
            {testResult.status === 'pending' && (
              <span className="text-stone-500 animate-pulse">
                {testResult.message}
              </span>
            )}
            {testResult.status === 'success' && (
              <span className="text-emerald-700 font-medium">
                {testResult.message}
              </span>
            )}
            {testResult.status === 'error' && (
              <span className="text-red-700 font-medium">
                {testResult.message}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export const OPENAI_VISION_MODELS = [
  { label: 'gpt-4o-mini', value: 'gpt-4o-mini' },
  { label: 'gpt-4o', value: 'gpt-4o' },
];
export const GEMINI_VISION_MODELS = [
  { label: 'gemini-2.5-flash', value: 'gemini-2.5-flash' },
  { label: 'gemini-2.5-pro', value: 'gemini-2.5-pro' },
  { label: 'gemini-2.0-flash', value: 'gemini-2.0-flash' },
  { label: 'gemini-2.0-flash-lite', value: 'gemini-2.0-flash-lite' },
];
export const XIAOMI_VISION_MODELS = [
  { label: 'mimo-v2.5', value: 'mimo-v2.5' },
];
export function getVisionModelOptions(provider: string) {
  if (provider === 'openai') return OPENAI_VISION_MODELS;
  if (provider === 'gemini') return GEMINI_VISION_MODELS;
  if (provider === 'xiaomi') return XIAOMI_VISION_MODELS;
  return [];
}

export const OPENAI_IMAGE_MODELS = [
  { label: 'gpt-image-1', value: 'gpt-image-1' },
  { label: 'gpt-image-1-mini', value: 'gpt-image-1-mini' },
];
export const GEMINI_IMAGE_MODELS = [
  { label: 'gemini-2.5-flash-image', value: 'gemini-2.5-flash-image' },
  {
    label: 'gemini-3.1-flash-image-preview',
    value: 'gemini-3.1-flash-image-preview',
  },
  { label: 'gemini-3-pro-image-preview', value: 'gemini-3-pro-image-preview' },
];
export function getImageModelOptions(provider: string) {
  if (provider === 'openai') return OPENAI_IMAGE_MODELS;
  if (provider === 'gemini') return GEMINI_IMAGE_MODELS;
  return [];
}
