import { type AutomationScheduleMode } from '../automation.types';

export type FormState = {
  name: string;
  enabled: boolean;
  scheduleMode: AutomationScheduleMode;
  scheduleDays: number[];
  scheduleTime: string;
  people_preset_id: number | '';
  effect_preset_id: number | '';
  notification_preset_ids: number[];
  album_name: string;
  ai_vision_provider: string;
  ai_vision_model: string;
  ai_image_provider: string;
  ai_image_model: string;
  ai_prompt_enrichment: boolean;
  ai_photo_selection_enabled: boolean;
};

export const emptyForm: FormState = {
  name: '',
  enabled: false,
  scheduleMode: 'daily',
  scheduleDays: [],
  scheduleTime: '08:00',
  people_preset_id: '',
  effect_preset_id: '',
  notification_preset_ids: [],
  album_name: 'AI Photos',
  ai_vision_provider: 'none',
  ai_vision_model: 'gpt-4o-mini',
  ai_image_provider: 'none',
  ai_image_model: 'gpt-image-1',
  ai_prompt_enrichment: false,
  ai_photo_selection_enabled: false,
};
