/*
 * Modal.jsx - Version 2 (2026-11-25): a simple pop-up box with a title, a message and buttons.
 * Used for "replace the saved field with the same name?" and the outside-Colorado warning.
 * (We use our own box instead of the browser's confirm(), which blocks the whole page.)
 */
import { useEffect } from 'react';

// buttons: [{ label, onClick, secondary? }]. Escape or clicking outside = onClose.
export default function Modal({ title, children, buttons, onClose }) {
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose();
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal-box" role="dialog" aria-modal="true" aria-labelledby="modal-title">
        <h2 id="modal-title">{title}</h2>
        <div className="modal-body">{children}</div>
        <div className="button-row modal-buttons">
          {buttons.map((b, i) => (
            <button
              key={b.label}
              type="button"
              className={b.secondary ? 'secondary' : ''}
              onClick={b.onClick}
              autoFocus={i === 0}
            >
              {b.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
