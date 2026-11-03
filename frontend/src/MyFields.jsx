/*
 * MyFields.jsx - Stage 10 Step 8: "My Fields" ranking.
 *
 * For a logged-in user, the backend takes every distinct field they have saved, runs the
 * AI weather check on each (real satellite + weather data), and ranks them:
 *   1) the weather does NOT explain the latest image, 2) next-week risk, 3) how far below
 *   what the AI expected. "Check these first this week."
 * It only READS saved fields; it never changes your account or history.
 */
import { useState } from 'react';
import { rankMyFields } from './api.js';

// Today's date as YYYY-MM-DD in the user's own time zone.
const today = () => new Date().toLocaleDateString('en-CA');
const signed = (x) => `${x > 0 ? '+' : ''}${x.toFixed(3)}`;

function weatherText(w) {
  if (!w) return 'weather missing';
  return `${w.rain_mm} mm rain, average high ${w.avg_high_c} °C`;
}

function RankedField({ entry, onShow }) {
  const { field, result, rank } = entry;
  const check = result.check;
  const risk = result.risk_next_week;
  const notExplained = check?.status === 'ok' && !check.weather_explains;
  const flagged = notExplained || risk?.level === 'High';
  const cardClass = result.status !== 'ok' ? 'inspect-unknown' : flagged ? 'inspect-flag' : 'inspect-calm';

  return (
    <li className={`inspect-card ranked-field ${cardClass}`}>
      <p className="inspect-headline">
        #{rank} {field.name}
      </p>

      {result.status !== 'ok' ? (
        <p>{result.message}</p>
      ) : (
        <>
          <p>
            Latest clear satellite image: <strong>{result.last_image_date}</strong>, field NDVI{' '}
            {result.actual_ndvi.toFixed(3)}
            {check.status === 'ok' && (
              <> (AI expected {check.expected_ndvi.toFixed(3)}, {signed(check.difference)})</>
            )}
          </p>
          <p>
            <strong>{check.message}</strong>
          </p>
          <p>
            Next-week risk (to {risk.target_date}): <strong>{risk.level}</strong>
            {risk.predicted_change !== undefined && <> — AI expects {signed(risk.predicted_change)} NDVI</>}
            {risk.level === 'Unknown' && <> — {risk.message}</>}
            <br />
            <span className="muted">Next 7 days: {weatherText(risk.weather_next_7_days)}.</span>
            {risk.note && <span className="muted"> {risk.note}</span>}
          </p>
          {result.geometry_note && <p className="muted">{result.geometry_note}</p>}
        </>
      )}
      <div className="button-row">
        <button type="button" className="secondary" onClick={() => onShow(field)}>
          Show on map
        </button>
      </div>
    </li>
  );
}

export default function MyFields({ user, onShow }) {
  const [asOf, setAsOf] = useState(today());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [ranking, setRanking] = useState(null);

  if (!user) {
    return <p className="muted">Log in and analyze fields to see your ranked list.</p>;
  }

  async function handleRank() {
    setBusy(true);
    setError('');
    setRanking(null);
    try {
      setRanking(await rankMyFields(asOf));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="my-fields">
      <p className="muted">
        The AI checks each field you have saved and lists which ones to check first this week.
      </p>
      <div className="dates">
        <label>
          Check as of
          <input type="date" value={asOf} max={today()} onChange={(e) => setAsOf(e.target.value)} />
        </label>
      </div>
      <button type="button" onClick={handleRank} disabled={busy || !asOf}>
        {busy ? 'Ranking…' : 'Rank my fields'}
      </button>
      {busy && <p className="muted">Getting real satellite and weather data for each field…</p>}
      {error && <p className="problems-box">{error}</p>}

      {ranking && ranking.status === 'off_season' && (
        <p className="inspect-card inspect-unknown">
          <strong>{ranking.message}</strong> The AI only works April–October. To try it now, pick a
          “Check as of” date in a past growing season (for example 2026-08-15).
        </p>
      )}
      {ranking && ranking.status === 'no_fields' && <p className="muted">{ranking.message}</p>}

      {ranking && ranking.status === 'ok' && (
        <>
          <h3>Check these first this week</h3>
          <ol className="ranked-list">
            {ranking.fields.map((entry) => (
              <RankedField key={entry.field.id} entry={entry} onShow={onShow} />
            ))}
          </ol>
          {ranking.skipped && <p className="muted">{ranking.skipped}</p>}
          <p className="muted">{ranking.rule}</p>
        </>
      )}

      {ranking && (
        <>
          <p className="next-step">
            <strong>{ranking.label}</strong> This is a way to decide where to look first, not a
            diagnosis or a watering instruction.
          </p>
          <p className="muted">{ranking.accuracy_note}</p>
          <p className="muted">{ranking.credits.join(' · ')}</p>
        </>
      )}
    </div>
  );
}
