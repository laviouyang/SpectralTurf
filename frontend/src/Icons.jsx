/*
 * Icons.jsx - Small line icons drawn as SVG (added 2026-11-23, UI redesign).
 * Made for this project, so there are no icon-library licenses to worry about.
 * They are decoration only (aria-hidden); the text next to them says what they mean.
 */

const PATHS = {
  draw: 'M6 19 4 9l7-5 8 4-2 11Z M4 9h.01 M11 4h.01 M19 8h.01 M17 19h.01 M6 19h.01',
  satellite: 'M12 8l4 4-4 4-4-4Z M8 12 3.5 7.5l3-3L11 9 M16 12l4.5 4.5-3 3L13 15 M5 16a3 3 0 0 0 3 3 M3 16a5 5 0 0 0 5 5',
  target: 'M12 3v3 M12 18v3 M3 12h3 M18 12h3 M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10Z M12 11a1 1 0 1 0 0 2 1 1 0 0 0 0-2Z',
  chart: 'M4 20V4 M4 20h16 M7 15l4-5 3 3 5-7 M17 6h2v2',
  list: 'M9 6h11 M9 12h11 M9 18h11 M4 5.5h1.5V7 M4 11h2l-2 2h2 M4 17h2v3H4',
  sliders: 'M5 4v16 M12 4v16 M19 4v16 M3 14h4 M10 8h4 M17 16h4',
  chat: 'M4 5h16v11H9l-5 4Z M8 9h8 M8 12h5',
  shield: 'M12 3l8 3v6c0 4.5-3.4 8-8 9-4.6-1-8-4.5-8-9V6Z M8.5 12l2.5 2.5 4.5-5',
  user: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z M4 21a8 8 0 0 1 16 0',
  close: 'M6 6l12 12 M18 6 6 18',
  chevronLeft: 'M15 5l-7 7 7 7',
  chevronRight: 'M9 5l7 7-7 7',
  arrowRight: 'M4 12h15 M13 6l6 6-6 6',
  search: 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14Z M16 16l5 5',
  github: 'M9 19c-4 1.5-4-2-6-2.5 M15 21v-3.5c0-1 .1-1.4-.5-2 2.8-.3 5.5-1.4 5.5-6a4.6 4.6 0 0 0-1.3-3.2 4.2 4.2 0 0 0-.1-3.2s-1-.3-3.3 1.3a11.4 11.4 0 0 0-6 0C6.9 2.8 5.9 3.1 5.9 3.1a4.2 4.2 0 0 0-.1 3.2A4.6 4.6 0 0 0 4.5 9.5c0 4.6 2.7 5.7 5.5 6-.6.6-.6 1.2-.5 2V21',
  drop: 'M12 3c3 4 6 7.2 6 10.5a6 6 0 0 1-12 0C6 10.2 9 7 12 3Z',
  eye: 'M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z',
  alert: 'M12 3 2 20h20Z M12 10v4 M12 17h.01',
  people: 'M9 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z M2.5 20a6.5 6.5 0 0 1 13 0 M16 4.5a3.5 3.5 0 0 1 0 6.5 M18 14a6.5 6.5 0 0 1 3.5 6',
  ruler: 'M3 17 17 3l4 4L7 21Z M7 13l2 2 M10 10l2 2 M13 7l2 2',
};

export function Icon({ name, size = 24, className = '' }) {
  return (
    <svg
      className={`icon ${className}`}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d={PATHS[name]} />
    </svg>
  );
}

// The SpectralTurf mark: a field (rounded square) seen from above, with turf stripes
// and a satellite's orbit. The same drawing is in public/logo.svg (the browser tab icon).
export function Logo({ size = 32 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" focusable="false">
      <rect x="2" y="2" width="28" height="28" rx="8" fill="#125C49" />
      <path d="M8 22h16M8 17.5h16M8 13h10" stroke="#74C7C3" strokeWidth="2.4" strokeLinecap="round" />
      <path d="M5 9.5C10 4.5 21 3.5 27.5 8" stroke="#DDA747" strokeWidth="1.6" fill="none" strokeLinecap="round" />
      <circle cx="24" cy="6.3" r="2.2" fill="#F7F6EE" />
    </svg>
  );
}
