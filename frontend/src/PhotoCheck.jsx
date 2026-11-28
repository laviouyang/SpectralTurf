/*
 * PhotoCheck.jsx - Stage 11 on the website (2026-11-26): "Check a photo" in the AI Check tab.
 *
 * Upload or take ONE photo of turf. Our own photo classifier (backend/photo_classifier.py) says
 * which of 6 categories it LOOKS MOST LIKE, with a bar for every category. Rule approved by the
 * student (wording changed 2026-11-26 with the mentor): always "Preliminary AI result — it can be
 * wrong. Confirm with a turf expert before treating." Below the cutoff it says
 * "Uncertain — inspect in person". The photo is never stored; the server removes GPS/EXIF data.
 *
 * Upload: the original file is sent when it fits the server limits (JPEG up to 10 MB; PNG/WebP up
 * to 4 megapixels), because re-compressing as JPEG changed the model's answers in our tests.
 * Bigger photos are shrunk in the browser to 1600 px and sent as PNG (lossless).
 */
import { useRef, useState } from 'react';
import { classifyPhoto } from './api.js';
import './photocheck.css';

const MAX_BYTES = 10 * 1024 * 1024;
const MAX_PNG_WEBP_PIXELS = 4_000_000;
const BROWSER_SIDE = 1600;
const TYPES = ['image/jpeg', 'image/png', 'image/webp'];
// Shown at the bottom of the AI Diagnosis tab. Same text as photo_classifier.NOT_A_DIAGNOSIS.
export const AI_DISCLAIMER = 'Preliminary AI result — it can be wrong. Confirm with a turf expert before treating.';

function loadImage(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => resolve({ img, url });
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error('This file could not be opened as a photo (use JPEG, PNG or WebP).'));
    };
    img.src = url;
  });
}

// The file to upload: the original if it fits the limits, otherwise a 1600 px PNG copy.
async function prepare(file) {
  const { img, url } = await loadImage(file);
  const fits = file.size <= MAX_BYTES &&
    (file.type === 'image/jpeg' || img.width * img.height <= MAX_PNG_WEBP_PIXELS);
  if (fits) return { blob: file, preview: url };
  const scale = Math.min(1, BROWSER_SIDE / Math.max(img.width, img.height));
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(img.width * scale);
  canvas.height = Math.round(img.height * scale);
  canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
  const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/png'));
  if (!blob || blob.size > MAX_BYTES) throw new Error('This photo is too big, even after shrinking it.');
  return { blob, preview: url };
}

function AccuracyNote({ accuracy }) {
  if (!accuracy) return null;
  return (
    <details className="photo-accuracy">
      <summary>How accurate is this?</summary>
      <p>
        On {accuracy.test_photos} test photos the model never saw during training (kept apart by site or
        source), it picked the right category for <strong>{accuracy.accuracy_percent}%</strong> of them.
        Averaged over the 6 categories, so the small ones count equally, it was right
        for {accuracy.balanced_accuracy_percent}%. It said &ldquo;Uncertain&rdquo; for
        {' '}{accuracy.uncertain_percent}% of the test photos; on the photos it did answer, it was right
        {' '}{accuracy.answered_accuracy_percent}% of the time.
      </p>
      <p className="photo-limit">⚠ {accuracy.limitation}</p>
    </details>
  );
}

export default function PhotoCheck() {
  const upload = useRef(null);
  const camera = useRef(null);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);

  async function choose(e) {
    const file = e.target.files?.[0];
    e.target.value = ''; // lets you pick the same file again
    if (!file) return;
    setError('');
    setResult(null);
    if (!TYPES.includes(file.type)) {
      setError('Please choose a JPEG, PNG or WebP photo.');
      return;
    }
    setBusy(true);
    try {
      const { blob, preview: url } = await prepare(file);
      if (preview) URL.revokeObjectURL(preview);
      setPreview(url);
      setResult(await classifyPhoto(blob));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="photo-check">
      <p className="hint">
        Upload or take a photo of the grass. SpectralTurf AI&apos;s photo AI says which of 6 categories it
        looks most like. The photo is not stored, and its hidden GPS data is removed.
      </p>
      <input ref={upload} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={choose} />
      <input ref={camera} type="file" accept="image/jpeg,image/png,image/webp" capture="environment" hidden onChange={choose} />
      <div className="photo-buttons">
        <button type="button" className="secondary" onClick={() => upload.current.click()} disabled={busy}>
          🖼 Upload a photo
        </button>
        <button type="button" className="secondary" onClick={() => camera.current.click()} disabled={busy}>
          📷 Take a photo
        </button>
      </div>

      {preview && <img className="photo-check-preview" src={preview} alt="The photo being checked" />}
      {busy && <p className="hint">Checking the photo…</p>}
      {error && <p className="problems">{error}</p>}

      {result && (
        <div className="photo-result" aria-live="polite">
          <p className={`photo-answer${result.uncertain ? ' uncertain' : ''}`}>{result.answer}</p>
          <ul className="photo-bars">
            {result.classes.map((c) => (
              <li key={c.id} className={c.id === result.top_class.id ? 'top' : ''}>
                <span className="photo-bar-label">{c.name}</span>
                <span className="photo-bar-track"><span className="photo-bar-fill" style={{ width: `${c.percent}%` }} /></span>
                <span className="photo-bar-value">{c.percent}%</span>
              </li>
            ))}
          </ul>
          {result.uncertain && (
            <p className="hint">
              The top category is below {result.uncertain_cutoff_percent}%, so the AI doesn&apos;t pick one.
            </p>
          )}
          {result.notes.map((n) => <p key={n} className="photo-note">{n}</p>)}
          <AccuracyNote accuracy={result.accuracy} />
        </div>
      )}
    </div>
  );
}
