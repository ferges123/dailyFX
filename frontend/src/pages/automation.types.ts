import type { GenerationModuleInfo } from '../api/client';

export type AutomationScheduleMode = 'daily' | 'weekdays' | 'weekends' | 'custom';

export type AutomationScheduleState = {
  mode: AutomationScheduleMode;
  days: number[];
  time: string;
};

export type ModificationGroupConfig = {
  enabled: boolean;
  weight: number;
  config: {
    asset_count?: number;
    styles?: string[];
    [key: string]: unknown;
  };
  [key: string]: unknown;
};

export type ModificationGroupsConfig = Record<string, ModificationGroupConfig>;

export const weekdayOptions = [
  { label: 'Mon', value: 0 },
  { label: 'Tue', value: 1 },
  { label: 'Wed', value: 2 },
  { label: 'Thu', value: 3 },
  { label: 'Fri', value: 4 },
  { label: 'Sat', value: 5 },
  { label: 'Sun', value: 6 },
] as const;

export const weekdayCodeByValue: Record<number, string> = {
  0: 'mon', 1: 'tue', 2: 'wed', 3: 'thu', 4: 'fri', 5: 'sat', 6: 'sun',
};

export const automationScheduleModeOptions: Array<{ label: string; value: AutomationScheduleMode }> = [
  { label: 'Every day', value: 'daily' },
  { label: 'Weekdays', value: 'weekdays' },
  { label: 'Weekends', value: 'weekends' },
  { label: 'Custom days', value: 'custom' },
];

const instagramFilterValues = [
  'random', '_1977', 'aden', 'brannan', 'brooklyn', 'clarendon', 'earlybird',
  'gingham', 'hudson', 'inkwell', 'kelvin', 'lark', 'lofi', 'maven', 'mayfair',
  'moon', 'nashville', 'perpetua', 'reyes', 'rise', 'slumber', 'stinson',
  'toaster', 'valencia', 'walden', 'willow', 'xpro2',
];

function createFilterOptions(filters: string[]) {
  return filters.map((value) => ({ label: value, value }));
}

export type ModulePreset = { label: string; config: Record<string, unknown> };

export const MODULE_PRESETS: Record<string, ModulePreset[]> = {
  collage: [
    { label: 'Random', config: { styles: ['random'] } },
    { label: 'Warm', config: { styles: ['clarendon', 'kelvin', 'valencia', 'rise'] } },
    { label: 'Moody', config: { styles: ['moon', 'inkwell', 'lofi', 'brannan'] } },
    { label: 'Vivid', config: { styles: ['xpro2', 'mayfair', 'hudson', 'earlybird'] } },
  ],
  instafilter: [
    { label: 'Random', config: { styles: ['random'] } },
    { label: 'Classic', config: { styles: ['clarendon', 'lark', 'valencia', 'gingham'] } },
    { label: 'B&W', config: { styles: ['moon', 'inkwell', 'willow'] } },
    { label: 'Retro', config: { styles: ['_1977', 'earlybird', 'nashville', 'brannan'] } },
  ],
  halftone: [
    { label: 'Fine', config: { cell_size: 8 } },
    { label: 'Default', config: { cell_size: 18 } },
    { label: 'Coarse', config: { cell_size: 40 } },
  ],
  glitch: [
    { label: 'Subtle', config: { shift: 5 } },
    { label: 'Default', config: { shift: 12 } },
    { label: 'Heavy', config: { shift: 28 } },
  ],
  prism_split: [
    { label: 'Subtle', config: { shift: 5 } },
    { label: 'Default', config: { shift: 14 } },
    { label: 'Heavy', config: { shift: 28 } },
  ],
};

