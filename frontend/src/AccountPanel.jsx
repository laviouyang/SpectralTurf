/*
 * AccountPanel.jsx - Log in / sign up, and the list of your saved analyses.
 *
 * Accounts are optional: anyone can analyze a field without one. Logged-in users
 * get every analysis saved automatically (a summary, not the map pictures), and can
 * put an old field back on the map with one click.
 */
import { useState } from 'react';
import { logIn, signUp } from './api.js';

// Short words for the saved inspection result.
const STATUS_TEXT = {
  whole_field: 'Most of field flagged',
  some_areas: 'Some areas flagged',
  no_area_stands_out: 'No area stands out',
  insufficient_evidence: 'Insufficient evidence',
};

// Exported in Version 2 so the separate log-in page (LoginPage.jsx) can use the same form.
export function LoginForm({ onUserChange }) {
  const [mode, setMode] = useState('login'); // 'login' or 'signup'
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(event) {
    event.preventDefault(); // stop the browser from reloading the page
    setBusy(true);
    setError('');
    try {
      const user = mode === 'login' ? await logIn(username, password) : await signUp(username, password);
      setPassword('');
      onUserChange(user);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="account-form" onSubmit={handleSubmit}>
      <p className="muted">
        Optional. With an account you can save fields under a name and use My Fields, the AI
        checks and Ask AI.
      </p>
      <label>
        Username
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="username"
          required
        />
      </label>
      <label>
        Password
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
          required
        />
      </label>
      {mode === 'signup' && (
        <p className="muted">
          3–30 letters, numbers, or _ for the username. At least 8 characters for the password.
          Don&apos;t use a real name or a password you use anywhere else. There is no email, so a
          forgotten password can&apos;t be reset.
        </p>
      )}
      <div className="button-row">
        <button type="submit" disabled={busy}>
          {busy ? 'Please wait…' : mode === 'login' ? 'Log in' : 'Create account'}
        </button>
        <button
          type="button"
          className="link-button"
          onClick={() => {
            setMode(mode === 'login' ? 'signup' : 'login');
            setError('');
          }}
        >
          {mode === 'login' ? 'New here? Create an account' : 'Have an account? Log in'}
        </button>
      </div>
      {error && <p className="problems-box">{error}</p>}
    </form>
  );
}

function HistoryItem({ item, onShow, onDelete }) {
  const s = item.summary;
  const stats = s.status === 'ok'
    ? `NDVI ${s.ndvi_median ?? '–'} · NDMI ${s.ndmi_median ?? '–'}`
    : 'Not enough clear pixels';
  return (
    <li className="history-item">
      <strong>{item.name}</strong>
      <span className="muted">
        Satellite image {item.observation_date} · {STATUS_TEXT[s.inspection_scope ?? s.inspection_status] ?? '–'}
      </span>
      <span className="muted">{stats} (field medians)</span>
      <div className="button-row">
        <button type="button" className="secondary" onClick={() => onShow(item)}>
          Show on map
        </button>
        <button type="button" className="link-button" onClick={() => onDelete(item)}>
          Delete
        </button>
      </div>
    </li>
  );
}

export default function AccountPanel({ user, onUserChange, onLogOut, history, historyError, onShow, onDelete }) {
  if (!user) return <LoginForm onUserChange={onUserChange} />;

  return (
    <div>
      <p>
        Logged in as <strong>{user.username}</strong>.{' '}
        <button type="button" className="link-button" onClick={onLogOut}>
          Log out
        </button>
      </p>
      <p className="muted">Fields you save with “Save &amp; analyze” are listed here.</p>
      {historyError && <p className="problems-box">{historyError}</p>}
      {history.length === 0 ? (
        <p className="muted">No saved analyses yet.</p>
      ) : (
        <details open={history.length <= 5}>
          <summary>My saved analyses ({history.length})</summary>
          <ul className="history-list">
            {history.map((item) => (
              <HistoryItem key={item.id} item={item} onShow={onShow} onDelete={onDelete} />
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

// Added 2026-11-23 (UI redesign): just the saved-analyses list, for the app's "My Fields" tab.
// Same items and buttons as above; the login form and "Log out" stay in the account menu.
export function SavedAnalyses({ history, historyError, onShow, onDelete }) {
  return (
    <div>
      {historyError && <p className="problems-box">{historyError}</p>}
      {history.length === 0 ? (
        <p className="muted">No saved analyses yet. Draw a field, give it a name and click “Save &amp; analyze”.</p>
      ) : (
        <ul className="history-list">
          {history.map((item) => (
            <HistoryItem key={item.id} item={item} onShow={onShow} onDelete={onDelete} />
          ))}
        </ul>
      )}
    </div>
  );
}
