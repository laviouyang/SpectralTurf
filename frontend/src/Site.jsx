/*
 * Site.jsx - Picks the page for the current address (added 2026-11-23, UI redesign):
 *   "/"      -> HomePage (landing page)
 *   "/app"   -> App (the map tool; everything it does is unchanged)
 *   "/about" -> AboutPage (methodology)
 *   "/how-it-works" -> HowItWorksPage, "/sources" -> SourcesPage (added 2026-11-27)
 *   "/login" -> LoginPage (Version 2: log in / sign up, between the homepage and the app)
 */
import { useEffect } from 'react';
import { Link, useLocation } from './router.jsx';
import App from './App.jsx';
import HomePage from './HomePage.jsx';
import AboutPage from './AboutPage.jsx';
import LoginPage from './LoginPage.jsx';
import HowItWorksPage from './HowItWorksPage.jsx';
import SourcesPage from './SourcesPage.jsx';
import { SiteFooter, SiteNav } from './SiteChrome.jsx';

const TITLES = {
  '/': 'SpectralTurf AI: satellite + AI turf inspection priority',
  '/app': 'SpectralTurf AI app',
  '/about': 'About SpectralTurf AI',
  '/how-it-works': 'How SpectralTurf AI works',
  '/sources': 'Sources · SpectralTurf AI',
  '/login': 'Log in · SpectralTurf AI',
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
    document.title = TITLES[path] ?? 'Page not found · SpectralTurf AI';
  }, [path]);

  if (path === '/') return <HomePage />;
  if (path === '/app') return <App />;
  if (path === '/about') return <AboutPage />;
  if (path === '/how-it-works') return <HowItWorksPage />;
  if (path === '/sources') return <SourcesPage />;
  if (path === '/login') return <LoginPage />;
  return <NotFound />;
}
