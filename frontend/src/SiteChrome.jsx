/*
 * SiteChrome.jsx - The top navigation bar and footer shared by the Home and About pages
 * (added 2026-11-23, UI redesign).
 */
import { useEffect, useState } from 'react';
import { currentUser } from './api.js';
import { Link } from './router.jsx';
import { Icon, Logo } from './Icons.jsx';

export const GITHUB_URL = 'https://github.com/laviouyang/SpectralTurf';

export function Brand() {
  return (
    <Link to="/" className="brand" aria-label="SpectralTurf home">
      <Logo size={32} />
      <span className="brand-name">SpectralTurf</span>
    </Link>
  );
}

export function SiteNav() {
  const [menuOpen, setMenuOpen] = useState(false);
  const close = () => setMenuOpen(false);
  // Version 2: if a saved login is still valid, show who is logged in (top right).
  const [user, setUser] = useState(null);
  useEffect(() => {
    currentUser().then(setUser);
  }, []);
  return (
    <header className="site-nav">
      <div className="container nav-inner">
        <Brand />
        <button
          type="button"
          className="nav-toggle"
          aria-expanded={menuOpen}
          aria-controls="site-menu"
          onClick={() => setMenuOpen(!menuOpen)}
        >
          <Icon name={menuOpen ? 'close' : 'list'} size={22} />
          <span className="visually-hidden">Menu</span>
        </button>
        <nav id="site-menu" className={`nav-menu ${menuOpen ? 'open' : ''}`} aria-label="Main">
          <div className="nav-links">
            <Link to="/#how" onClick={close}>How it works</Link>
            <Link to="/#ai" onClick={close}>AI</Link>
            <Link to="/about" onClick={close}>About</Link>
          </div>
          <div className="nav-actions">
            {user ? (
              <Link to="/app#account" className="btn btn-ghost nav-user" onClick={close} title="Your account">
                <span className="avatar" aria-hidden="true">{user.username.slice(0, 1).toUpperCase()}</span>
                Logged in as {user.username}
              </Link>
            ) : (
              <Link to="/login" className="btn btn-ghost" onClick={close}>Log in</Link>
            )}
            <Link to={user ? '/app' : '/login'} className="btn btn-primary" onClick={close}>Open the app</Link>
          </div>
        </nav>
      </div>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="container footer-grid">
        <div>
          <Brand />
          <p className="footer-disclaimer">
            Decision support, not a diagnosis or irrigation controller. A person always makes the
            final call after looking at the field.
          </p>
        </div>
        <div>
          <h2 className="footer-heading">Explore</h2>
          <ul className="footer-links">
            <li><Link to="/app">Open the app</Link></li>
            <li><Link to="/#how">How it works</Link></li>
            <li><Link to="/about">About &amp; methodology</Link></li>
            <li>
              <a href={GITHUB_URL} target="_blank" rel="noreferrer">
                <Icon name="github" size={16} /> Source code on GitHub
              </a>
            </li>
          </ul>
        </div>
        <div>
          <h2 className="footer-heading">Data credits</h2>
          <ul className="footer-links footer-credits">
            <li>
              Contains modified Copernicus Sentinel-2 data (
              <a href="https://dataspace.copernicus.eu/" target="_blank" rel="noreferrer">Copernicus Data Space Ecosystem</a>)
            </li>
            <li>
              Weather data by <a href="https://open-meteo.com/" target="_blank" rel="noreferrer">Open-Meteo.com</a>
            </li>
            <li>
              Field outlines and place search ©{' '}
              <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap contributors</a>
              {' '}(search by <a href="https://nominatim.openstreetmap.org/" target="_blank" rel="noreferrer">Nominatim</a>)
            </li>
            <li>
              Satellite photo for drawing:{' '}
              <a href="https://www.esri.com/" target="_blank" rel="noreferrer">Esri World Imagery</a>
            </li>
          </ul>
        </div>
      </div>
      <div className="container footer-bottom">© 2026 Yuanzhi Ouyang</div>
    </footer>
  );
}
