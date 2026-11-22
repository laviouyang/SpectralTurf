/*
 * Panel.jsx - A sidebar section you can open and close (a "dropdown"), so the page is short.
 *
 * Uses the browser's built-in <details>/<summary>, so it works with the keyboard too.
 * - defaultOpen: open the first time someone visits
 * - the browser remembers which panels you left open (localStorage; if storage is blocked,
 *   it simply starts from defaultOpen)
 * - status: a short note shown on the header (e.g. "✓ results ready"), so you can see
 *   what's inside without opening it
 * - openWhen: when this value changes to something truthy, the panel opens by itself
 *   (e.g. when new results arrive)
 */
import { useEffect, useState } from 'react';

const STORAGE_KEY = 'spectralturf_open_panels';

function loadSaved() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {};
  } catch {
    return {};
  }
}

function save(id, open) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...loadSaved(), [id]: open }));
  } catch {
    // storage blocked (e.g. private window): the panel still works, it just isn't remembered
  }
}

export default function Panel({ id, title, status, defaultOpen = false, openWhen, className = '', children }) {
  const [open, setOpen] = useState(() => loadSaved()[id] ?? defaultOpen);

  useEffect(() => {
    if (openWhen) setOpen(true);
  }, [openWhen]);

  return (
    <details
      className={`panel ${className}`}
      open={open}
      onToggle={(e) => {
        setOpen(e.currentTarget.open);
        save(id, e.currentTarget.open);
      }}
    >
      <summary>
        <h2>{title}</h2>
        {status && <span className="panel-status">{status}</span>}
      </summary>
      <div className="panel-body">{children}</div>
    </details>
  );
}
