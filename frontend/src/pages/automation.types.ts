import type { GenerationModuleInfo } from '../api/client';

export type AutomationScheduleMode =
  | 'daily'
  | 'weekdays'
  | 'weekends'
  | 'custom';

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
  0: 'mon',
  1: 'tue',
  2: 'wed',
  3: 'thu',
  4: 'fri',
  5: 'sat',
  6: 'sun',
};

export const automationScheduleModeOptions: Array<{
  label: string;
  value: AutomationScheduleMode;
}> = [
  { label: 'Every day', value: 'daily' },
  { label: 'Weekdays', value: 'weekdays' },
  { label: 'Weekends', value: 'weekends' },
  { label: 'Custom days', value: 'custom' },
];

const instagramFilterValues = [
  'random',
  '_1977',
  'aden',
  'brannan',
  'brooklyn',
  'clarendon',
  'earlybird',
  'gingham',
  'hudson',
  'inkwell',
  'kelvin',
  'lark',
  'lofi',
  'maven',
  'mayfair',
  'moon',
  'nashville',
  'perpetua',
  'reyes',
  'rise',
  'slumber',
  'stinson',
  'toaster',
  'valencia',
  'walden',
  'willow',
  'xpro2',
];

function createFilterOptions(filters: string[]) {
  return filters.map((value) => ({ label: value, value }));
}

export type ModulePreset = { label: string; config: Record<string, unknown> };

