/*
 * WhatIf.jsx - Stage 10 Step 9: "What if?" weather simulator.
 *
 * The user picks made-up weather for the 14 days after a field's latest clear satellite
 * image. The backend runs the trained AI model with that weather (the weather BEFORE the
 * image stays real) and returns the estimated greenness (NDVI) change and a risk level.
 * The slider ranges come from what the model saw in training; outside them, no estimate.
 * "Scenario estimate from the AI model, not a forecast."
 */
import { useEffect, useRef, useState } from 'react';
import { getWhatIfLimits, runWhatIf } from './api.js';

const today = () => new Date().toLocaleDateString('en-CA');
const signed = (x) => `${x > 0 ? '+' : ''}${x.toFixed(3)}`;
const WAIT_MS = 600; // wait until the slider stops moving before asking the backend

function Estimate({ name, result }) {
  if (result.status !== 'ok') {
    const warn = result.status === 'outside_training';
    return (
      <li className={`inspect-card ranked-field ${warn ? 'inspect-flag' : 'inspect-unknown'}`}>
        <strong>{name}</strong>
        <p>{warn ? '⚠ ' : ''}{result.message}</p>
      </li>
    );
  }
  const cardClass = result.risk_level === 'Low' ? 'inspect-calm' : 'inspect-flag';
  return (
    <li className={`inspect-card ranked-field ${cardClass}`}>
      <strong>{name}</strong>
      <p>
        Starts from NDVI {result.start_ndvi.toFixed(3)} (clear image {result.last_image_date}).
        <br />
        Estimated NDVI on {result.target_date}: <strong>{result.predicted_ndvi.toFixed(3)}</strong> (
        {signed(result.predicted_change)}). Risk: <strong>{result.risk_level}</strong>
      </p>
      {result.geometry_note && <p className="muted">{result.geometry_note}</p>}
    </li>
  );
}

