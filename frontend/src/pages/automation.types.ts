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
