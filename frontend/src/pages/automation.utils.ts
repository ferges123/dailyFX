import type {
  AutomationScheduleState,
  AutomationScheduleMode,
} from './automation.types';
import {
  type ModificationGroupsConfig,
  weekdayCodeByValue,
  weekdayOptions,
} from './automation.types';

export function parseAutomationSchedule(
  schedule: string,
): AutomationScheduleState {
  const normalized = (schedule || 'weekly').trim().toLowerCase();
  if (normalized === 'daily') return { mode: 'daily', days: [], time: '' };
  if (normalized === 'weekly') return { mode: 'custom', days: [], time: '' };
  if (normalized === 'weekdays')
    return { mode: 'weekdays', days: [0, 1, 2, 3, 4], time: '' };
  if (normalized === 'weekends')
    return { mode: 'weekends', days: [5, 6], time: '' };

  const parts = normalized
    .split('@')
    .map((p) => p.trim())
    .filter(Boolean);
  if (!parts.length) return { mode: 'custom', days: [], time: '' };

  const [mode, first, second] = parts;
  if (
    mode !== 'daily' &&
    mode !== 'weekly' &&
    mode !== 'weekdays' &&
    mode !== 'weekends'
  ) {
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
        .map((d) =>
          weekdayOptions.find(
            (o) =>
              o.label.toLowerCase() === d || weekdayCodeByValue[o.value] === d,
          ),
        )
        .filter((o): o is (typeof weekdayOptions)[number] => Boolean(o))
        .map((o) => o.value);
    }
  }
  if (second && /^(?:[01]\d|2[0-3]):[0-5]\d$/.test(second)) next.time = second;
  return next;
}

export function serializeAutomationSchedule(
  state: AutomationScheduleState,
): string {
  if (state.mode === 'daily')
    return state.time ? `daily@${state.time}` : 'daily';
  if (state.mode === 'weekdays')
    return state.time ? `weekdays@${state.time}` : 'weekdays';
  if (state.mode === 'weekends')
    return state.time ? `weekends@${state.time}` : 'weekends';
  if (!state.days.length) return 'weekly';
  const dayCodeList = state.days.map((d) => weekdayCodeByValue[d]).join(',');
  return state.time
    ? `weekly@${dayCodeList}@${state.time}`
    : `weekly@${dayCodeList}`;
}

