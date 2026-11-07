/*
 * AIWeatherCheck.jsx - Stage 10 Steps 6-7: "AI Weather Check" panel, shown BELOW the normal
 * analysis results (the analysis itself is unchanged and works even if this panel fails).
 *
 * For the field on the map, as of a date, the backend (POST /api/ai/weather-check) uses real
 * satellite history + real weather and the trained AI model (version 3) to show:
 *   - expected vs actual NDVI for the latest clear image ("Weather explains this" or not)
 *   - next-week risk, with the forecast compared with normal weather
 *   - a small chart: clear-image NDVI (dots) and what the AI expected (dashed line)
 *   - CLOUDY-DAY ESTIMATE: if there has been no clear image for 7+ days, the AI's estimated
 *     NDVI for the date, labeled "AI estimate, not a measurement", with the last clear image
 *     date and the model's typical error.
 */
import { useEffect, useRef, useState } from 'react';
import { weatherCheck } from './api.js';

const today = () => new Date().toLocaleDateString('en-CA');
const signed = (x) => `${x > 0 ? '+' : ''}${x.toFixed(3)}`;

function CloudyEstimate({ estimate }) {
  if (!estimate) return null;
  return (
    <div className="inspect-card inspect-unknown cloudy-estimate">
      <strong>☁ {estimate.label}</strong>
      <p>
        No clear satellite image for {estimate.days_without_clear_image} days (clouds). Last clear
        image: <strong>{estimate.last_clear_date}</strong> (NDVI {estimate.last_clear_ndvi.toFixed(3)}).
      </p>
      {estimate.status === 'ok' ? (
        <p>
          AI-estimated NDVI on {estimate.estimate_date}:{' '}
          <strong>{estimate.estimated_ndvi.toFixed(3)} ± {estimate.typical_error.toFixed(2)}</strong>
          <br />
          <span className="muted">
            ± {estimate.typical_error.toFixed(2)} is the model&apos;s typical (average) error when
            tested on 2025; real values are sometimes further off. Wait for a clear image to measure.
          </span>
        </p>
      ) : (
        <p>{estimate.message}</p>
      )}
    </div>
  );
}

function Chart({ images, expected, estimate }) {
  if (!images || images.length < 2) return null;
  const W = 300, H = 130, pad = 28;
  const points = [...images.map((p) => p.date), ...expected.map((p) => p.date)];
  if (estimate?.status === 'ok') points.push(estimate.estimate_date);
  const times = points.map((d) => Date.parse(d));
  const t0 = Math.min(...times), t1 = Math.max(...times);
  const values = [...images.map((p) => p.ndvi), ...expected.map((p) => p.expected_ndvi)];
  if (estimate?.status === 'ok') {
    values.push(estimate.estimated_ndvi - estimate.typical_error, estimate.estimated_ndvi + estimate.typical_error);
  }
  const v0 = Math.max(-0.1, Math.min(...values) - 0.05), v1 = Math.min(1, Math.max(...values) + 0.05);
  const x = (d) => pad + ((Date.parse(d) - t0) / Math.max(t1 - t0, 1)) * (W - pad - 8);
  const y = (v) => H - 18 - ((v - v0) / (v1 - v0)) * (H - 28);
  return (
    <figure className="ai-chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="NDVI of clear images and the AI's expected values">
        <line x1={pad} y1={H - 18} x2={W - 8} y2={H - 18} className="axis" />
        <text x={2} y={y(v1) + 4} className="tick">{v1.toFixed(2)}</text>
        <text x={2} y={y(v0) + 4} className="tick">{v0.toFixed(2)}</text>
        <text x={pad} y={H - 4} className="tick">{images[0].date.slice(5)}</text>
        <text x={W - 40} y={H - 4} className="tick">{points.sort().at(-1).slice(5)}</text>
        {expected.length > 1 && (
          <polyline className="expected" points={expected.map((p) => `${x(p.date)},${y(p.expected_ndvi)}`).join(' ')} />
        )}
        {images.map((p) => <circle key={p.date} cx={x(p.date)} cy={y(p.ndvi)} r={3} className="actual" />)}
        {estimate?.status === 'ok' && (
          <g className="estimate">
            <line x1={x(estimate.estimate_date)} x2={x(estimate.estimate_date)}
                  y1={y(estimate.estimated_ndvi - estimate.typical_error)}
                  y2={y(estimate.estimated_ndvi + estimate.typical_error)} />
            <circle cx={x(estimate.estimate_date)} cy={y(estimate.estimated_ndvi)} r={4} />
          </g>
        )}
      </svg>
      <figcaption className="muted">
        Dots: measured NDVI on clear days. Dashed: what the AI expected from an image 7–20 days
        earlier.{estimate?.status === 'ok' && ' Hollow circle: AI estimate (not a measurement) ± typical error.'}
      </figcaption>
    </figure>
  );
}

