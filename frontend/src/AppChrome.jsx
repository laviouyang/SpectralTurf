/*
 * AppChrome.jsx - Small layout pieces for the map tool's new look (added 2026-11-23, UI
 * redesign): the account menu in the top bar, empty states, and loading skeletons.
 * They only arrange and style things; all the account logic stays in AccountPanel.jsx.
 */
import { useEffect, useRef } from 'react';
import { Icon } from './Icons.jsx';

// The account button (top right) and the drop-down that holds the login form / your account.
export function AccountMenu({ user, open, onOpenChange, children }) {
  const box = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => e.key === 'Escape' && onOpenChange(false);
    const onClick = (e) => box.current && !box.current.contains(e.target) && onOpenChange(false);
    document.addEventListener('keydown', onKey);
    document.addEventListener('mousedown', onClick);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('mousedown', onClick);
    };
  }, [open, onOpenChange]);

  return (
    <div className="account-menu" ref={box}>
      <button
        type="button"
        className={`account-button ${user ? 'signed-in' : ''}`}
        aria-expanded={open}
        aria-controls="account-popover"
        onClick={() => onOpenChange(!open)}
      >
        {user ? (
          <span className="avatar" aria-hidden="true">{user.username.slice(0, 1).toUpperCase()}</span>
        ) : (
          <Icon name="user" size={18} />
        )}
        <span className="account-label">{user ? user.username : 'Log in'}</span>
      </button>
      {open && (
        <div id="account-popover" className="account-popover" role="dialog" aria-label="Your account">
          <div className="popover-head">
            <h2>Your account</h2>
            <button type="button" className="icon-button" onClick={() => onOpenChange(false)} aria-label="Close">
              <Icon name="close" size={18} />
            </button>
          </div>
          {children}
        </div>
      )}
    </div>
  );
}

// A friendly "nothing here yet" message with an icon and an optional button.
export function EmptyState({ icon, title, children, action }) {
  return (
    <div className="empty-state">
      <span className="empty-icon"><Icon name={icon} size={28} /></span>
      <h3>{title}</h3>
      <div className="empty-text">{children}</div>
      {action}
    </div>
  );
}

// Gray placeholder blocks shown while real results are loading (no fake numbers).
export function ResultsSkeleton() {
  return (
    <div className="skeleton-group" aria-hidden="true">
      <div className="skeleton-row">
        <div className="skeleton skeleton-tile" />
        <div className="skeleton skeleton-tile" />
        <div className="skeleton skeleton-tile" />
      </div>
      <div className="skeleton skeleton-card" />
      <div className="skeleton skeleton-line" />
      <div className="skeleton skeleton-line short" />
    </div>
  );
}

export function Spinner() {
  return <span className="spinner" aria-hidden="true" />;
}
