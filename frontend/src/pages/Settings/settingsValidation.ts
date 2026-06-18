import { type SettingsUpdate } from '../../api/client';

export type SettingsFieldErrorKey =
  | 'immich_url'
  | 'local_ai_base_url'
  | 'ai_vision_hourly_limit'
  | 'ai_image_hourly_limit'
  | 'favorite_albums_json';

export type SettingsFieldErrors = Partial<
  Record<SettingsFieldErrorKey, string>
>;

export function isHttpUrl(value: string) {
  try {
    const parsed = new URL(value);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:';
  } catch {
    return false;
  }
}

export function validateSettingsForm(
  form: SettingsUpdate,
): SettingsFieldErrors {
  const errors: SettingsFieldErrors = {};

  if (form.immich_url && !isHttpUrl(form.immich_url)) {
    errors.immich_url =
      'Immich URL must be an absolute http:// or https:// URL.';
  }
  if (form.local_ai_base_url && !isHttpUrl(form.local_ai_base_url)) {
    errors.local_ai_base_url =
      'Local AI base URL must be an absolute http:// or https:// URL.';
  }
  if (
    !Number.isInteger(form.ai_vision_hourly_limit) ||
    form.ai_vision_hourly_limit < 1 ||
    form.ai_vision_hourly_limit > 1000
  ) {
    errors.ai_vision_hourly_limit =
      'Vision calls per hour must be between 1 and 1000.';
  }
  if (
    !Number.isInteger(form.ai_image_hourly_limit) ||
    form.ai_image_hourly_limit < 1 ||
    form.ai_image_hourly_limit > 1000
  ) {
    errors.ai_image_hourly_limit =
      'Image calls per hour must be between 1 and 1000.';
  }
  if (form.favorite_albums_json) {
    try {
      const parsed = JSON.parse(form.favorite_albums_json);
      if (!Array.isArray(parsed)) {
        errors.favorite_albums_json =
          'favorite_albums_json must be a JSON array.';
      }
    } catch {
      errors.favorite_albums_json = 'favorite_albums_json must be valid JSON.';
    }
  }

  return errors;
}

export function normalizeSettingsPayload(form: SettingsUpdate): SettingsUpdate {
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
