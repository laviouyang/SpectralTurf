/*
 * RegionMap.jsx - Homepage "US grass regions" map (added 2026-11-25; replaces the state picker).
 *
 * Our own SVG drawing: US state shapes from U.S. Census data (usMap.json, built by
 * scripts/make_us_map.mjs) with our hand-drawn, approximate region zones clipped to them. The
 * region LAYOUT follows the "Grass Types USA" map by Simple Lawn Solutions (credited under the
 * map; their picture itself is not used). Click (or tab to) a region to see its common grasses.
 * Only Region 3 (Denver-area fields) is validated; the rest are "Coming soon".
 */
import { useState } from 'react';
import { DATA, REGIONS, VALIDATED_REGION } from './turfRegions.js';
import MAP from './usMap.json';

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
          <svg viewBox={`0 0 ${MAP.width} ${MAP.height}`} role="group" aria-label="Map of 7 US grass regions. Select a region for its grasses.">
            <defs>
              <clipPath id="us-outline-clip">
                <path d={MAP.nation} />
              </clipPath>
              <pattern id="coming-soon-hatch" width="9" height="9" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                <line x1="0" y1="0" x2="0" y2="9" stroke="#ffffff" strokeWidth="2" strokeOpacity="0.45" />
              </pattern>
            </defs>
            <path d={MAP.nation} className="region-us-shadow" />
            {REGIONS.map((r) => {
              const d = MAP.zones[r.id];
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
            <path d={MAP.borders} className="region-state-lines" />
            <path d={MAP.nation} className="region-us-outline" />
            {REGIONS.map((r) => {
              const [x, y] = MAP.labels[r.id];
              // Region 1 is a thin strip: its name sits just left of the circle, over the ocean.
              const anchor = r.id === 1 ? 'end' : 'middle';
              const tx = r.id === 1 ? x + 12 : x;
              return (
                <g key={r.id} className={`region-label ${r.id === (hovered ?? selected) ? 'active' : ''}`} aria-hidden="true">
                  <circle cx={x} cy={y} r="17" fill="#ffffff" stroke={STYLE[r.id].fill} strokeWidth="3.5" />
                  <text x={x} y={y + 6.5} textAnchor="middle" className="region-number">{r.id}</text>
                  <text x={tx} y={y + 37} textAnchor={anchor} className="region-name" fill={STYLE[r.id].ink}>
                    {r.short}
                  </text>
                  <text x={tx} y={y + 54} textAnchor={anchor} className="region-status" fill={STYLE[r.id].ink}>
                    {statusText(r.id)}
                  </text>
                </g>
              );
            })}
          </svg>
          <figcaption className="region-credit">
            <strong>Source:</strong> {DATA.sources.layout.name}. {DATA.sources.states.name} (
            <a href={DATA.sources.states.url} target="_blank" rel="noreferrer">us-atlas</a>). Grass lists:
            university extensions (shown for each region). Boundaries are approximate; striped = coming soon.
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
          How the regions were drawn: a simplified map, not an official USDA map. The region layout
          follows the &ldquo;Grass Types USA&rdquo; map by Simple Lawn Solutions (a lawn-care company, so a
          visual reference rather than a scientific source), redrawn by hand on U.S. Census state shapes.
          The split into cool-season, transition and warm-season areas matches{' '}
          {DATA.sources.framework.map((s, i) => (
            <span key={s.url}>
              {i > 0 && ' and '}
              <a href={s.url} target="_blank" rel="noreferrer">{s.name}</a>
            </span>
          ))}
          ; the exact lines are approximate.
        </p>
      </details>
    </div>
  );
}
