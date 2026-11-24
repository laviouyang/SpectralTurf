/*
 * Site.jsx - Picks the page for the current address (added 2026-11-23, UI redesign):
 *   "/"      -> HomePage (landing page)
 *   "/app"   -> App (the map tool; everything it does is unchanged)
 *   "/about" -> AboutPage (methodology)
 */
import { useEffect } from 'react';
import { Link, useLocation } from './router.jsx';
import App from './App.jsx';
import HomePage from './HomePage.jsx';
import AboutPage from './AboutPage.jsx';
import { SiteFooter, SiteNav } from './SiteChrome.jsx';

const TITLES = {
  '/': 'SpectralTurf: satellite + AI turf inspection priority',
  '/app': 'SpectralTurf app',
  '/about': 'About SpectralTurf',
};

function NotFound() {
  return (
    <div className="site">
      <SiteNav />
      <main className="section container not-found">
        <h1>Page not found</h1>
        <p>There is no page at this address.</p>
        <Link to="/" className="btn btn-primary">Go to the homepage</Link>
      </main>
      <SiteFooter />
    </div>
  );
}

export default function Site() {
  const { path } = useLocation();

  useEffect(() => {
    document.title = TITLES[path] ?? 'Page not found · SpectralTurf';
  }, [path]);

  if (path === '/') return <HomePage />;
  if (path === '/app') return <App />;
  if (path === '/about') return <AboutPage />;
  return <NotFound />;
}
