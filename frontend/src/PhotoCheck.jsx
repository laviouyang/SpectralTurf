/*
 * PhotoCheck.jsx - "Check a spot with a photo" (photo AI, Stage 9).
 *
 * The satellite shows WHERE to look. Standing at that spot, the user takes a photo and an AI
 * suggests WHAT it looks like: healthy, dry/stressed, worn/bare, or not turf, with a
 * confidence. It is a suggestion, never a diagnosis. Below the confidence cutoff it says
 * "Uncertain - inspect in person".
 *
 * On a phone, the file button opens the camera (capture="environment" = back camera).
 * The photo is sent to our backend only; it is not kept unless the box below is ticked.
 */
import { useEffect, useRef, useState } from 'react';
import { analyzePhoto } from './api.js';

const MAX_BYTES = 10 * 1024 * 1024; // same 10 MB limit as the backend
const LABEL_TEXT = {
  healthy: 'Healthy turf',
  dry_stressed: 'Dry / stressed turf',
  worn_bare: 'Worn / bare turf',
  non_turf: 'Not turf',
};
const OFF_SEASON_MONTHS = [11, 12, 1, 2, 3];

function percent(value) {
  return `${Math.round(value * 100)}%`;
}

function ProbabilityBar({ label, value, highlight }) {
  return (
    <div className={`prob-row${highlight ? ' prob-top' : ''}`}>
      <span className="prob-name">{LABEL_TEXT[label]}</span>
      <span className="prob-track">
        <span className="prob-fill" style={{ width: percent(value) }} />
      </span>
      <span className="prob-value">{percent(value)}</span>
    </div>
  );
}

function PhotoResult({ result }) {
  const probabilities = Object.entries(result.probabilities);
  return (
    <div className={`photo-result ${result.uncertain ? 'photo-uncertain' : 'photo-sure'}`}>
      {result.uncertain ? (
        <>
          <p className="photo-headline">Uncertain — inspect in person</p>
          <p className="muted">
            The AI&apos;s closest guess is {LABEL_TEXT[result.label].toLowerCase()} at only{' '}
            {percent(result.confidence)}, below this app&apos;s {percent(result.cutoff)} cutoff.
          </p>
        </>
      ) : (
        <>
          <p className="photo-headline">AI suggestion: {LABEL_TEXT[result.label]}</p>
          <ProbabilityBar label={result.label} value={result.confidence} highlight />
          <p className="muted">Confidence {percent(result.confidence)}</p>
        </>
      )}

      <p className="photo-warning">AI suggestion — confirm in person. It is not a diagnosis.</p>
      {result.off_season && (
        <p className="photo-season">
          This photo is from the off-season (Nov–Mar). In winter, Colorado turf often turns brown
          naturally (dormancy), so brown grass may be normal.
        </p>
      )}

      <details>
        <summary>All four probabilities</summary>
        {probabilities.map(([label, value]) => (
          <ProbabilityBar key={label} label={label} value={value} highlight={label === result.label} />
        ))}
      </details>
      <p className="muted small">
        Method: {result.method}. Photo date: {result.photo_date}
        {result.date_source === 'photo' ? ' (read from the photo).' : " (the photo had no date, so today's date)."}
        {result.saved_for_training && ' A copy was kept to improve the model, with location data removed.'}
      </p>
    </div>
  );
}

export default function PhotoCheck() {
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState('');
  const [allowTraining, setAllowTraining] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const requestCount = useRef(0); // so an old, slow answer can't replace a newer one

  // Show a preview of the chosen photo; free the browser's memory when it changes.
  useEffect(() => {
    if (!file) return undefined;
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  async function check(chosen) {
    const thisRequest = ++requestCount.current;
    setResult(null);
    setError('');
    if (chosen.size > MAX_BYTES) {
      setError('This photo is larger than 10 MB. Try a smaller one.');
      return;
    }
    setLoading(true);
    try {
      const data = await analyzePhoto(chosen, allowTraining);
      if (thisRequest === requestCount.current) setResult(data);
    } catch (e) {
      if (thisRequest === requestCount.current) setError(e.message);
    } finally {
      if (thisRequest === requestCount.current) setLoading(false);
    }
  }

  function handleChoose(event) {
    const chosen = event.target.files?.[0];
    event.target.value = ''; // lets the same photo be chosen again
    if (!chosen) return;
    setFile(chosen);
    check(chosen);
  }

  const month = new Date().getMonth() + 1;

  return (
    <div className="photo-check">
      <h4>Check a spot with a photo</h4>
      <p className="muted">
        At a flagged spot, photograph the grass from about 1–2 m up, pointing down, in daylight.
        An AI suggests whether it looks healthy, dry/stressed, worn/bare, or not turf.
      </p>
      {OFF_SEASON_MONTHS.includes(month) && (
        <p className="photo-season">
          It&apos;s the off-season: brown turf in Nov–Mar may be normal winter dormancy.
        </p>
      )}

      <label className="photo-consent">
        <input
          type="checkbox"
          checked={allowTraining}
          onChange={(e) => setAllowTraining(e.target.checked)}
        />
        Allow this photo to improve the model (location and other photo data are removed first).
        If unticked, the photo is not kept.
      </label>

      <label className="photo-button">
        {loading ? 'Checking photo…' : file ? 'Take or choose another photo' : 'Take or choose a photo'}
        <input
          type="file"
          accept="image/jpeg,image/png,image/webp"
          capture="environment"
          onChange={handleChoose}
          disabled={loading}
        />
      </label>

      {previewUrl && <img className="photo-preview" src={previewUrl} alt="The photo being checked" />}
      {loading && <p className="muted">The first photo can take a few seconds while the AI loads.</p>}
      {error && <p className="problems-box">{error}</p>}
      {result && <PhotoResult result={result} />}
    </div>
  );
}
