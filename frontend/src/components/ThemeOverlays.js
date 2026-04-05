import React from 'react';

/** Full-page loading veil (login, entering chronicle) — styles in `gothic-theme.css`. */
export function GothicPageLoadingOverlay({ visible, label }) {
  if (!visible) return null;
  return (
    <div className="sr-page-loading-overlay" role="status" aria-live="polite" aria-busy="true">
      <div className="sr-page-loading-card">
        <div className="sr-page-loading-rune" aria-hidden />
        <div className="sr-page-loading-title">ShadowRealms</div>
        <div className="sr-page-loading-sub">{label || 'One moment…'}</div>
      </div>
    </div>
  );
}

/** Brief welcome / transition card after auth — styles in `gothic-theme.css`. */
export function SessionRevealOverlay({ visible, title, subtitle }) {
  if (!visible) return null;
  return (
    <div className="sr-session-reveal-overlay" role="status" aria-live="polite">
      <div className="sr-session-reveal-card">
        <div className="sr-session-reveal-sigil" aria-hidden />
        <div className="sr-session-reveal-title">{title || 'ShadowRealms'}</div>
        <div className="sr-session-reveal-sub">{subtitle || ''}</div>
      </div>
    </div>
  );
}
