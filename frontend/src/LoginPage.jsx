/*
 * LoginPage.jsx - Version 2 (2026-11-25): a separate log-in / sign-up page at "/login",
 * between the homepage and the app. The form itself is the same LoginForm as before
 * (AccountPanel.jsx). You can also continue without an account (Analyze still works).
 */
import { useEffect, useState } from 'react';
import { Link, navigate } from './router.jsx';
import { LoginForm } from './AccountPanel.jsx';
import { SiteFooter, SiteNav } from './SiteChrome.jsx';
import { currentUser, logOut } from './api.js';

export default function LoginPage() {
  const [user, setUser] = useState(undefined); // undefined = still checking

  useEffect(() => {
    currentUser().then(setUser);
  }, []);

  return (
    <div className="site">
      <SiteNav />
      <main className="section container login-page">
        <div className="login-card">
          <h1>{user ? 'You are logged in' : 'Log in to SpectralTurf'}</h1>
          {user === undefined && <p className="muted">Checking…</p>}
          {user === null && (
            <>
              <LoginForm onUserChange={() => navigate('/app')} />
              <p className="login-skip">
                <Link to="/app">Continue without an account →</Link>
                <br />
                <span className="muted">
                  Without an account you can still draw and analyze a field. My Fields, the AI checks
                  and AI Diagnosis need an account.
                </span>
              </p>
            </>
          )}
          {user && (
            <>
              <p>
                Logged in as <strong>{user.username}</strong>.
              </p>
              <div className="button-row">
                <Link to="/app" className="btn btn-primary">Get started</Link>
                <button
                  type="button"
                  className="secondary"
                  onClick={async () => {
                    await logOut().catch(() => {});
                    setUser(null);
                  }}
                >
                  Log out
                </button>
              </div>
            </>
          )}
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}