export const fallbackModules: GenerationModuleInfo[] = [
  {
    name: 'collage', label: 'Collage', description: 'Four-filter collage from a single photo.',
    default_weight: 5, default_config: { styles: ['random'] },
    config_schema: [{ key: 'styles', label: 'Styles', type: 'multiselect', description: 'Pick the filters used across collage tiles.', options: createFilterOptions(instagramFilterValues) }],
  },
  {
    name: 'instafilter', label: 'Instafilter', description: 'Single-photo Instagram-style filter.',
    default_weight: 2, default_config: { styles: ['random'] },
    config_schema: [{ key: 'styles', label: 'Allowed filters', type: 'multiselect', description: 'Choose which filters may be picked at run time.', options: createFilterOptions(instagramFilterValues) }],
  },
  {
    name: 'apple_weather', label: 'Apple Weather', description: 'Apple-style weather card with frosted glass and clean typography.',
    default_weight: 2, default_config: { units: 'celsius', protect_faces: 'true' },
    config_schema: [
      { key: 'units', label: 'Temperature Unit', type: 'select', description: 'Units to show temperature.', options: [{ label: 'Celsius (°C)', value: 'celsius' }, { label: 'Fahrenheit (°F)', value: 'fahrenheit' }], default: 'celsius' },
      { key: 'protect_faces', label: 'Face protection', type: 'select', description: 'Shift the card to avoid detected faces.', options: [{ label: 'Enabled', value: 'true' }, { label: 'Disabled', value: 'false' }], default: 'true' },
    ],
  },
  { name: 'filmstrip', label: 'Filmstrip', description: 'Retro filmstrip layout with date and time labels.', default_weight: 1, default_config: {}, config_schema: [] },
  { name: 'popart', label: 'Pop Art', description: 'Four-tile pop-art collage with vivid color palettes.', default_weight: 1, default_config: {}, config_schema: [] },
  { name: 'duotone', label: 'Duotone', description: 'High-contrast duotone grading with grain and vignette.', default_weight: 2, default_config: {}, config_schema: [] },
  { name: 'halftone', label: 'Halftone', description: 'Dot-matrix halftone posterization.', default_weight: 2, default_config: { cell_size: 18 }, config_schema: [{ key: 'cell_size', label: 'Cell size', type: 'number', description: 'Larger values create coarser dots.', min: 8, max: 64, step: 1, default: 18 }] },
  { name: 'glitch', label: 'Glitch', description: 'Chromatic glitch with scanlines and row shifting.', default_weight: 2, default_config: { shift: 12 }, config_schema: [{ key: 'shift', label: 'Shift', type: 'number', description: 'Maximum horizontal channel displacement in pixels.', min: 3, max: 32, step: 1, default: 12 }] },
  { name: 'light_leak', label: 'Light Leak', description: 'Warm film leak overlay with faded contrast.', default_weight: 2, default_config: {}, config_schema: [] },
  { name: 'neon_bloom', label: 'Neon Bloom', description: 'Bright bloom effect with vivid neon tones.', default_weight: 2, default_config: {}, config_schema: [] },
  { name: 'cyanotype', label: 'Cyanotype', description: 'Blue-print toning with paper grain and a soft vignette.', default_weight: 2, default_config: {}, config_schema: [] },
  { name: 'polaroid', label: 'Polaroid', description: 'Instant-film frame with a warm fade and caption strip.', default_weight: 1, default_config: {}, config_schema: [] },
  { name: 'prism_split', label: 'Prism Split', description: 'Chromatic split with diagonal glare and crisp contrast.', default_weight: 2, default_config: { shift: 14 }, config_schema: [{ key: 'shift', label: 'Shift', type: 'number', description: 'Maximum chromatic offset in pixels.', min: 3, max: 32, step: 1, default: 14 }] },
  { name: 'paper_cutout', label: 'Paper Cutout', description: 'Posterized cutout on a textured paper backdrop.', default_weight: 2, default_config: {}, config_schema: [] },
  {
    name: 'aerochrome', label: 'Kodak Aerochrome', description: 'Infrared film simulation turning green foliage into vivid red/pink, with cool teal skies.',
    default_weight: 2, default_config: { red_hue: 170, foliage_sensitivity: 20, saturation_boost: 1.3, sky_cyan_shift: '1' },
    config_schema: [
      { key: 'red_hue', label: 'Red/Pink Hue', type: 'number', description: 'Foliage hue target (140 = Pink, 170 = Crimson, 180 = Deep Red).', min: 140, max: 180, step: 5, default: 170 },
      { key: 'foliage_sensitivity', label: 'Green Sensitivity', type: 'number', description: 'Foliage detection range (10 = narrow, 30 = wide).', min: 10, max: 30, step: 2, default: 20 },
      { key: 'saturation_boost', label: 'Vibrancy Boost', type: 'number', description: 'Red foliage saturation multiplier.', min: 1.0, max: 1.8, step: 0.1, default: 1.3 },
      { key: 'sky_cyan_shift', label: 'Teal Skies', type: 'select', description: 'Shift blue skies towards a cool retro cyan/teal.', options: [{ label: 'Enabled', value: '1' }, { label: 'Disabled', value: '0' }], default: '1' }
    ]
  },
  { name: 'ai_caricature', label: 'AI Caricature', description: 'Uses the default AI provider to turn a photo into a caricature.', default_weight: 1, default_config: {}, config_schema: [] },
  { name: 'ai_anime', label: 'AI Anime', description: 'Uses the default AI provider to turn a photo into anime-style art.', default_weight: 1, default_config: {}, config_schema: [] },
  { name: 'ai_cinematic_3d_toy', label: 'AI Cinematic 3D Toy', description: 'Uses the default AI provider to turn a photo into a polished cinematic 3D toy-style portrait.', default_weight: 1, default_config: {}, config_schema: [] },
  { name: 'ai_collectible_figure', label: 'AI Collectible Hero Figure', description: 'Uses the default AI provider to turn a photo into a premium collectible hero figure portrait.', default_weight: 1, default_config: {}, config_schema: [] },
  { name: 'ai_fantasy_hero', label: 'AI Fantasy Hero', description: 'Uses the default AI provider to turn a photo into an epic fantasy portrait.', default_weight: 1, default_config: {}, config_schema: [] },
  { name: 'ai_high_fashion_editorial', label: 'AI High-Fashion Editorial', description: 'Uses the default AI provider to turn a photo into a luxury editorial portrait.', default_weight: 1, default_config: {}, config_schema: [] },
  { name: 'ai_film_noir_portrait', label: 'AI Film Noir Portrait', description: 'Uses the default AI provider to turn a photo into a dramatic noir portrait.', default_weight: 1, default_config: {}, config_schema: [] },
  { name: 'ai_watercolor_postcard', label: 'AI Watercolor Postcard', description: 'Uses the default AI provider to turn a photo into a soft watercolor postcard illustration.', default_weight: 1, default_config: {}, config_schema: [] },
  { name: 'ai_vintage_travel_poster', label: 'AI Vintage Travel Poster', description: 'Uses the default AI provider to turn a photo into a retro travel poster.', default_weight: 1, default_config: {}, config_schema: [] },
  { name: 'ai_brick_built_figure', label: 'AI Brick-Built Figure', description: 'Uses the default AI provider to turn a photo into a playful brick-built character scene.', default_weight: 1, default_config: {}, config_schema: [] },
  { name: 'ai_yellow_cartoon_sitcom', label: 'AI Yellow Cartoon Sitcom', description: 'Uses the default AI provider to turn a photo into a bright cartoon family-comedy portrait.', default_weight: 1, default_config: {}, config_schema: [] },
  { name: 'museum_archive', label: 'Museum Archive', description: 'Fine-art gallery framing with elegant serif typography and passe-partout.', default_weight: 3, default_config: {}, config_schema: [] },
];
