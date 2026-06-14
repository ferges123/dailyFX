import { type RefObject, useState, useEffect } from 'react';
import { HelpCircle, Check, X } from 'lucide-react';
import {
  type FilterPreset,
  type EffectPreset,
  type NotificationPreset,
  type Schedule,
  getProviderModels,
} from '../../api/client';
import { Field, SelectField } from '../../components/Field';
import { InlineError, ProviderModelField, SectionCard } from '../../components/FormUI';
import { describeAutomationSchedule } from '../automation.utils';
import {
  automationScheduleModeOptions,
  weekdayOptions,
} from '../automation.types';
import { getVisionModelOptions, getImageModelOptions } from '../Settings';
import { type FormState } from './types';

export interface ScheduleFormProps {
  formPanelRef: RefObject<HTMLElement | null>;
  isNew: boolean;
  editing: Schedule | null;
  form: FormState;
  setForm: React.Dispatch<React.SetStateAction<FormState>>;
  validationIssues: string[];
  filterPresets: FilterPreset[];
  effectPresets: EffectPreset[];
  notificationPresets: NotificationPreset[];
  canSave: boolean;
  isSaving: boolean;
  onSave: () => void;
  onCancel: () => void;
}

export function ScheduleForm({
  formPanelRef,
  isNew,
  editing,
  form,
  setForm,
  validationIssues,
  filterPresets,
  effectPresets,
  notificationPresets,
  canSave,
  isSaving,
  onSave,
  onCancel,
}: ScheduleFormProps) {
  function toggleDay(day: number) {
    setForm((current) => ({
      ...current,
      scheduleMode: 'custom',
      scheduleDays: current.scheduleDays.includes(day)
        ? current.scheduleDays.filter((existing) => existing !== day)
        : [...current.scheduleDays, day].sort((a, b) => a - b),
    }));
  }

  const [visionModels, setVisionModels] = useState<Array<{ label: string; value: string }>>(() =>
    getVisionModelOptions(form.ai_vision_provider)
  );
  const [imageModels, setImageModels] = useState<Array<{ label: string; value: string }>>(() =>
    getImageModelOptions(form.ai_image_provider)
  );

  useEffect(() => {
    let active = true;
    if (form.ai_vision_provider === 'none') {
      setVisionModels([]);
      return;
    }
    setVisionModels(getVisionModelOptions(form.ai_vision_provider));
    getProviderModels(form.ai_vision_provider)
      .then((data) => {
        if (active) {
          setVisionModels(data.vision_models);
        }
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [form.ai_vision_provider]);

  useEffect(() => {
    let active = true;
    if (form.ai_image_provider === 'none') {
      setImageModels([]);
      return;
    }
    setImageModels(getImageModelOptions(form.ai_image_provider));
    getProviderModels(form.ai_image_provider)
      .then((data) => {
        if (active) {
          setImageModels(data.image_models);
        }
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [form.ai_image_provider]);


  return (
    <aside
      ref={formPanelRef}
      aria-label="Schedule form panel"
      className="app-panel grid gap-2 p-2 md:gap-2.5 md:p-2.5"
    >
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-center gap-1.5">
          <div className="text-sm font-semibold text-stone-900">
            {isNew ? 'New schedule' : `Editing: ${editing?.name}`}
          </div>
          <span
            title="Required fields are marked with an asterisk."
            aria-label="Required fields are marked with an asterisk."
            className="inline-flex items-center text-stone-400 transition hover:text-stone-600"
          >
            <HelpCircle size={14} />
          </span>
        </div>
        <div className="rounded-xl border border-stone-200 bg-stone-50 px-2 py-1 text-[10px] leading-4 text-stone-500">
          {describeAutomationSchedule({
            mode: form.scheduleMode,
            days: form.scheduleDays,
            time: form.scheduleTime,
          })}
        </div>
      </div>

      {validationIssues.length > 0 && (
        <InlineError
          title="Fix the highlighted fields"
          message={validationIssues.join(' ')}
        />
      )}

      <div className="grid gap-2 xl:grid-cols-2 xl:items-start">
        <div className="grid gap-2">
          <SectionCard
            title="Basics"
            description="Choose the schedule name and target album."
            className="gap-1.5 p-2 md:p-2.5"
          >
            <div className="grid gap-1.5 sm:grid-cols-2">
              <Field
                label="Name"
                required
                value={form.name}
                maxLength={255}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    name: event.target.value,
                  }))
                }
                className="text-xs"
                hint="Shown in the schedules list."
              />
              <Field
                label="Album name"
                required
                value={form.album_name}
                maxLength={255}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    album_name: event.target.value,
                  }))
                }
                className="text-xs"
                hint="The album created or updated on run."
              />
            </div>
          </SectionCard>

          <SectionCard
            title="Schedule"
            description="Pick when the job runs and how much control you need."
            className="gap-1.5 p-2 md:p-2.5"
          >
            <div className="grid gap-1.5 md:gap-2">
              <div className="grid gap-1 sm:flex sm:flex-wrap">
                {automationScheduleModeOptions.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => {
                      const days =
                        option.value === 'weekdays'
                          ? [0, 1, 2, 3, 4]
                          : option.value === 'weekends'
                            ? [5, 6]
                            : [];
                      setForm((current) => ({
                        ...current,
                        scheduleMode: option.value,
                        scheduleDays: days,
                      }));
                    }}
                    className={`rounded-full border px-3 py-2 text-xs font-medium transition-colors sm:py-1 ${
                      form.scheduleMode === option.value
                        ? 'border-emerald-500 bg-emerald-50 text-emerald-800'
                        : 'border-stone-300 bg-white text-stone-700 hover:border-emerald-300'
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
              {form.scheduleMode === 'custom' && (
                <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap">
                  {weekdayOptions.map((day) => (
                    <button
                      key={day.value}
                      type="button"
                      onClick={() => toggleDay(day.value)}
                      className={`rounded-full border px-2.5 py-2 text-xs font-medium transition-colors sm:py-1 ${
                        form.scheduleDays.includes(day.value)
                          ? 'border-emerald-500 bg-emerald-50 text-emerald-800'
                          : 'border-stone-300 bg-white text-stone-600 hover:border-emerald-300'
                      }`}
                    >
                      {day.label}
                    </button>
                  ))}
                </div>
              )}
              <div className="grid gap-1.5 sm:grid-cols-[120px_1fr] sm:items-end">
                <label className="grid gap-0.5 text-sm font-medium text-stone-800">
                  <span className="flex items-center gap-1">
                    <span>Time</span>
                    <span className="text-rose-500">*</span>
                  </span>
                  <input
                    type="time"
                    value={form.scheduleTime}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        scheduleTime: event.target.value,
                      }))
                    }
                    className="app-control h-9 w-full min-w-0"
                  />
                </label>
                <div className="rounded-xl border border-stone-200 bg-stone-50 px-2 py-1 text-[10px] leading-4 text-stone-600">
                  {describeAutomationSchedule({
                    mode: form.scheduleMode,
                    days: form.scheduleDays,
                    time: form.scheduleTime,
                  })}
                </div>
              </div>
            </div>
          </SectionCard>
        </div>

        <div className="grid gap-2">
          <SectionCard
            title="Presets"
            description="Link the filter, effect, and notification presets used by the run."
            className="gap-1.5 p-2 md:p-2.5"
          >
            <div className="grid gap-1.5 md:gap-2 lg:grid-cols-3">
              <SelectField
                label="Filter preset"
                value={String(form.filter_preset_id)}
                required
                className="text-xs"
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    filter_preset_id: event.target.value
                      ? Number(event.target.value)
                      : '',
                  }))
                }
              >
                <option value="">Select a filter preset</option>
                {filterPresets.map((preset) => (
                  <option key={preset.id} value={preset.id}>
                    {preset.name}
                  </option>
                ))}
              </SelectField>
              <SelectField
                label="Effect preset"
                value={String(form.effect_preset_id)}
                required
                className="text-xs"
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    effect_preset_id: event.target.value
                      ? Number(event.target.value)
                      : '',
                  }))
                }
              >
                <option value="">Select an effect preset</option>
                {effectPresets.map((preset) => (
                  <option key={preset.id} value={preset.id}>
                    {preset.name}
                  </option>
                ))}
              </SelectField>
              <div className="grid gap-0.5">
                <div className="text-sm font-medium text-stone-800">
                  Notification presets{' '}
                  <span className="text-rose-500">*</span>
                </div>
                <div className="rounded-2xl border border-stone-200 bg-white p-2.5 shadow-xs">
                  <div className="flex flex-wrap gap-1">
                    {notificationPresets
                      .filter((preset) =>
                        form.notification_preset_ids.includes(preset.id),
                      )
                      .map((preset) => (
                        <span
                          key={preset.id}
                          className="app-chip inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-medium text-stone-800"
                        >
                          {preset.name}
                          <button
                            type="button"
                            onClick={() =>
                              setForm((current) => ({
                                ...current,
                                notification_preset_ids:
                                  current.notification_preset_ids.filter(
                                    (id) => id !== preset.id,
                                  ),
                              }))
                            }
                            className="rounded-xs p-0.5 text-stone-400 hover:text-stone-700"
                          >
                            <X size={10} />
                          </button>
                        </span>
                      ))}
                    {form.notification_preset_ids.length === 0 && (
                      <span
                        title="No notification presets selected."
                        aria-label="No notification presets selected."
                        className="inline-flex items-center text-stone-400 transition hover:text-stone-600"
                      >
                        <HelpCircle size={12} />
                      </span>
                    )}
                  </div>
                  <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                    <select
                      value=""
                      onChange={(event) => {
                        const id = Number(event.target.value);
                        if (
                          id &&
                          !form.notification_preset_ids.includes(id)
                        ) {
                          setForm((current) => ({
                            ...current,
                            notification_preset_ids: [
                              ...current.notification_preset_ids,
                              id,
                            ],
                          }));
                        }
                      }}
                      className="app-control h-9 px-2 text-xs"
                    >
                      <option value="">Add notification preset</option>
                      {notificationPresets
                        .filter(
                          (preset) =>
                            !form.notification_preset_ids.includes(preset.id),
                        )
                        .map((preset) => (
                          <option key={preset.id} value={preset.id}>
                            {preset.name}
                          </option>
                        ))}
                    </select>
                    <span
                      title="You can attach more than one channel preset."
                      aria-label="You can attach more than one channel preset."
                      className="inline-flex items-center text-stone-400 transition hover:text-stone-600"
                    >
                      <HelpCircle size={12} />
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </SectionCard>

          <SectionCard
            title="AI settings"
            description="Optional. Enable one or both providers to enrich prompts."
            className="gap-1.5 p-2 md:p-2.5"
          >
            <div className="grid gap-2">
              <ProviderModelField
                label="Vision"
                provider={form.ai_vision_provider}
                providerOptions={[
                  { label: 'OpenAI', value: 'openai' },
                  { label: 'Gemini', value: 'gemini' },
                  { label: 'Xiaomi', value: 'xiaomi' },
                  { label: 'OpenRouter', value: 'openrouter' },
                  { label: 'Local AI', value: 'local' },
                ]}
                onProviderChange={(provider) => {
                  setForm((current) => {
                    const next = {
                      ...current,
                      ai_vision_provider: provider,
                      ai_photo_selection_enabled:
                        provider === 'none'
                          ? false
                          : current.ai_photo_selection_enabled,
                    };
                    if (provider !== 'openrouter') {
                      const opts = getVisionModelOptions(provider);
                      if (
                        !opts.some(
                          (opt) => opt.value === current.ai_vision_model,
                        )
                      ) {
                        next.ai_vision_model =
                          opts[0]?.value ?? current.ai_vision_model;
                      }
                    }
                    return next;
                  });
                }}
                model={form.ai_vision_model}
                modelOptions={visionModels}
                onModelChange={(value) =>
                  setForm((current) => ({
                    ...current,
                    ai_vision_model: value,
                  }))
                }
                freeTextProviders={['openrouter', 'local']}
                providerHelp="Used to build richer prompt context before generation."
                modelPlaceholder="e.g. your-local-model"
              />
              <ProviderModelField
                label="Image"
                provider={form.ai_image_provider}
                providerOptions={[
                  { label: 'OpenAI', value: 'openai' },
                  { label: 'Gemini', value: 'gemini' },
                  { label: 'OpenRouter', value: 'openrouter' },
                  { label: 'BytePlus', value: 'byteplus' },
                  { label: 'Local AI', value: 'local' },
                ]}
                onProviderChange={(provider) => {
                  setForm((current) => {
                    const next = {
                      ...current,
                      ai_image_provider: provider,
                    };
                    if (
                      provider !== 'openrouter' &&
                      provider !== 'byteplus'
                    ) {
                      const opts = getImageModelOptions(provider);
                      if (
                        !opts.some(
                          (opt) => opt.value === current.ai_image_model,
                        )
                      ) {
                        next.ai_image_model =
                          opts[0]?.value ?? current.ai_image_model;
                      }
                    }
                    return next;
                  });
                }}
                model={form.ai_image_model}
                modelOptions={imageModels}
                onModelChange={(value) =>
                  setForm((current) => ({
                    ...current,
                    ai_image_model: value,
                  }))
                }
                freeTextProviders={['openrouter', 'byteplus', 'local']}
                providerHelp="Set this only when you want a separate image-generation provider."
                modelPlaceholder="e.g. your-local-model"
              />
              <label
                className={`flex items-center gap-2 rounded-2xl border border-stone-200 bg-white px-2 py-1.5 text-sm font-medium text-stone-800 shadow-xs ${
                  form.ai_vision_provider === 'none' ||
                  form.ai_image_provider === 'none'
                    ? 'opacity-60'
                    : ''
                }`}
              >
                <input
                  type="checkbox"
                  checked={form.ai_prompt_enrichment}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      ai_prompt_enrichment: event.target.checked,
                    }))
                  }
                  disabled={
                    form.ai_vision_provider === 'none' ||
                    form.ai_image_provider === 'none'
                  }
                  className="h-4 w-4 rounded-sm border-stone-300 text-emerald-600 focus:ring-emerald-500"
                />
                <div className="grid gap-0.5">
                  <span>AI prompt enrichment</span>
                  <span
                    title={
                      form.ai_vision_provider === 'none' ||
                      form.ai_image_provider === 'none'
                        ? 'Enable both providers before turning this on.'
                        : 'Combine vision output with the effect prompt.'
                    }
                    aria-label={
                      form.ai_vision_provider === 'none' ||
                      form.ai_image_provider === 'none'
                        ? 'Enable both providers before turning this on.'
                        : 'Combine vision output with the effect prompt.'
                    }
                    className="inline-flex items-center text-stone-400 transition hover:text-stone-600"
                  >
                    <HelpCircle size={12} />
                  </span>
                </div>
              </label>
              <label
                className={`flex items-center gap-2 rounded-2xl border border-stone-200 bg-white px-2 py-1.5 text-sm font-medium text-stone-800 shadow-xs ${
                  form.ai_vision_provider === 'none' ? 'opacity-60' : ''
                }`}
              >
                <input
                  type="checkbox"
                  aria-label="AI photo selection"
                  checked={form.ai_photo_selection_enabled}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      ai_photo_selection_enabled: event.target.checked,
                    }))
                  }
                  disabled={form.ai_vision_provider === 'none'}
                  className="h-4 w-4 rounded-sm border-stone-300 text-emerald-600 focus:ring-emerald-500"
                />
                <div className="grid gap-0.5">
                  <span>AI photo selection</span>
                  <span className="text-xs font-normal leading-5 text-stone-500">
                    Pick the best photo from 4 candidates for
                    single-image effects.
                  </span>
                </div>
              </label>
            </div>
          </SectionCard>
        </div>
      </div>

      <div className="flex gap-2">
        <button
          type="button"
          onClick={onSave}
          disabled={!canSave || isSaving}
          className="app-button-primary flex-1 justify-center px-3 py-2 text-sm font-semibold disabled:opacity-50 sm:flex-none sm:w-auto"
        >
          <Check size={14} />
          Save
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="app-button-secondary flex-1 justify-center px-3 py-2 text-sm font-semibold sm:flex-none sm:w-auto"
        >
          <X size={14} />
          Cancel
        </button>
      </div>
    </aside>
  );
}
