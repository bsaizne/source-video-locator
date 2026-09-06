// Minimal inline SVG icon set (stroke-based, Fluent-like). Keys are used by
// <BaseIcon :name="...">. Self-drawn — no third-party icon font or source.

export interface IconPath {
  d: string
}

const S = {
  home: 'M3 11.5 12 4l9 7.5M5.5 10.5V20h4v-5h5v5h4v-9.5',
  folder: 'M3 6.5A1.5 1.5 0 0 1 4.5 5h4l2 2h9A1.5 1.5 0 0 1 21 8.5V17a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z',
  film: 'M4 6h16v12H4zM4 10h16M4 14h16M8 6v12M16 6v12',
  search: 'M10.5 4a6.5 6.5 0 1 1 0 13 6.5 6.5 0 0 1 0-13ZM15 15l4.5 4.5',
  chart: 'M4 20V10M10 20V4M16 20v-8M22 20H2',
  settings: 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z M19.4 15a1.6 1.6 0 0 0 .32 1.76l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.6 1.6 0 0 0-1.76-.32 1.6 1.6 0 0 0-1 1.47V21a2 2 0 1 1-4 0v-.09a1.6 1.6 0 0 0-1-1.47 1.6 1.6 0 0 0-1.76.32l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.6 1.6 0 0 0 4.6 15a1.6 1.6 0 0 0-1.47-1H3a2 2 0 1 1 0-4h.09A1.6 1.6 0 0 0 4.56 9a1.6 1.6 0 0 0-.32-1.76l-.06-.06A2 2 0 1 1 7.01 4.3l.06.06a1.6 1.6 0 0 0 1.76.32H9a1.6 1.6 0 0 0 1-1.47V3a2 2 0 1 1 4 0v.09a1.6 1.6 0 0 0 1 1.47 1.6 1.6 0 0 0 1.76-.32l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.6 1.6 0 0 0-.32 1.76V9a1.6 1.6 0 0 0 1.47 1H21a2 2 0 1 1 0 4h-.09a1.6 1.6 0 0 0-1.51 1Z',
  play: 'M8 5v14l11-7z',
  pause: 'M7 5h3v14H7zM14 5h3v14h-3z',
  check: 'M4 12.5 9.5 18 20 6.5',
  x: 'M6 6l12 12M18 6 6 18',
  'chevron-right': 'M9 6l6 6-6 6',
  'chevron-down': 'M6 9l6 6 6-6',
  plus: 'M12 5v14M5 12h14',
  download: 'M12 4v10m0 0 4-4m-4 4-4-4M5 19h14',
  cpu: 'M7 8h10v8H7zM9 4v2M15 4v2M9 18v2M15 18v2M4 9h2M4 15h2M18 9h2M18 15h2',
  clock: 'M12 7v5l3 2M12 4a8 8 0 1 0 0 16 8 8 0 0 0 0-16Z',
  list: 'M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01',
  compare: 'M4 7h7v10H4zM13 7h7v10h-7zM7.5 10v4M16.5 10v4',
  edit: 'M4 20h4l11-11-4-4L4 16v4ZM13.5 6.5l4 4',
  'arrow-right': 'M4 12h16m0 0-5-5m5 5-5 5',
  info: 'M12 11v5M12 8h.01M12 4a8 8 0 1 0 0 16 8 8 0 0 0 0-16Z',
  warn: 'M12 4 3 20h18L12 4ZM12 10v4M12 17h.01',
  dot: 'M12 12h.01',
  export: 'M12 4v10m0 0 4-4m-4 4-4-4M5 19h14',
  folderplus: 'M3 6.5A1.5 1.5 0 0 1 4.5 5h4l2 2h9A1.5 1.5 0 0 1 21 8.5V17a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2zM12 11v5M9.5 13.5h5',
  copy: 'M9 9h11v11H9zM5 15H4V4h11v1',
  layers: 'M12 4 3 9l9 5 9-5-9-5ZM3 14l9 5 9-5',
} as const

export const ICONS: Record<string, IconPath> = Object.fromEntries(
  Object.entries(S).map(([k, d]) => [k, { d }]),
)

export function hasIcon(name: string): boolean {
  return name in ICONS
}
