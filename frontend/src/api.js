/*
 * api.js - The only file that talks to our backend.
 *
 * The website never contacts Copernicus directly: that would require putting
 * our secret login in the browser. Instead it asks our backend, which has the secret.
 *
 * Accounts: after logging in, the backend gives us a session token (a temporary key).
 * We keep it in the browser's localStorage so you stay logged in after a page reload,
 * and send it with each request as "Authorization: Bearer <token>".
 */

// Where the backend runs. Empty = "the same address this page came from": Vite then
// passes /api/... requests on to the backend (see vite.config.js). That way it also
// works through a share link. Can be changed with a VITE_API_URL setting.
const API_URL = import.meta.env.VITE_API_URL || '';
const TOKEN_KEY = 'spectralturf_token';

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null; // storage blocked (e.g. private window): just act logged out
  }
}

function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // ignore: you'd stay logged in only until the page reloads
  }
}

// Send one request to the backend and return its JSON, or throw a readable error.
async function request(path, { method = 'GET', body } = {}) {
  const headers = {};
  if (body) headers['Content-Type'] = 'application/json';
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  let response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
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
    const error = new Error(detail || `The backend could not process this request (HTTP ${response.status}).`);
    error.status = response.status;
    throw error;
  }
  return data;
}

// Send the drawn outline, the excluded areas inside it, and dates;
// get back real NDVI/NDMI statistics. If logged in, the backend also saves
// a summary to your history under "name" - only when save is true (Version 2: saving is a
// separate choice, "Save & analyze" vs "Analyze").
// region (added 2026-11-25): the field's grass region 1-7 (only a label; the math is the same).
export function analyzeArea(geometry, exclude, start, end, name = '', save = true, region = null) {
  return request('/api/analyze', { method: 'POST', body: { geometry, exclude, start, end, name, save, region } });
}

// Version 2: save a field (outline + excluded areas + name) to My Fields WITHOUT analyzing it.
export function saveField(name, geometry, exclude) {
  return request('/api/fields', { method: 'POST', body: { name, geometry, exclude } });
}

// ---- Accounts ----

export async function signUp(username, password) {
  const data = await request('/api/auth/signup', { method: 'POST', body: { username, password } });
  setToken(data.token);
  return data.user;
}

export async function logIn(username, password) {
  const data = await request('/api/auth/login', { method: 'POST', body: { username, password } });
  setToken(data.token);
  return data.user;
}

export async function logOut() {
  try {
    await request('/api/auth/logout', { method: 'POST' });
  } finally {
    setToken(null); // forget the token even if the backend can't be reached
  }
}

// Who is logged in? Returns null if nobody (or the saved token has expired).
export async function currentUser() {
  if (!getToken()) return null;
  try {
    return (await request('/api/auth/me')).user;
  } catch (e) {
    if (e.status === 401) setToken(null); // expired or logged out elsewhere
    return null;
  }
}

// ---- Saved history ----

export async function getHistory() {
  return (await request('/api/history')).analyses;
}

export function deleteHistoryItem(id) {
  return request(`/api/history/${id}`, { method: 'DELETE' });
}

// ---- Stage 10: AI checks ----

// Step 8: your saved fields, ranked by the AI weather check ("check these first").
export function rankMyFields(asOf) {
  return request('/api/ai/my-fields', { method: 'POST', body: { as_of: asOf } });
}

// Step 9: slider ranges (from what the AI saw in training), and one "What if?" scenario.
export function getWhatIfLimits(asOf) {
  // asOf (optional): limit the temperature slider to what happened in that month, 2019-2025
  return request(asOf ? `/api/ai/what-if/limits?as_of=${encodeURIComponent(asOf)}` : '/api/ai/what-if/limits');
}

export function runWhatIf(body) {
  return request('/api/ai/what-if', { method: 'POST', body });
}

// Stage 10 Steps 6-7: AI Weather Check for the field on the map (incl. cloudy-day estimate).
export function weatherCheck(geometry, exclude, asOf) {
  return request('/api/ai/weather-check', { method: 'POST', body: { geometry, exclude, as_of: asOf } });
}

// Stage 10 Step 10: "Ask SpectralTurf" assistant. Only the question + the field on screen are
// sent to OUR backend; the backend talks to Gemini (the Gemini key never comes to the browser).
export function askSpectralTurf(body) {
  return request('/api/ai/ask', { method: 'POST', body });
}