export default function WhatIf({ geometry, exclude, user }) {
  const [limits, setLimits] = useState(null);
  const [asOf, setAsOf] = useState(today());
  const [dryDays, setDryDays] = useState(7);
  const [rain, setRain] = useState(10);
  const [high, setHigh] = useState(30);
  const [includeMine, setIncludeMine] = useState(true);
  const [started, setStarted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [answer, setAnswer] = useState(null);
  const [error, setError] = useState('');
  const requestCount = useRef(0);

  // Slider limits depend on the month of the date (only temperatures that really happened then).
  useEffect(() => {
    let current = true;
    getWhatIfLimits(asOf)
      .then((data) => {
        if (!current) return;
        setLimits(data);
        const [low, high] = data.avg_high_c;
        setHigh((h) => Math.min(Math.max(h, low), high)); // keep the slider inside the allowed range
      })
      .catch((e) => current && setError(e.message));
    return () => { current = false; };
  }, [asOf]);

  const withMine = Boolean(user) && includeMine;
  const nothingToRun = !geometry && !withMine;
  const geometryKey = JSON.stringify([geometry, exclude]);

  // After the first "Run scenario", every change re-runs the model (after a short pause).
  useEffect(() => {
    if (!started || nothingToRun) return undefined;
    const timer = setTimeout(async () => {
      const thisRequest = ++requestCount.current;
      setBusy(true);
      setError('');
      try {
        const data = await runWhatIf({
          geometry, exclude, as_of: asOf, dry_days: dryDays,
          rain_mm: dryDays >= (limits?.days ?? 14) ? 0 : rain, avg_high_c: high,
          include_my_fields: withMine,
        });
        if (thisRequest === requestCount.current) setAnswer(data);
      } catch (e) {
        if (thisRequest === requestCount.current) setError(e.message);
      } finally {
        if (thisRequest === requestCount.current) setBusy(false);
      }
    }, WAIT_MS);
    return () => clearTimeout(timer);
    // geometryKey stands in for geometry + exclude (new arrays on every render)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [started, asOf, dryDays, rain, high, withMine, geometryKey, nothingToRun]);

  if (!limits) {
    return error ? <p className="problems-box">{error}</p> : <p className="muted">Loading…</p>;
  }
  const days = limits.days;
  const allDry = dryDays >= days;
  const et0Note = answer?.current_field?.et0_note || answer?.my_fields?.find((e) => e.result.et0_note)?.result.et0_note;

  return (
    <div className="what-if">
      <p className="muted">
        Pick weather for the {days} days after a field&apos;s latest clear satellite image and see
        what the AI model estimates. Works for the field on the map
        {user ? ' and your saved fields' : ' (log in to include your saved fields)'}.
      </p>

      <label className="slider">
        Days without rain (the last days of the {days}): <strong>{dryDays}</strong>
        <input type="range" min={limits.dry_days[0]} max={limits.dry_days[1]} step={1}
               value={dryDays} onChange={(e) => setDryDays(Number(e.target.value))} />
      </label>
      <label className="slider">
        Rain on the other {days - dryDays} days: <strong>{allDry ? 0 : rain} mm</strong>
        <input type="range" min={limits.rain_mm[0]} max={limits.rain_mm[1]} step={1}
               value={allDry ? 0 : rain} disabled={allDry}
               onChange={(e) => setRain(Number(e.target.value))} />
      </label>
      <label className="slider">
        Average high temperature: <strong>{high} °C</strong> ({Math.round(high * 1.8 + 32)} °F)
        <span className="slider-range">
          {' '}— allowed {limits.avg_high_c[0]}–{limits.avg_high_c[1]} °C
          {limits.month ? ` in ${limits.month}` : ''}
        </span>
        <input type="range" min={limits.avg_high_c[0]} max={limits.avg_high_c[1]} step={1}
               value={high} onChange={(e) => setHigh(Number(e.target.value))} />
      </label>
      {limits.month_note && <p className="muted">{limits.month_note}.</p>}
      <p className="muted"><strong>{limits.heat_note}</strong></p>
      <p className="muted">
        Slider ranges = what the AI saw in training (2019–2025). Some combinations can still be
        outside it; then you get a warning instead of a number.
      </p>

      <div className="dates">
        <label>
          Starting from the latest image before
          <input type="date" value={asOf} max={today()} onChange={(e) => setAsOf(e.target.value)} />
        </label>
      </div>
      {user && (
        <label className="checkbox">
          <input type="checkbox" checked={includeMine} onChange={(e) => setIncludeMine(e.target.checked)} />{' '}
          Also show My Fields
        </label>
      )}

      {!started && (
        <button type="button" onClick={() => setStarted(true)} disabled={nothingToRun}>
          Run scenario
        </button>
      )}
      {nothingToRun && <p className="muted">Draw a field on the map{user ? ' or tick “Also show My Fields”' : ''} first.</p>}
      {started && busy && <p className="muted">Running the AI model…</p>}
      {error && <p className="problems-box">{error}</p>}

      {started && answer && (
        <>
          <p className="next-step">
            <strong>{answer.label}</strong>
          </p>
          <ul className="ranked-list">
            {answer.current_field && (
              answer.current_field.status === 'off_season' ? (
                <li className="inspect-card inspect-unknown">
                  <strong>{answer.current_field.message}</strong> Pick a date in April–October (for
                  example 2026-08-15) to try it.
                </li>
              ) : (
                <Estimate name="Field on the map" result={answer.current_field} />
              )
            )}
            {answer.my_fields?.map((entry) => (
              <Estimate key={entry.field.id} name={entry.field.name} result={entry.result} />
            ))}
          </ul>
          {answer.my_fields && answer.my_fields.length === 0 && (
            <p className="muted">You have no saved fields yet.</p>
          )}
          <p className="muted">{answer.pattern_note}</p>
          {et0Note && <p className="muted">{et0Note}</p>}
          <p className="muted">
            Risk: High = estimated drop at least 2× the AI&apos;s typical error, Medium = at least 1×
            (project choices). {answer.accuracy_note}
          </p>
          <p className="muted">{answer.credits.join(' · ')}</p>
        </>
      )}
    </div>
  );
}