export function describeAutomationSchedule(
  state: AutomationScheduleState,
): string {
  if (state.mode === 'daily')
    return state.time ? `Runs every day at ${state.time}` : 'Runs every day';
  if (state.mode === 'weekdays')
    return state.time
      ? `Runs on weekdays at ${state.time}`
      : 'Runs on weekdays';
  if (state.mode === 'weekends')
    return state.time
      ? `Runs on weekends at ${state.time}`
      : 'Runs on weekends';
  if (!state.days.length) return 'Runs once per week';
  const label = state.days
    .map((d) => weekdayOptions.find((o) => o.value === d)?.label ?? '')
    .filter(Boolean)
    .join(', ');
  return state.time ? `Runs on ${label} at ${state.time}` : `Runs on ${label}`;
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
    aerochrome: {
      enabled: true,
      weight: 2,
      config: {
        red_hue: 170,
        foliage_sensitivity: 20,
        saturation_boost: 1.3,
        sky_cyan_shift: '1',
      },
    },
    apple_weather: { enabled: false, weight: 1, config: {} },
    instaweather: { enabled: false, weight: 1, config: {} },
    bokeh_blur: { enabled: false, weight: 1, config: {} },
    vintage_film: { enabled: false, weight: 1, config: {} },
    huji: { enabled: false, weight: 1, config: {} },
    pencil_sketch: { enabled: false, weight: 1, config: {} },
    cartoon: { enabled: false, weight: 1, config: {} },
    hdr: { enabled: false, weight: 1, config: {} },
    ai_anime: { enabled: true, weight: 1, config: {} },
    ai_brick_built_figure: { enabled: false, weight: 1, config: {} },
    ai_caricature: { enabled: true, weight: 1, config: {} },
    ai_cinematic_3d_toy: { enabled: false, weight: 1, config: {} },
    ai_claymation: { enabled: false, weight: 1, config: {} },
    ai_collectible_figure: { enabled: false, weight: 1, config: {} },
    ai_comic_book: { enabled: false, weight: 1, config: {} },
    ai_cyberpunk: { enabled: false, weight: 1, config: {} },
    ai_fantasy_hero: { enabled: false, weight: 1, config: {} },
    ai_high_fashion_editorial: { enabled: false, weight: 1, config: {} },
    ai_yearbook_90s: { enabled: false, weight: 1, config: {} },
    ai_celebrity_red_carpet: { enabled: false, weight: 1, config: {} },
    ai_film_noir_portrait: { enabled: false, weight: 1, config: {} },
    ai_mugshot: { enabled: false, weight: 1, config: {} },
    ai_celebrity_mugshot: { enabled: false, weight: 1, config: {} },
    ai_gangster_mugshot: { enabled: false, weight: 1, config: {} },
    ai_space_explorer: { enabled: false, weight: 1, config: {} },
    ai_superhero: { enabled: false, weight: 1, config: {} },
    ai_post_apocalyptic: { enabled: false, weight: 1, config: {} },
    ai_low_poly_3d: { enabled: false, weight: 1, config: {} },
    ai_zombie: { enabled: false, weight: 1, config: {} },
    ai_caveman: { enabled: false, weight: 1, config: {} },
    ai_watercolor_postcard: { enabled: false, weight: 1, config: {} },
    ai_vintage_travel_poster: { enabled: false, weight: 1, config: {} },
    ai_yellow_cartoon_sitcom: { enabled: false, weight: 1, config: {} },
    ai_renaissance_oil: { enabled: false, weight: 1, config: {} },
    ai_stained_glass: { enabled: false, weight: 1, config: {} },
    ai_vaporwave_nostalgia: { enabled: false, weight: 1, config: {} },
    ai_gta_loading_screen: { enabled: false, weight: 1, config: {} },
    ai_pixel_rpg_8bit: { enabled: false, weight: 1, config: {} },
    ai_voxel_3d: { enabled: false, weight: 1, config: {} },
    ai_corporate_headshot: { enabled: false, weight: 1, config: {} },
    ai_double_exposure: { enabled: false, weight: 1, config: {} },
    ai_cinematic_movie_still: { enabled: false, weight: 1, config: {} },
    ai_polaroid_memory: { enabled: false, weight: 1, config: {} },
    ai_editorial_black_white: { enabled: false, weight: 1, config: {} },
    ai_album_cover: { enabled: false, weight: 1, config: {} },
    ai_dreamy_golden_hour: { enabled: false, weight: 1, config: {} },
    ai_snow_globe: { enabled: false, weight: 1, config: {} },
    ai_ancient_statue: { enabled: false, weight: 1, config: {} },
    ai_newspaper_archive: { enabled: false, weight: 1, config: {} },
    ai_fairytale_storybook: { enabled: false, weight: 1, config: {} },
    ai_luxury_perfume_ad: { enabled: false, weight: 1, config: {} },
    ai_magazine_cover_no_text: { enabled: false, weight: 1, config: {} },
    ai_spy_thriller_poster: { enabled: false, weight: 1, config: {} },
    ai_royal_portrait: { enabled: false, weight: 1, config: {} },
    ai_medieval_tapestry: { enabled: false, weight: 1, config: {} },
    ai_paper_diorama: { enabled: false, weight: 1, config: {} },
    ai_tintype_portrait: { enabled: false, weight: 1, config: {} },
    ai_film_contact_sheet: { enabled: false, weight: 1, config: {} },
    ai_ukiyo_e_print: { enabled: false, weight: 1, config: {} },
    ai_solarpunk: { enabled: false, weight: 1, config: {} },
    ai_underwater_dream: { enabled: false, weight: 1, config: {} },
    ai_miniature_train_set: { enabled: false, weight: 1, config: {} },
    ai_80s_action_movie: { enabled: false, weight: 1, config: {} },
    ai_old_master_pastel: { enabled: false, weight: 1, config: {} },
    ai_documentary_photoessay: { enabled: false, weight: 1, config: {} },
    ai_museum_diorama: { enabled: false, weight: 1, config: {} },
    ai_anime_chibi: { enabled: false, weight: 1, config: {} },
    ai_anime_ghibli_inspired: { enabled: false, weight: 1, config: {} },
    ai_bauhaus_poster: { enabled: false, weight: 1, config: {} },
    ai_comic_noir: { enabled: false, weight: 1, config: {} },
    ai_cubist_portrait: { enabled: false, weight: 1, config: {} },
    ai_expressionist_portrait: { enabled: false, weight: 1, config: {} },
    ai_linocut_print: { enabled: false, weight: 1, config: {} },
    ai_minimalist_poster: { enabled: false, weight: 1, config: {} },
    ai_papercut_shadowbox: { enabled: false, weight: 1, config: {} },
    ai_pop_art: { enabled: false, weight: 1, config: {} },
    ai_retro_arcade: { enabled: false, weight: 1, config: {} },
    ai_ukiyo_e_modern: { enabled: false, weight: 1, config: {} },
    ai_retro_futurism: { enabled: false, weight: 1, config: {} },
    ai_art_nouveau: { enabled: false, weight: 1, config: {} },
    ai_street_art_stencil: { enabled: false, weight: 1, config: {} },
    ai_cybernetic_upgrade: { enabled: false, weight: 1, config: {} },
    ai_sand_sculpture: { enabled: false, weight: 1, config: {} },
    museum_archive: { enabled: true, weight: 3, config: {} },
  };
}

export function parseModificationGroups(raw: string | null): {
  value: ModificationGroupsConfig;
  error: string | null;
} {
  if (!raw) return { value: createDefaultModificationGroups(), error: null };
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return {
        value: createDefaultModificationGroups(),
        error: 'Effect settings must be a JSON object.',
      };
    }
    return {
      value: {
        ...createDefaultModificationGroups(),
        ...(parsed as ModificationGroupsConfig),
      },
      error: null,
    };
  } catch {
    return {
      value: createDefaultModificationGroups(),
      error: 'Effect settings JSON is invalid.',
    };
  }
}
