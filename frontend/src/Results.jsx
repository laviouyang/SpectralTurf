/*
 * Results.jsx - Everything the user sees after an analysis:
 * inspection indicator, map layer choice + legend, the numbers, what they mean,
 * data quality, and limitations.
 */

const LAYERS = [
  { id: 'inspection', label: 'Inspection' },
  { id: 'ndvi', label: 'NDVI' },
  { id: 'ndmi', label: 'NDMI' },
  { id: 'true_color', label: 'True color' },
  { id: 'none', label: 'None' },
];

// A color bar built from the backend's color scale, so legend and map always match.
function Legend({ scale, rejectedColor, lowLabel, highLabel, note }) {
  const first = scale[0][0];
  const last = scale[scale.length - 1][0];
  const gradient = scale
    .map(([value, color]) => `${color} ${((value - first) / (last - first)) * 100}%`)
    .join(', ');

  return (
    <div className="legend">
      <div className="legend-bar" style={{ background: `linear-gradient(to right, ${gradient})` }} />
      <div className="legend-labels">
        {scale.map(([value], i) => (
          <span key={value}>
            {i === 0 ? `≤${value}` : i === scale.length - 1 ? `≥${value}` : value}
          </span>
        ))}
      </div>
      <div className="legend-ends">
        <span>{lowLabel}</span>
        <span>{highLabel}</span>
      </div>
      <p className="muted">
        <span className="swatch" style={{ background: rejectedColor }} /> Gray: inside your area but
        rejected (cloud, shadow, etc.). {note}
      </p>
      <p className="muted">These colors are a display scale, not health categories.</p>
    </div>
  );
}

// Things a person can look at on site. They help someone check the spot in
// person; they do NOT diagnose a cause or prescribe watering.
function VisitChecklist() {
  return (
    <details className="checklist">
      <summary>What to check when you visit</summary>
      <ul>
        <li>Is the spot actually turf? It may be bare dirt, a path, an infield edge, or a goal area.</li>
        <li>Does the grass look thin, worn, brown, or patchy compared with nearby turf?</li>
        <li>Push a screwdriver into the soil. Is it much harder or drier than in greener areas?</li>
        <li>If the field is irrigated, do the sprinklers reach this spot? Look for broken or blocked heads.</li>
        <li>Has anything recently happened there: heavy use, events, mowing, painting, or reseeding?</li>
        <li>
          For advice on causes and care, ask a turf professional or{' '}
          <a href="https://extension.colostate.edu/" target="_blank" rel="noreferrer">
            Colorado State University Extension
          </a>
          .
        </li>
      </ul>
    </details>
  );
}

// One plain next action for each outcome. It says where to look, never what the cause is.
const NEXT_STEP = {
  may_warrant_inspection:
    'Visit the pink spots and compare them with greener parts of the field. The checklist below lists what to look for.',
  no_area_stands_out:
    'No single spot needs a closer look. If the whole field looks poor to you, inspect it in person, because this rule cannot detect problems that affect the entire field.',
  insufficient_evidence:
    'Draw a larger area of turf, or choose a different date range with fewer clouds, and analyze again.',
};

function InspectionCard({ inspection, onShowOnMap }) {
  const style = {
    may_warrant_inspection: 'inspect-flag',
    no_area_stands_out: 'inspect-calm',
    insufficient_evidence: 'inspect-unknown',
  }[inspection.status];

  return (
    <div className={`inspect-card ${style}`}>
      <p className="inspect-headline">{inspection.headline}</p>
      <p>{inspection.reason}</p>
      <p className="next-step">
        <strong>Your next step:</strong> {NEXT_STEP[inspection.status]}
      </p>
      {inspection.status === 'may_warrant_inspection' && (
        <button type="button" className="secondary" onClick={onShowOnMap}>
          Show the pink spots on the map
        </button>
      )}
      <p className="muted">
        <strong>Preliminary.</strong> Based on one satellite image and a simple rule chosen for this
        project, not a validated method. It shows where to look, not what is wrong.
      </p>
      <details>
        <summary>How this rule works</summary>
        <p>{inspection.rule}</p>
        {inspection.field_median_ndvi !== undefined && (
          <p>
            For this field: median NDVI {inspection.field_median_ndvi}, so pixels below{' '}
            {inspection.cutoff_ndvi} count as notably low. {inspection.low_pixels} of{' '}
            {inspection.pixels_checked} checked pixels are below that.
          </p>
        )}
      </details>
      {inspection.status !== 'insufficient_evidence' && <VisitChecklist />}
    </div>
  );
}

