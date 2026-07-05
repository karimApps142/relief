// SVG icons ported from the design. Stroke-based (currentColor) unless `fill`.
const STROKE: Record<string, string[]> = {
  relief: ['M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z', 'm3.3 7 8.7 5 8.7-5', 'M12 22V12'],
  cube: ['M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z'],
  text: ['M4 7V4h16v3', 'M9 20h6', 'M12 4v16'],
  upscale: ['M15 3h6v6', 'M9 21H3v-6', 'M21 3l-7 7', 'M3 21l7-7'],
  system: ['M15 2v2M15 20v2M2 15h2M2 9h2M20 15h2M20 9h2M9 2v2M9 20v2'],
  history: ['M3 3v5h5', 'M3.05 13A9 9 0 1 0 6 5.3L3 8', 'M12 7v5l4 2'],
  chevronRight: ['m9 18 6-6-6-6'],
  chevronLeft: ['m15 18-6-6 6-6'],
  chevronDown: ['m6 9 6 6 6-6'],
  expand: ['M8 3H5a2 2 0 0 0-2 2v3', 'M16 3h3a2 2 0 0 1 2 2v3', 'M21 16v3a2 2 0 0 1-2 2h-3', 'M8 21H5a2 2 0 0 1-2-2v-3'],
  plus: ['M12 5v14M5 12h14'],
  upload: ['M12 13v8M8 17l4-4 4 4', 'M20 16.7A5 5 0 0 0 18 7h-1.3A8 8 0 1 0 4 15.3'],
  warning: ['M12 9v4M12 17h.01', 'M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z'],
  check: ['M20 6 9 17l-5-5'],
  x: ['M18 6 6 18M6 6l12 12'],
  xCircle: ['M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z', 'm15 9-6 6M9 9l6 6'],
  download: ['M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4', 'M7 10l5 5 5-5M12 15V3'],
  shuffle: ['M21 2v6h-6M3 12a9 9 0 0 1 15-6.7L21 8M3 22v-6h6M21 12a9 9 0 0 1-15 6.7L3 16'],
  rerun: ['M21 2v6h-6M3 12a9 9 0 0 1 15-6.7L21 8'],
  clock: ['M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z', 'M12 6v6l4 2'],
  sparkle: ['m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3z'],
  image: ['M5 21h14a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2z', 'M9 11a2 2 0 1 0 0-4 2 2 0 0 0 0 4z', 'm21 15-3.1-3.1a2 2 0 0 0-2.8 0L6 21'],
  mesh: ['M12 2 2 7l10 5 10-5z', 'm2 17 10 5 10-5M2 12l10 5 10-5'],
  portrait: ['M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2', 'M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z'],
  scissors: ['M6 9a3 3 0 1 0 0-6 3 3 0 0 0 0 6z', 'M6 21a3 3 0 1 0 0-6 3 3 0 0 0 0 6z', 'M20 4 8.12 15.88', 'M14.47 14.48 20 20', 'M8.12 8.12 12 12'],
  layers: ['m12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.84z', 'm22 17.65-9.17 4.16a2 2 0 0 1-1.66 0L2 17.65', 'm22 12.65-9.17 4.16a2 2 0 0 1-1.66 0L2 12.65'],
  face: ['M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z', 'M8 14s1.5 2 4 2 4-2 4-2', 'M9 9h.01', 'M15 9h.01'],
  sun: ['M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10z', 'M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42'],
  speech: ['M11 5 6 9H2v6h4l5 4z', 'M15.54 8.46a5 5 0 0 1 0 7.07', 'M19.07 4.93a10 10 0 0 1 0 14.14'],
  waveform: ['M2 10v3', 'M6 6v11', 'M10 3v18', 'M14 8v7', 'M18 5v13', 'M22 10v3'],
  mic: ['M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z', 'M19 10v2a7 7 0 0 1-14 0v-2', 'M12 19v3'],
}
const FILL: Record<string, string[]> = {
  logo: ['M12 2 9.5 9.5 2 12l7.5 2.5L12 22l2.5-7.5L22 12l-7.5-2.5z'],
}
const FEATURE: Record<string, string> = { box: 'relief', text: 'text', image: 'image', upscale: 'upscale' }

export function Icon({ name, size = 20, sw = 1.9 }: { name: string; size?: number; sw?: number }) {
  if (FILL[name]) {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor">
        {FILL[name].map((d, i) => <path key={i} d={d} />)}
      </svg>
    )
  }
  const paths = STROKE[name] || STROKE.cube
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round">
      {paths.map((d, i) => <path key={i} d={d} />)}
    </svg>
  )
}

// feature.icon → STROKE icon name (legacy aliases via FEATURE; otherwise the icon name
// is used directly, e.g. 'portrait' | 'scissors' | 'layers' | 'face' | 'sun' | 'mesh').
export const featureIcon = (icon: string) => FEATURE[icon] || (icon in STROKE ? icon : 'cube')
