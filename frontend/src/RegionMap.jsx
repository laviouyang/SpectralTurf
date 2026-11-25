/*
 * RegionMap.jsx - Homepage "US grass regions" map (added 2026-11-25; replaces the state picker).
 *
 * An ORIGINAL, simplified SVG drawn from our own coordinates (turfRegions.json): each region
 * zone is clipped to a simplified outline of the 48 states. Click (or tab to) a region to see
 * its common grasses. Only Region 3 (Denver-area fields) is validated; the rest are "Coming soon".
 * Boundaries are approximate. Sources are listed under the map.
 */
import { useState } from 'react';
import { DATA, REGIONS, VALIDATED_REGION } from './turfRegions.js';

// Region colors (brand palette and tints) and the label text color that reads on each.
const STYLE = {
  1: { fill: '#1c897d', ink: '#0b2b2f' }, // its name sits over the background (dark text)
  2: { fill: '#dda747', ink: '#0b2b2f' },
  3: { fill: '#125c49', ink: '#ffffff' },
  4: { fill: '#74c7c3', ink: '#0b2b2f' },
  5: { fill: '#ecd29b', ink: '#0b2b2f' },
  6: { fill: '#a7d7c0', ink: '#0b2b2f' },
  7: { fill: '#d98a66', ink: '#0b2b2f' },
};

// Simple map projection: longitude/latitude -> SVG x/y (longitude shrunk by cos 38°, mid-US).
const SCALE = 12;
// (130 °W at the left edge leaves room for Region 1's label over the ocean.)
const project = ([lon, lat]) => [(lon + 130) * 0.788 * SCALE, (49.6 - lat) * SCALE];
const toPath = (points) => `M${points.map((p) => project(p).map((v) => v.toFixed(1)).join(',')).join('L')}Z`;
const OUTLINE = toPath(DATA.us_outline);

function statusText(id) {
  return id === VALIDATED_REGION ? 'Validated' : 'Coming soon';
}

