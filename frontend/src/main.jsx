import React from 'react';
import ReactDOM from 'react-dom/client';

// Styles for the map and the drawing toolbar, then our own styles.
import 'leaflet/dist/leaflet.css';
import 'leaflet-draw/dist/leaflet.draw.css';
import './App.css';
// UI redesign (2026-11-23): design system, site pages, and the app's new layout.
import './theme.css';
import './site.css';
import './appshell.css';

import Site from './Site.jsx';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <Site />
  </React.StrictMode>
);