export default function Results({ result, layer, onLayerChange }) {
  const { observation, status, message, pixels, ndvi, ndmi, warnings, color_scales: scales } = result;
  const enoughData = status === 'ok';
  const rejectedReasons = Object.entries(pixels.rejected_by_reason);

  // The full response without the long picture codes, for the "raw data" view.
  const { images, ...rawWithoutImages } = result;

  return (
    <div className="results">
      <h3>Results</h3>
      <p>
        <strong>Observation date: {observation.date}</strong>
        <br />
        <span className="muted">
          One Sentinel-2 image: the least cloudy of {observation.scenes_considered} in your date range
          (tile cloud cover {observation.tile_cloud_cover}%).
        </span>
      </p>

      <InspectionCard inspection={result.inspection} onShowOnMap={() => onLayerChange('inspection')} />

      {/* ---- Map layer choice and legend ---- */}
      <div className="layer-choice" role="radiogroup" aria-label="Map layer">
        {LAYERS.map(({ id, label }) => (
          <label key={id}>
            <input
              type="radio"
              name="layer"
              value={id}
              checked={layer === id}
              onChange={() => onLayerChange(id)}
            />
            {label}
          </label>
        ))}
      </div>
      {layer === 'inspection' && (
        <div className="legend">
          <p className="muted">
            <span className="swatch" style={{ background: scales.inspection_low }} /> Pink: notably less
            green than the rest of this field
            <br />
            <span className="swatch" style={{ background: scales.inspection_checked }} /> Faint white:
            checked, not notably low
            <br />
            <span className="swatch" style={{ background: scales.rejected }} /> Gray: rejected (cloud,
            shadow, etc.)
            <br />
            Pixels along the outline&apos;s edge are not checked, so they show no color.
          </p>
        </div>
      )}
      {layer === 'ndvi' && (
        <Legend
          scale={scales.ndvi}
          rejectedColor={scales.rejected}
          lowLabel="bare / not green"
          highLabel="dense green"
          note="Each square is one 10 m pixel."
        />
      )}
      {layer === 'ndmi' && (
        <Legend
          scale={scales.ndmi}
          rejectedColor={scales.rejected}
          lowLabel="drier"
          highLabel="more leaf water"
          note="NDMI is 20 m data, so it shows as blocks of about 2×2 squares."
        />
      )}
      {layer === 'true_color' && (
        <p className="muted">
          Natural color from the same Sentinel-2 image, brightened for viewing. Use it to check for
          clouds, haze, or surfaces that are not turf. This is not the background photo.
        </p>
      )}

      {/* ---- The numbers ---- */}
      {enoughData ? (
        <table className="stats">
          <thead>
            <tr>
              <th></th>
              <th>Mean</th>
              <th>Median</th>
              <th>Range</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>NDVI (greenness, 10 m)</td>
              <td>{ndvi.mean}</td>
              <td>{ndvi.median}</td>
              <td>{ndvi.min} to {ndvi.max}</td>
            </tr>
            <tr>
              <td>NDMI (leaf moisture, 20 m)</td>
              <td>{ndmi.mean}</td>
              <td>{ndmi.median}</td>
              <td>{ndmi.min} to {ndmi.max}</td>
            </tr>
          </tbody>
        </table>
      ) : (
        // Too few clear pixels: we deliberately do NOT show averages.
        <p className="problems-box">
          <strong>Insufficient evidence.</strong> {message} No averages are shown because they would
          not be reliable.
        </p>
      )}

      {/* ---- What the numbers mean ---- */}
      <h4>What these numbers mean</h4>
      <p>
        <strong>NDVI</strong> compares near-infrared and red light. Green, leafy grass reflects much
        more near-infrared than red, so it scores high. Approximate typical values: water below 0,
        pavement and bare soil about 0 to 0.2, sparse or dry vegetation about 0.2 to 0.5, dense green
        vegetation above about 0.6.
      </p>
      <p>
        <strong>NDMI</strong> compares near-infrared and shortwave-infrared light, which is absorbed
        by water in leaves. Higher values suggest more water in the vegetation; negative values suggest
        drier plants or surfaces that are not vegetation.
      </p>
      <p>
        A low value is a reason to look at the field in person. It does not say why: dormancy, recent
        mowing, wear, disease, or watering problems can all look similar from space.
      </p>

      {/* ---- Data quality ---- */}
      <h4>Data quality</h4>
      <ul className="facts">
        <li>
          Clear pixels: {pixels.valid_after_masking.toLocaleString()} of{' '}
          {/* Round DOWN so 724 of 728 shows 99%, never a misleading 100%. */}
          {pixels.with_data.toLocaleString()} inside your area ({Math.floor(pixels.valid_fraction * 100)}%)
        </li>
        {result.excluded?.areas > 0 && (
          <li>
            Left out by you: {result.excluded.areas} area{result.excluded.areas > 1 ? 's' : ''} (
            {result.excluded.pixels.toLocaleString()} pixels, not analyzed)
          </li>
        )}
        {rejectedReasons.length > 0 && (
          <li>
            Rejected: {rejectedReasons.map(([reason, count]) => `${count} ${reason}`).join(', ')}
          </li>
        )}
        <li>About {Math.floor(ndmi.valid_pixels / 4).toLocaleString()} independent 20 m measurements for NDMI</li>
      </ul>
      {warnings.length > 0 ? (
        <ul className="warnings">
          {warnings.map((w) => (
            <li key={w}>⚠ {w}</li>
          ))}
        </ul>
      ) : (
        <p className="ok">No data-quality warnings for this analysis.</p>
      )}
      <p className="muted">
        Cloud and shadow pixels are removed using Sentinel-2&apos;s own scene classification. Warning
        levels and the 20-pixel minimum are this project&apos;s choices, not official standards.
      </p>

      {/* ---- Limitations ---- */}
      <h4>Limitations</h4>
      <ul className="facts">
        <li>Each NDVI pixel is 10 m × 10 m and each NDMI pixel is 20 m × 20 m. Patches smaller than that can be missed.</li>
        <li>Pixels on the edge of your outline can mix turf with dirt, pavement, or trees, which pulls values toward those surfaces.</li>
        <li>This is a single snapshot from one day, not a trend over time.</li>
        <li>Cloud masking can miss thin haze or small shadows.</li>
        <li>The inspection indicator compares parts of one field with each other, so a problem affecting the whole field evenly will not stand out.</li>
        <li>It cannot diagnose disease, prove drought, or say how much to water.</li>
      </ul>

      <details>
        <summary>Full backend response (raw data)</summary>
        <pre>{JSON.stringify(rawWithoutImages, null, 2)}</pre>
      </details>
      <p className="attribution">Data: {result.source}. Contains modified Copernicus Sentinel data {observation.date.slice(0, 4)}.</p>
    </div>
  );
}
