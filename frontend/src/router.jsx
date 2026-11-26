/*
 * router.jsx - A tiny "client-side router" (added 2026-11-23, UI redesign).
 *
 * The website has three pages: "/" (home), "/app" (the map tool) and "/about".
 * Instead of asking the server for a new page, we change the address bar with the
 * browser's History API and show a different React component. On Render, every
 * address is rewritten to index.html, so opening /app or /about directly also works.
 * (Vite's dev server does the same thing on your computer.)
 */
import { useEffect, useState } from 'react';

const CHANGE = 'spectralturf:navigate';

// Go to another page without reloading. "to" may include a #section, e.g. "/#how".
export function navigate(to) {
  const url = new URL(to, window.location.origin);
  const samePage = url.pathname === window.location.pathname;
  window.history.pushState({}, '', url.pathname + url.search + url.hash);
  window.dispatchEvent(new Event(CHANGE));
  if (url.hash) {
    // Wait for the new page to draw, then scroll to the section.
    setTimeout(() => document.getElementById(url.hash.slice(1))?.scrollIntoView({ behavior: 'smooth' }), 30);
  } else if (!samePage) {
    window.scrollTo(0, 0);
  }
}

// The current address (path + hash); updates on navigate() and the browser's Back button.
export function useLocation() {
  const read = () => ({ path: window.location.pathname.replace(/\/+$/, '') || '/', hash: window.location.hash });
  const [location, setLocation] = useState(read);
  useEffect(() => {
    const update = () => setLocation(read());
    window.addEventListener('popstate', update);
    window.addEventListener(CHANGE, update);
    return () => {
      window.removeEventListener('popstate', update);
      window.removeEventListener(CHANGE, update);
    };
  }, []);
  return location;
}

// A normal link that switches pages without reloading. Ctrl/Cmd-click still opens a new tab.
export function Link({ to, children, onClick, ...rest }) {
  return (
    <a
      href={to}
      onClick={(event) => {
        onClick?.(event);
        if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey) return;
        event.preventDefault();
        navigate(to);
      }}
      {...rest}
    >
      {children}
    </a>
  );
}
