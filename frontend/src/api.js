/*
 * api.js - The only file that talks to our backend.
 *
 * The website never contacts Copernicus directly: that would require putting
 * our secret login in the browser. Instead it asks our backend, which has the secret.
 */

// Where the backend runs. Can be changed later (for deployment) with a VITE_API_URL setting.
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Send the drawn outline, the excluded areas inside it, and dates;
// get back real NDVI/NDMI statistics.
export async function analyzeArea(geometry, exclude, start, end) {
  let response;
  try {
    response = await fetch(`${API_URL}/api/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ geometry, exclude, start, end }),
    });
  } catch {
    throw new Error(
      'Could not reach the SpectralTurf backend. Make sure it is running ' +
        '(in the backend folder: uvicorn main:app --reload).'
    );
  }

  const data = await response.json().catch(() => null);
  if (!response.ok) {
    // Our backend explains errors in "detail". Use it if it's a readable sentence.
    const detail = typeof data?.detail === 'string' ? data.detail : null;
    throw new Error(detail || `The backend could not process this request (HTTP ${response.status}).`);
  }
  return data;
}