export default function RegionMap() {
  const [selected, setSelected] = useState(VALIDATED_REGION);
  const [hovered, setHovered] = useState(null);
  const shown = REGIONS.find((r) => r.id === (hovered ?? selected));
  const source = DATA.sources[shown.source];

  return (
    <div className="region-map">
      <div className="region-map-grid">
        <figure className="region-figure">
          <svg viewBox="0 0 604 304" role="group" aria-label="Map of 7 US grass regions. Select a region for its grasses.">
            <defs>
              <clipPath id="us-outline-clip">
                <path d={OUTLINE} />
              </clipPath>
              <pattern id="coming-soon-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                <line x1="0" y1="0" x2="0" y2="6" stroke="#ffffff" strokeWidth="1.4" strokeOpacity="0.45" />
              </pattern>
            </defs>
            <path d={OUTLINE} className="region-us-shadow" />
            {REGIONS.map((r) => {
              const d = toPath(r.zone.coordinates[0]);
              const active = r.id === (hovered ?? selected);
              return (
                <g
                  key={r.id}
                  role="button"
                  tabIndex={0}
                  aria-pressed={r.id === selected}
                  aria-label={`Region ${r.id}: ${r.name}. ${statusText(r.id)}. Grasses: ${r.grasses.join(', ')}.`}
                  className={`region-shape ${active ? 'active' : ''}`}
                  onClick={() => setSelected(r.id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      setSelected(r.id);
                    }
                  }}
                  onMouseEnter={() => setHovered(r.id)}
                  onMouseLeave={() => setHovered(null)}
                  onFocus={() => setHovered(r.id)}
                  onBlur={() => setHovered(null)}
                >
                  <path d={d} clipPath="url(#us-outline-clip)" fill={STYLE[r.id].fill} />
                  {r.id !== VALIDATED_REGION && (
                    <path d={d} clipPath="url(#us-outline-clip)" fill="url(#coming-soon-hatch)" />
                  )}
                </g>
              );
            })}
            <path d={OUTLINE} className="region-us-outline" />
            {REGIONS.map((r) => {
              const [x, y] = project(r.label);
              // Region 1 is a thin strip: its name sits just left of the circle, over the ocean.
              const anchor = r.id === 1 ? 'end' : 'middle';
              const tx = r.id === 1 ? x + 8 : x;
              return (
                <g key={r.id} className="region-label" aria-hidden="true">
                  <circle cx={x} cy={y} r="11" fill="#ffffff" stroke={STYLE[r.id].fill} strokeWidth="2.5" />
                  <text x={x} y={y + 4} textAnchor="middle" className="region-number">{r.id}</text>
                  <text x={tx} y={y + 24} textAnchor={anchor} className="region-name" fill={STYLE[r.id].ink}>
                    {r.short}
                  </text>
                  <text x={tx} y={y + 35} textAnchor={anchor} className="region-status" fill={STYLE[r.id].ink}>
                    {statusText(r.id)}
                  </text>
                </g>
              );
            })}
          </svg>
          <figcaption className="muted">
            Simplified map drawn for SpectralTurf. Boundaries are approximate. Striped = coming soon.
          </figcaption>
        </figure>

        <div className="region-info" aria-live="polite">
          <p className="region-info-kicker">Region {shown.id}</p>
          <h3>{shown.name}</h3>
          <p className={`region-badge ${shown.id === VALIDATED_REGION ? 'ok' : 'soon'}`}>
            {shown.id === VALIDATED_REGION ? '✓ Validated (Denver-area fields)' : 'Coming soon'}
          </p>
          <p className="muted">Climate: {shown.climate}</p>
          <p><strong>Common lawn and sports-field grasses:</strong></p>
          <ul>
            {shown.grasses.map((g) => <li key={g}>{g}</li>)}
          </ul>
          <p className="muted">
            Source: <a href={source.url} target="_blank" rel="noreferrer">{source.name}</a>
          </p>
        </div>
      </div>

      <ul className="region-legend" aria-label="Legend">
        {REGIONS.map((r) => (
          <li key={r.id}>
            <button type="button" onClick={() => setSelected(r.id)} aria-pressed={r.id === selected}>
              <span className="region-swatch" style={{ background: STYLE[r.id].fill }} aria-hidden="true" />
              <span>{r.id}. {r.name}</span>
              <span className={`region-chip ${r.id === VALIDATED_REGION ? 'ok' : 'soon'}`}>{statusText(r.id)}</span>
            </button>
          </li>
        ))}
      </ul>

      <p className="state-note">
        <strong>Only Region 3 is validated right now</strong>, using real Denver-area fields: the
        healthy-turf baseline, the color cutoff and the AI model were all made from them. Doing the
        same for another region means downloading years of satellite and weather data for new fields
        there and training and testing the AI again, which takes a lot of time and processing quota.
        You can still analyze a field anywhere: the within-field check works everywhere, and other
        results are marked &ldquo;not validated for this region yet&rdquo;.
      </p>

      <details className="region-list">
        <summary>All regions as a list (text version of the map)</summary>
        <ol>
          {REGIONS.map((r) => (
            <li key={r.id}>
              <strong>Region {r.id}: {r.name}</strong> ({r.climate}) — {statusText(r.id)}. Common grasses:{' '}
              {r.grasses.join(', ')}. Source:{' '}
              <a href={DATA.sources[r.source].url} target="_blank" rel="noreferrer">{DATA.sources[r.source].name}</a>.
            </li>
          ))}
        </ol>
        <p className="muted">
          How the regions were drawn: a simplified project map, not an official USDA map. The split
          into cool-season, transition and warm-season areas follows{' '}
          {DATA.sources.framework.map((s, i) => (
            <span key={s.url}>
              {i > 0 && ' and '}
              <a href={s.url} target="_blank" rel="noreferrer">{s.name}</a>
            </span>
          ))}
          ; the finer split into 7 regions and the exact lines are our approximation.
        </p>
      </details>
    </div>
  );
}
