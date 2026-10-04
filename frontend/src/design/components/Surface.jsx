import React from 'react';
import { FogLayer } from '../atmosphere/Atmosphere';
import Glyph from '../glyphs/Glyph';
import { cx } from './internal';
import './display.css';

const Corner = ({ pos }) => (
  <svg className={`sr-card__corner sr-card__corner--${pos}`} viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" focusable="false">
    <path d="M2 22V9C2 5 5 2 9 2H22" fill="none" stroke="currentColor" strokeWidth="1.2" />
    <path d="M6 22V11C6 8.2 8.2 6 11 6H22" fill="none" stroke="currentColor" strokeWidth="0.8" opacity="0.6" />
    <path d="M2 2l3 3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
    <circle cx="9.5" cy="9.5" r="1.2" fill="currentColor" />
  </svg>
);

/**
 * Card: surface + radius-lg + shadow. `ornate` adds original corner filigree.
 * `interactive` gives a hover lift (use with an inner link/button, not as a click target itself).
 */
export function Card({ as: Tag = 'div', ornate = false, interactive = false, glow, className, children, ...rest }) {
  return (
    <Tag
      className={cx('sr-card', ornate && 'sr-card--ornate', interactive && 'sr-card--interactive', glow && `sr-card--glow-${glow}`, className)}
      {...rest}
    >
      {ornate ? (
        <>
          <Corner pos="tl" />
          <Corner pos="tr" />
          <Corner pos="bl" />
          <Corner pos="br" />
        </>
      ) : null}
      {children}
    </Tag>
  );
}

/**
 * Panel: titled section (renders <section aria-labelledby>). `actions` goes in the header.
 */
export function Panel({ title, icon, actions, headingLevel = 2, className, children, ...rest }) {
  const headingId = React.useId();
  const H = `h${Math.min(Math.max(headingLevel, 1), 6)}`;
  return (
    <section className={cx('sr-panel', className)} aria-labelledby={title ? headingId : undefined} {...rest}>
      {title || actions ? (
        <header className="sr-panel__header">
          {title ? (
            <H id={headingId} className="sr-panel__title">
              {typeof icon === 'string' ? <Glyph name={icon} size={18} /> : icon}
              <span>{title}</span>
            </H>
          ) : null}
          {actions ? <div className="sr-panel__actions">{actions}</div> : null}
        </header>
      ) : null}
      <div className="sr-panel__body">{children}</div>
    </section>
  );
}

/**
 * Badge / pill.
 * tone: 'neutral' | 'blood' | 'arcane' | 'gold' | 'ok' | 'warn' | 'danger'
 * edition: e.g. "V5" / "V20" — renders the engraved edition-badge style.
 */
export function Badge({ tone = 'neutral', icon, edition, count, className, children, ...rest }) {
  if (edition) {
    return (
      <span className={cx('sr-badge', 'sr-badge--edition', `sr-badge--${tone}`, className)} {...rest}>
        <Glyph name={icon || 'ornament'} size={12} />
        <span className="sr-badge__edition">{edition}</span>
        {children ? <span className="sr-badge__extra">{children}</span> : null}
      </span>
    );
  }
  if (count != null) {
    const shown = count > 99 ? '99+' : String(count);
    return (
      <span className={cx('sr-badge', 'sr-badge--count', `sr-badge--${tone}`, className)} {...rest}>
        {shown}
      </span>
    );
  }
  return (
    <span className={cx('sr-badge', `sr-badge--${tone}`, className)} {...rest}>
      {typeof icon === 'string' ? <Glyph name={icon} size={12} /> : icon}
      {children}
    </span>
  );
}

function initials(name) {
  if (!name) return '';
  const parts = String(name).trim().split(/\s+/).filter(Boolean);
  const letters = parts.length > 1 ? parts[0][0] + parts[parts.length - 1][0] : parts[0].slice(0, 2);
  return letters.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleUpperCase();
}

/**
 * Avatar: image, or initials on an original sigil background when there's no image (or it fails).
 * size: 24 | 32 | 40 | 80. presence: 'online' | 'idle' | 'offline'.
 */
export function Avatar({ src, name, alt, size = 40, sigil = 'logo-mark', presence, className, ...rest }) {
  const [failed, setFailed] = React.useState(false);
  React.useEffect(() => setFailed(false), [src]);
  const label = alt != null ? alt : name || '';
  const showImg = src && !failed;
  return (
    <span
      className={cx('sr-avatar', className)}
      style={{ '--avatar-size': `${size}px` }}
      role={showImg ? undefined : label ? 'img' : undefined}
      aria-label={showImg ? undefined : label || undefined}
      aria-hidden={!showImg && !label ? true : undefined}
      {...rest}
    >
      {showImg ? (
        <img className="sr-avatar__img" src={src} alt={label} onError={() => setFailed(true)} />
      ) : (
        <>
          <Glyph name={sigil} size={Math.round(size * 0.86)} className="sr-avatar__sigil" />
          {size >= 32 && name ? (
            <span className="sr-avatar__initials" aria-hidden="true">
              {initials(name)}
            </span>
          ) : null}
        </>
      )}
      {presence ? (
        <span className={cx('sr-avatar__presence', `is-${presence}`)} aria-hidden="true">
          <Glyph name={presence === 'online' ? 'moon-full' : presence === 'idle' ? 'moon-crescent' : 'moon-new'} size={Math.max(10, Math.round(size * 0.3))} strokeWidth={2.4} />
        </span>
      ) : null}
    </span>
  );
}

/**
 * Divider with a central ornament glyph (or a text label). Decorative unless `label` is set.
 */
export function Divider({ ornament = 'ornament', label, className, ...rest }) {
  if (label) {
    return (
      <div className={cx('sr-divider', 'sr-divider--label', className)} role="separator" {...rest}>
        <span className="sr-divider__line" aria-hidden="true" />
        <span className="sr-divider__text">{label}</span>
        <span className="sr-divider__line" aria-hidden="true" />
      </div>
    );
  }
  return (
    <div className={cx('sr-divider', className)} role="separator" {...rest}>
      <span className="sr-divider__line" aria-hidden="true" />
      {ornament ? <Glyph name={ornament} size={18} className="sr-divider__glyph" /> : null}
      <span className="sr-divider__line" aria-hidden="true" />
    </div>
  );
}

/** Empty state: glyph, title, body, optional action. */
export function EmptyState({ glyph = 'web', title, children, action, headingLevel = 3, ambient = false, className, ...rest }) {
  const H = `h${headingLevel}`;
  return (
    <div className={cx('sr-empty', ambient && 'sr-empty--ambient', className)} {...rest}>
      {ambient ? <FogLayer intensity={0.08} speed={0.7} className="sr-empty__fog" /> : null}
      <Glyph name={glyph} size={48} className="sr-empty__glyph" />
      {title ? <H className="sr-empty__title">{title}</H> : null}
      {children ? <div className="sr-empty__body">{children}</div> : null}
      {action ? <div className="sr-empty__action">{action}</div> : null}
    </div>
  );
}

/** Keyboard key. <Kbd>Ctrl</Kbd>+<Kbd>K</Kbd> */
export function Kbd({ className, children, ...rest }) {
  return (
    <kbd className={cx('sr-kbd', className)} {...rest}>
      {children}
    </kbd>
  );
}