function weatherText(w) {
  return w ? `${w.rain_mm} mm rain, average high ${w.avg_high_c} °C` : 'weather missing';
}

export default function AIWeatherCheck({ geometry, exclude, defaultAsOf }) {
  const startDate = defaultAsOf && defaultAsOf < today() ? defaultAsOf : today();
  const [asOf, setAsOf] = useState(startDate);
  const [busy, setBusy] = useState(false);
  const [answer, setAnswer] = useState(null);
  const [error, setError] = useState('');
  const requestCount = useRef(0);

  async function run(day) {
    const thisRequest = ++requestCount.current;
    setBusy(true);
    setError('');
    setAnswer(null);
    try {
      const data = await weatherCheck(geometry, exclude, day);
      if (thisRequest === requestCount.current) setAnswer(data);
    } catch (e) {
      if (thisRequest === requestCount.current) setError(e.message);
    } finally {
      if (thisRequest === requestCount.current) setBusy(false);
    }
  }

  // Runs once when the panel appears (after an analysis); "Check again" re-runs it.
  useEffect(() => {
    run(startDate);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const check = answer?.check;
  const risk = answer?.risk_next_week;
  return (
    <div className="ai-weather-check">
      <h3>AI Weather Check</h3>
      <p className="next-step"><strong>AI estimate based on satellite + weather history. Confirm in person.</strong></p>
      <div className="dates">
        <label>
          Check as of
          <input type="date" value={asOf} max={today()} onChange={(e) => setAsOf(e.target.value)} />
        </label>
      </div>
      <button type="button" onClick={() => run(asOf)} disabled={busy}>
        {busy ? 'Checking…' : 'Check again'}
      </button>
      {busy && <p className="muted">Downloading real satellite + weather history…</p>}
      {error && <p className="problems-box">AI Weather Check failed: {error} (the analysis above is unaffected)</p>}

      {answer && answer.status !== 'ok' && (
        <>
          <p className="inspect-card inspect-unknown">{answer.message}</p>
          <CloudyEstimate estimate={answer.cloudy_estimate} />
        </>
      )}
      {answer && answer.status === 'ok' && (
        <>
          <div className={`inspect-card ${check.status === 'ok' && !check.weather_explains ? 'inspect-flag' : 'inspect-calm'}`}>
            <p>
              Latest clear image: <strong>{answer.last_image_date}</strong>, NDVI {answer.actual_ndvi.toFixed(3)}
              {check.status === 'ok' && <> (AI expected {check.expected_ndvi.toFixed(3)}, {signed(check.difference)})</>}
            </p>
            <p><strong>{check.message}</strong></p>
          </div>
          <CloudyEstimate estimate={answer.cloudy_estimate} />
          <Chart images={answer.recent_images} expected={answer.expected_series} estimate={answer.cloudy_estimate} />
          <p>
            Next-week risk (to {risk.target_date}): <strong>{risk.level}</strong>
            {risk.predicted_change !== undefined && <> — AI expects {signed(risk.predicted_change)} NDVI</>}
            {risk.level === 'Unknown' && <> — {risk.message}</>}
            <br />
            <span className="muted">
              Next 7 days: {weatherText(risk.weather_next_7_days)}
              {risk.normal_next_7_days && <> (normal: {weatherText(risk.normal_next_7_days)})</>}.
              {risk.note && ` ${risk.note}`}
            </span>
          </p>
          {answer.geometry_note && <p className="muted">{answer.geometry_note}</p>}
          <p className="muted">
            Risk: High = expected drop at least 2× the AI&apos;s typical error, Medium = at least 1×
            (project choices). A prioritization signal, not a diagnosis or watering advice.{' '}
            {answer.accuracy_note}
          </p>
          <p className="muted">{answer.weather_source}</p>
        </>
      )}
      {answer?.credits && <p className="muted">{answer.credits.join(' · ')}</p>}
    </div>
  );
}
