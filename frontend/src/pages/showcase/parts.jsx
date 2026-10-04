import { useEffect, useId, useRef, useState } from 'react';
import { useReducedMotionPref } from '../../design';

/** Adds `is-in` once the element is on screen (sections rise in once). Immediate without IntersectionObserver. */
export function useReveal() {
  const ref = useRef(null);
  const [shown, setShown] = useState(() => typeof window === 'undefined' || typeof window.IntersectionObserver !== 'function');
  useEffect(() => {
    if (shown) return undefined;
    const el = ref.current;
    if (!el) return undefined;
    const io = new window.IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setShown(true);
          io.disconnect();
        }
      },
      { rootMargin: '0px 0px -10% 0px' }
    );
    io.observe(el);
    return () => io.disconnect();
  }, [shown]);
  return [ref, shown];
}

/** Smooth scroll to a section (instant under reduced motion) and move focus to its heading. */
export function useScrollToSection() {
  const reduced = useReducedMotionPref();
  return (id) => {
    const el = typeof document !== 'undefined' ? document.getElementById(id) : null;
    if (!el) return;
    if (typeof el.scrollIntoView === 'function') el.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'start' });
    const heading = el.querySelector('h2, h1');
    if (heading && typeof heading.focus === 'function') heading.focus({ preventScroll: true });
  };
}

/** One numbered chapter of the tour. */
export function Section({ id, numeral, kicker, title, lede, className = '', children }) {
  const headingId = useId();
  const [ref, shown] = useReveal();
  return (
    <section
      ref={ref}
      id={`sc-${id}`}
      aria-labelledby={headingId}
      className={`sc-section sc-reveal${shown ? ' is-in' : ''} ${className}`.trim()}
      data-testid={`showcase-section-${id}`}
    >
      <header className="sc-section__head">
        <span className="sc-section__num" aria-hidden="true" lang="en">
          {numeral}
        </span>
        {kicker ? <p className="sc-kicker">{kicker}</p> : null}
        <h2 id={headingId} className="sc-section__title" tabIndex={-1}>
          {title}
        </h2>
        {lede ? <p className="sc-section__lede">{lede}</p> : null}
      </header>
      {children}
    </section>
  );
}

/**
 * Pill radio group (native radios, so arrows / Tab work as users expect).
 * options: [{ value, label, hint? }]
 */
export function PillGroup({ label, name, value, onChange, options, disabled = false, className = '', testId }) {
  const labelId = useId();
  return (
    <div className={`sc-pills ${className}`.trim()} role="radiogroup" aria-labelledby={labelId} data-testid={testId}>
      <span id={labelId} className="sc-pills__label">
        {label}
      </span>
      <div className="sc-pills__row">
        {options.map((o) => (
          <label key={o.value} className={`sc-pill${value === o.value ? ' is-on' : ''}${disabled ? ' is-disabled' : ''}`} title={o.hint || undefined}>
            <input
              type="radio"
              name={name}
              value={o.value}
              checked={value === o.value}
              disabled={disabled}
              onChange={() => onChange(o.value)}
              data-value={o.value}
            />
            <span>{o.label}</span>
          </label>
        ))}
      </div>
    </div>
  );
}