export const MODULE_PRESETS: Record<string, ModulePreset[]> = {
  collage: [
    { label: 'Random', config: { styles: ['random'] } },
    {
      label: 'Warm',
      config: { styles: ['clarendon', 'kelvin', 'valencia', 'rise'] },
    },
    {
      label: 'Moody',
      config: { styles: ['moon', 'inkwell', 'lofi', 'brannan'] },
    },
    {
      label: 'Vivid',
      config: { styles: ['xpro2', 'mayfair', 'hudson', 'earlybird'] },
    },
  ],
  instafilter: [
    { label: 'Random', config: { styles: ['random'] } },
    {
      label: 'Classic',
      config: { styles: ['clarendon', 'lark', 'valencia', 'gingham'] },
    },
    { label: 'B&W', config: { styles: ['moon', 'inkwell', 'willow'] } },
    {
      label: 'Retro',
      config: { styles: ['_1977', 'earlybird', 'nashville', 'brannan'] },
    },
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
    name: 'collage',
    label: 'Collage',
    description: 'Four-filter collage from a single photo.',
    display_group: 'Poster',
    default_weight: 5,
    default_config: { styles: ['random'] },
    config_schema: [
      {
        key: 'styles',
        label: 'Styles',
        type: 'multiselect',
        description: 'Pick the filters used across collage tiles.',
        options: createFilterOptions(instagramFilterValues),
      },
    ],
  },
  {
    name: 'instafilter',
    label: 'Instafilter',
    description: 'Single-photo Instagram-style filter.',
    display_group: 'Photography',
    default_weight: 2,
    default_config: { styles: ['random'] },
    config_schema: [
      {
        key: 'styles',
        label: 'Allowed filters',
        type: 'multiselect',
        description: 'Choose which filters may be picked at run time.',
        options: createFilterOptions(instagramFilterValues),
      },
    ],
  },
  {
    name: 'apple_weather',
    label: 'Apple Weather',
    description:
      'Apple-style weather card with frosted glass and clean typography.',
    display_group: 'Portrait',
    default_weight: 2,
    default_config: { units: 'celsius', protect_faces: 'true' },
    config_schema: [
      {
        key: 'units',
        label: 'Temperature Unit',
        type: 'select',
        description: 'Units to show temperature.',
        options: [
          { label: 'Celsius (°C)', value: 'celsius' },
          { label: 'Fahrenheit (°F)', value: 'fahrenheit' },
        ],
        default: 'celsius',
      },
      {
        key: 'protect_faces',
        label: 'Face protection',
        type: 'select',
        description: 'Shift the card to avoid detected faces.',
        options: [
          { label: 'Enabled', value: 'true' },
          { label: 'Disabled', value: 'false' },
        ],
        default: 'true',
      },
    ],
  },
  {
    name: 'instaweather',
    label: 'InstaWeather',
    description: 'Instagram-style weather and location overlay card.',
    display_group: 'Portrait',
    default_weight: 2,
    default_config: {
      layout_style: 'classic',
      units: 'celsius',
      protect_faces: 'true',
    },
    config_schema: [
      {
        key: 'layout_style',
        label: 'Layout Style',
        type: 'select',
        description: 'Visual theme of the watermark overlay card.',
        options: [
          { label: 'Classic (Inter Sans)', value: 'classic' },
          { label: 'Postcard (Playfair Serif)', value: 'postcard' },
        ],
        default: 'classic',
      },
      {
        key: 'units',
        label: 'Temperature Unit',
        type: 'select',
        description: 'Units to show temperature.',
        options: [
          { label: 'Celsius (°C)', value: 'celsius' },
          { label: 'Fahrenheit (°F)', value: 'fahrenheit' },
        ],
        default: 'celsius',
      },
      {
        key: 'protect_faces',
        label: 'Face protection',
        type: 'select',
        description:
          'Auto-shift the watermark overlay to avoid covering detected faces.',
        options: [
          { label: 'Enabled', value: 'true' },
          { label: 'Disabled', value: 'false' },
        ],
        default: 'true',
      },
    ],
  },
  {
    name: 'filmstrip',
    label: 'Filmstrip',
    description: 'Retro filmstrip layout with date and time labels.',
    display_group: 'Photography',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'popart',
    label: 'Pop Art',
    description: 'Four-tile pop-art collage with vivid color palettes.',
    display_group: 'Artistic',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'duotone',
    label: 'Duotone',
    description: 'High-contrast duotone grading with grain and vignette.',
    display_group: 'Artistic',
    default_weight: 2,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'halftone',
    label: 'Halftone',
    description: 'Dot-matrix halftone posterization.',
    display_group: 'Artistic',
    default_weight: 2,
    default_config: { cell_size: 18 },
    config_schema: [
      {
        key: 'cell_size',
        label: 'Cell size',
        type: 'number',
        description: 'Larger values create coarser dots.',
        min: 8,
        max: 64,
        step: 1,
        default: 18,
      },
    ],
  },
  {
    name: 'glitch',
    label: 'Glitch',
    description: 'Chromatic glitch with scanlines and row shifting.',
    display_group: 'Artistic',
    default_weight: 2,
    default_config: { shift: 12 },
    config_schema: [
      {
        key: 'shift',
        label: 'Shift',
        type: 'number',
        description: 'Maximum horizontal channel displacement in pixels.',
        min: 3,
        max: 32,
        step: 1,
        default: 12,
      },
    ],
  },
  {
    name: 'light_leak',
    label: 'Light Leak',
    description: 'Warm film leak overlay with faded contrast.',
    display_group: 'Photography',
    default_weight: 2,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'neon_bloom',
    label: 'Neon Bloom',
    description: 'Bright bloom effect with vivid neon tones.',
    display_group: 'Artistic',
    default_weight: 2,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'cyanotype',
    label: 'Cyanotype',
    description: 'Blue-print toning with paper grain and a soft vignette.',
    display_group: 'Photography',
    default_weight: 2,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'polaroid',
    label: 'Polaroid',
    description: 'Instant-film frame with a warm fade and caption strip.',
    display_group: 'Photography',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'prism_split',
    label: 'Prism Split',
    description: 'Chromatic split with diagonal glare and crisp contrast.',
    display_group: 'Photography',
    default_weight: 2,
    default_config: { shift: 14 },
    config_schema: [
      {
        key: 'shift',
        label: 'Shift',
        type: 'number',
        description: 'Maximum chromatic offset in pixels.',
        min: 3,
        max: 32,
        step: 1,
        default: 14,
      },
    ],
  },
  {
    name: 'paper_cutout',
    label: 'Paper Cutout',
    description: 'Posterized cutout on a textured paper backdrop.',
    display_group: 'Artistic',
    default_weight: 2,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'aerochrome',
    label: 'Kodak Aerochrome',
    description:
      'Infrared film simulation turning green foliage into vivid red/pink, with cool teal skies.',
    display_group: 'Photography',
    default_weight: 2,
    default_config: {
      red_hue: 170,
      foliage_sensitivity: 20,
      saturation_boost: 1.3,
      sky_cyan_shift: '1',
    },
    config_schema: [
      {
        key: 'red_hue',
        label: 'Red/Pink Hue',
        type: 'number',
        description:
          'Foliage hue target (140 = Pink, 170 = Crimson, 180 = Deep Red).',
        min: 140,
        max: 180,
        step: 5,
        default: 170,
      },
      {
        key: 'foliage_sensitivity',
        label: 'Green Sensitivity',
        type: 'number',
        description: 'Foliage detection range (10 = narrow, 30 = wide).',
        min: 10,
        max: 30,
        step: 2,
        default: 20,
      },
      {
        key: 'saturation_boost',
        label: 'Vibrancy Boost',
        type: 'number',
        description: 'Red foliage saturation multiplier.',
        min: 1.0,
        max: 1.8,
        step: 0.1,
        default: 1.3,
      },
      {
        key: 'sky_cyan_shift',
        label: 'Teal Skies',
        type: 'select',
        description: 'Shift blue skies towards a cool retro cyan/teal.',
        options: [
          { label: 'Enabled', value: '1' },
          { label: 'Disabled', value: '0' },
        ],
        default: '1',
      },
    ],
  },
  {
    name: 'ai_anime',
    label: 'AI Anime',
    description:
      'Uses the default AI provider to turn a photo into anime-style art.',
    display_group: 'Illustration',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_brick_built_figure',
    label: 'AI Brick-Built Figure',
    description:
      'Uses the default AI provider to turn a photo into a playful brick-built character scene.',
    display_group: '3D / Toy',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_caricature',
    label: 'AI Caricature',
    description:
      'Uses the default AI provider to turn a photo into a caricature.',
    display_group: 'Portrait',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_cinematic_3d_toy',
    label: 'AI Cinematic 3D Toy',
    description:
      'Uses the default AI provider to turn a photo into a polished cinematic 3D toy-style portrait.',
    display_group: '3D / Toy',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_claymation',
    label: 'AI Claymation',
    description:
      'Uses the default AI provider to turn a photo into plasticine stop-motion clay art.',
    display_group: '3D / Toy',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_collectible_figure',
    label: 'AI Collectible Hero Figure',
    description:
      'Uses the default AI provider to turn a photo into a premium collectible hero figure portrait.',
    display_group: '3D / Toy',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_comic_book',
    label: 'AI Comic Book',
    description:
      'Uses the default AI provider to turn a photo into a retro comic book illustration.',
    display_group: 'Illustration',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_cyberpunk',
    label: 'AI Cyberpunk',
    description:
      'Uses the default AI provider to turn a photo into a neon-soaked cyberpunk artwork.',
    display_group: 'Illustration',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_fantasy_hero',
    label: 'AI Fantasy Hero',
    description:
      'Uses the default AI provider to turn a photo into an epic fantasy portrait.',
    display_group: 'Portrait',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_high_fashion_editorial',
    label: 'AI High-Fashion Editorial',
    description:
      'Uses the default AI provider to turn a photo into a luxury editorial portrait.',
    display_group: 'Portrait',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_yearbook_90s',
    label: 'AI Yearbook 90s',
    description:
      'Uses the default AI provider to turn a photo into an authentic 1990s yearbook portrait.',
    display_group: 'Portrait',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_celebrity_red_carpet',
    label: 'AI Celebrity Red Carpet',
    description:
      'Uses the default AI provider to stage a photo as a glamorous red carpet appearance.',
    display_group: 'Portrait',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_film_noir_portrait',
    label: 'AI Film Noir Portrait',
    description:
      'Uses the default AI provider to turn a photo into a dramatic noir portrait.',
    display_group: 'Portrait',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_mugshot',
    label: 'AI Mugshot',
    description:
      'Uses the default AI provider to stage a photo as a realistic police booking portrait.',
    display_group: 'Portrait',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_celebrity_mugshot',
    label: 'AI Celebrity Mugshot',
    description:
      'Uses the default AI provider to stage a photo as a viral celebrity booking portrait.',
    display_group: 'Portrait',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_gangster_mugshot',
    label: 'AI Gangster Mugshot',
    description:
      'Uses the default AI provider to stage a photo as a cinematic crime-drama mugshot.',
    display_group: 'Portrait',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_space_explorer',
    label: 'AI Space Explorer',
    description:
      'Uses the default AI provider to turn a photo into a cinematic space exploration scene.',
    display_group: 'Sci-Fi',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_superhero',
    label: 'AI Superhero',
    description:
      'Uses the default AI provider to turn a photo into a blockbuster superhero portrait.',
    display_group: 'Pop Culture',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_post_apocalyptic',
    label: 'AI Post-Apocalyptic',
    description:
      'Uses the default AI provider to turn a photo into a cinematic survivor portrait.',
    display_group: 'Cinematic',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_low_poly_3d',
    label: 'AI Low Poly 3D',
    description:
      'Uses the default AI provider to turn a photo into stylized low-poly 3D art.',
    display_group: '3D / Toy',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_zombie',
    label: 'AI Zombie',
    description:
      'Uses the default AI provider to create a cinematic zombie transformation.',
    display_group: 'Horror',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_caveman',
    label: 'AI Caveman',
    description:
      'Uses the default AI provider to turn a photo into a prehistoric portrait.',
    display_group: 'Historical',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_watercolor_postcard',
    label: 'AI Watercolor Postcard',
    description:
      'Uses the default AI provider to turn a photo into a soft watercolor postcard illustration.',
    display_group: 'Illustration',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_vintage_travel_poster',
    label: 'AI Vintage Travel Poster',
    description:
      'Uses the default AI provider to turn a photo into a retro travel poster.',
    display_group: 'Poster',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_yellow_cartoon_sitcom',
    label: 'AI Yellow Cartoon Sitcom',
    description:
      'Uses the default AI provider to turn a photo into a bright cartoon family-comedy portrait.',
    display_group: 'Pop Culture',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_renaissance_oil',
    label: 'AI Renaissance Oil',
    description:
      'Transforms the photo into a classic Renaissance oil painting on canvas.',
    display_group: 'Artistic',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_stained_glass',
    label: 'AI Stained Glass',
    description:
      'Turns the photo into a colorful medieval gothic stained glass window.',
    display_group: 'Artistic',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_vaporwave_nostalgia',
    label: 'AI Vaporwave Nostalgia',
    description:
      'Applies a nostalgic 80s/90s vaporwave aesthetic with neon grid and VHS scanlines.',
    display_group: 'Artistic',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_gta_loading_screen',
    label: 'AI GTA Loading Screen',
    description:
      'Turns the photo into high-contrast GTA-style loading screen vector art.',
    display_group: 'Pop Culture',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_pixel_rpg_8bit',
    label: 'AI Pixel RPG 8-Bit',
    description:
      'Transforms the photo into a retro 16-bit pixel art character and scene.',
    display_group: 'Illustration',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_voxel_3d',
    label: 'AI Voxel 3D',
    description:
      'Transforms the photo into a 3D isometric voxel art block model.',
    display_group: '3D / Toy',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_corporate_headshot',
    label: 'AI Corporate Headshot',
    description:
      'Transforms a casual photo into a professional business portrait for LinkedIn.',
    display_group: 'Portrait',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_double_exposure',
    label: 'AI Double Exposure',
    description:
      'Blends the silhouette of the person with a majestic misty forest and mountains.',
    display_group: 'Portrait',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_cinematic_movie_still',
    label: 'AI Cinematic Movie Still',
    description: 'Turns a photo into a dramatic cinematic film still.',
    display_group: 'Cinematic',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_polaroid_memory',
    label: 'AI Polaroid Memory',
    description: 'Turns a photo into a nostalgic instant-film memory.',
    display_group: 'Photography',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_editorial_black_white',
    label: 'AI Editorial Black & White',
    description: 'Creates a clean modern black-and-white editorial portrait.',
    display_group: 'Photography',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_album_cover',
    label: 'AI Album Cover',
    description: 'Stages a photo as a dramatic text-free music album cover.',
    display_group: 'Poster',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_dreamy_golden_hour',
    label: 'AI Dreamy Golden Hour',
    description: 'Adds a photorealistic warm golden-hour portrait look.',
    display_group: 'Photography',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_snow_globe',
    label: 'AI Snow Globe',
    description: 'Turns a photo into a miniature winter snow-globe diorama.',
    display_group: 'Seasonal',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_ancient_statue',
    label: 'AI Ancient Statue',
    description:
      'Reimagines a photo as a museum-quality marble or bronze statue.',
    display_group: 'Artistic',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_newspaper_archive',
    label: 'AI Newspaper Archive',
    description: 'Turns a photo into an archival newspaper press image.',
    display_group: 'Historical',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_fairytale_storybook',
    label: 'AI Fairytale Storybook',
    description:
      'Turns a photo into a soft classic fairytale storybook illustration.',
    display_group: 'Illustration',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_luxury_perfume_ad',
    label: 'AI Luxury Perfume Ad',
    description:
      'Stages a photo as a text-free luxury fragrance campaign portrait.',
    display_group: 'Portrait',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_magazine_cover_no_text',
    label: 'AI Magazine Cover No Text',
    description:
      'Creates a premium magazine-cover portrait without typography.',
    display_group: 'Portrait',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_spy_thriller_poster',
    label: 'AI Spy Thriller Poster',
    description: 'Turns a photo into a moody text-free spy thriller poster.',
    display_group: 'Cinematic',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_royal_portrait',
    label: 'AI Royal Portrait',
    description: 'Reimagines a photo as a dignified royal portrait.',
    display_group: 'Portrait',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_medieval_tapestry',
    label: 'AI Medieval Tapestry',
    description: 'Turns a photo into a woven medieval tapestry scene.',
    display_group: 'Artistic',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_paper_diorama',
    label: 'AI Paper Diorama',
    description: 'Turns a photo into a layered handmade paper diorama.',
    display_group: '3D / Toy',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_tintype_portrait',
    label: 'AI Tintype Portrait',
    description: 'Creates a 19th-century tintype-style portrait.',
    display_group: 'Historical',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_film_contact_sheet',
    label: 'AI Film Contact Sheet',
    description: 'Turns a photo into a text-free analog film contact sheet.',
    display_group: 'Photography',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_ukiyo_e_print',
    label: 'AI Ukiyo-e Print',
    description:
      'Turns a photo into a Japanese woodblock-print inspired artwork.',
    display_group: 'Artistic',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_solarpunk',
    label: 'AI Solarpunk',
    description:
      'Reimagines a photo as a bright optimistic ecological future scene.',
    display_group: 'Sci-Fi',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_underwater_dream',
    label: 'AI Underwater Dream',
    description: 'Turns a photo into a surreal underwater dream portrait.',
    display_group: 'Artistic',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_miniature_train_set',
    label: 'AI Miniature Train Set',
    description: 'Turns a photo into a detailed model railway miniature scene.',
    display_group: '3D / Toy',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_80s_action_movie',
    label: 'AI 80s Action Movie',
    description: 'Stages a photo as a text-free 1980s action movie image.',
    display_group: 'Cinematic',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_old_master_pastel',
    label: 'AI Old Master Pastel',
    description: 'Turns a photo into a soft classical pastel portrait.',
    display_group: 'Artistic',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_documentary_photoessay',
    label: 'AI Documentary Photoessay',
    description: 'Gives a photo an authentic documentary photoessay look.',
    display_group: 'Photography',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'ai_museum_diorama',
    label: 'AI Museum Diorama',
    description: 'Turns a photo into a curated museum diorama display.',
    display_group: '3D / Toy',
    default_weight: 1,
    default_config: {},
    config_schema: [],
  },
  {
    name: 'museum_archive',
    label: 'Museum Archive',
    description:
      'Fine-art gallery framing with elegant serif typography and passe-partout.',
    display_group: 'Poster',
    default_weight: 3,
    default_config: {},
    config_schema: [],
  },
];
