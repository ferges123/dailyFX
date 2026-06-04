import type { AutomationScheduleState, AutomationScheduleMode } from './automation.types';
import { type ModificationGroupsConfig, weekdayCodeByValue, weekdayOptions } from './automation.types';

export function parseAutomationSchedule(schedule: string): AutomationScheduleState {
  const normalized = (schedule || 'weekly').trim().toLowerCase();
  if (normalized === 'daily') return { mode: 'daily', days: [], time: '' };
  if (normalized === 'weekly') return { mode: 'custom', days: [], time: '' };
  if (normalized === 'weekdays') return { mode: 'weekdays', days: [0, 1, 2, 3, 4], time: '' };
  if (normalized === 'weekends') return { mode: 'weekends', days: [5, 6], time: '' };

  const parts = normalized.split('@').map((p) => p.trim()).filter(Boolean);
  if (!parts.length) return { mode: 'custom', days: [], time: '' };

  const [mode, first, second] = parts;
  if (mode !== 'daily' && mode !== 'weekly' && mode !== 'weekdays' && mode !== 'weekends') {
    return { mode: 'custom', days: [], time: '' };
  }

  const next: AutomationScheduleState = {
    mode: mode === 'weekly' ? 'custom' : (mode as AutomationScheduleMode),
    days: [],
    time: '',
  };
  if (first) {
    if (/^(?:[01]\d|2[0-3]):[0-5]\d$/.test(first)) {
      next.time = first;
    } else {
      next.days = first
        .split(',')
        .map((d) => d.trim())
        .filter(Boolean)
        .map((d) => weekdayOptions.find((o) => o.label.toLowerCase() === d || weekdayCodeByValue[o.value] === d))
        .filter((o): o is (typeof weekdayOptions)[number] => Boolean(o))
        .map((o) => o.value);
    }
  }
  if (second && /^(?:[01]\d|2[0-3]):[0-5]\d$/.test(second)) next.time = second;
  return next;
}

export function serializeAutomationSchedule(state: AutomationScheduleState): string {
  if (state.mode === 'daily') return state.time ? `daily@${state.time}` : 'daily';
  if (state.mode === 'weekdays') return state.time ? `weekdays@${state.time}` : 'weekdays';
  if (state.mode === 'weekends') return state.time ? `weekends@${state.time}` : 'weekends';
  if (!state.days.length) return 'weekly';
  const dayCodeList = state.days.map((d) => weekdayCodeByValue[d]).join(',');
  return state.time ? `weekly@${dayCodeList}@${state.time}` : `weekly@${dayCodeList}`;
}

export function describeAutomationSchedule(state: AutomationScheduleState): string {
  if (state.mode === 'daily') return state.time ? `Runs every day at ${state.time}` : 'Runs every day';
  if (state.mode === 'weekdays') return state.time ? `Runs on weekdays at ${state.time}` : 'Runs on weekdays';
  if (state.mode === 'weekends') return state.time ? `Runs on weekends at ${state.time}` : 'Runs on weekends';
  if (!state.days.length) return 'Runs once per week';
  const label = state.days
    .map((d) => weekdayOptions.find((o) => o.value === d)?.label ?? '')
    .filter(Boolean)
    .join(', ');
  return state.time ? `Runs on ${label} at ${state.time}` : `Runs on ${label}`;
}

export function formatAutomationStatus(status: string | null): string {
  if (!status) return 'No runs yet';
  return status.split('_').filter(Boolean).map((p) => p.charAt(0).toUpperCase() + p.slice(1)).join(' ');
}

export function getAutomationStatusClass(status: string | null): string {
  if (status === 'completed') return 'border-emerald-200 bg-emerald-50 text-emerald-800';
  if (status === 'error') return 'border-rose-200 bg-rose-50 text-rose-800';
  if (!status) return 'border-stone-200 bg-white text-stone-700';
  return 'border-amber-200 bg-amber-50 text-amber-800';
}

export function createDefaultModificationGroups(): ModificationGroupsConfig {
  return {
    collage: { enabled: true, weight: 5, config: { styles: ['random'] } },
    instafilter: { enabled: true, weight: 2, config: { styles: ['random'] } },
    filmstrip: { enabled: false, weight: 1, config: {} },
    popart: { enabled: false, weight: 1, config: {} },
    duotone: { enabled: true, weight: 2, config: {} },
    halftone: { enabled: true, weight: 2, config: { cell_size: 18 } },
    glitch: { enabled: true, weight: 2, config: { shift: 12 } },
    light_leak: { enabled: true, weight: 2, config: {} },
    neon_bloom: { enabled: true, weight: 2, config: {} },
    cyanotype: { enabled: true, weight: 2, config: {} },
    polaroid: { enabled: false, weight: 1, config: {} },
    prism_split: { enabled: true, weight: 2, config: { shift: 14 } },
    paper_cutout: { enabled: true, weight: 2, config: {} },
    aerochrome: { enabled: true, weight: 2, config: { red_hue: 170, foliage_sensitivity: 20, saturation_boost: 1.3, sky_cyan_shift: '1' } },
    ai_caricature: { enabled: true, weight: 1, config: {} },
    ai_anime: { enabled: true, weight: 1, config: {} },
  };
}

export function parseModificationGroups(raw: string | null): { value: ModificationGroupsConfig; error: string | null } {
  if (!raw) return { value: createDefaultModificationGroups(), error: null };
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return { value: createDefaultModificationGroups(), error: 'Effect settings must be a JSON object.' };
    }
    return { value: { ...createDefaultModificationGroups(), ...(parsed as ModificationGroupsConfig) }, error: null };
  } catch {
    return { value: createDefaultModificationGroups(), error: 'Effect settings JSON is invalid.' };
  }
}

export function serializeModificationGroups(value: ModificationGroupsConfig): string {
  return JSON.stringify(value, null, 2);
}
