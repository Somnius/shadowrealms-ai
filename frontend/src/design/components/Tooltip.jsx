import { cloneElement, isValidElement, useEffect, useId, useRef, useState } from 'react';
import { cx } from './internal';
import './overlay.css';

/**
 * Tooltip around a single focusable child.
 * - Shows after `delay` ms on hover, immediately on keyboard focus; Esc hides it.
 * - describe (default true): links the tip via aria-describedby. Use describe={false} when the
 *   tip only repeats the child's accessible name (IconButton does this).
 * placement: 'top' | 'bottom' | 'left' | 'right'
 */
export default function Tooltip({ content, children, placement = 'top', delay = 400, describe = true, className }) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const timer = useRef(null);

  const clear = () => {
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = null;
  };
  const show = (immediate) => {
    clear();
    if (immediate) setOpen(true);
    else timer.current = window.setTimeout(() => setOpen(true), delay);
  };
  const hide = () => {
    clear();
    setOpen(false);
  };

  useEffect(() => clear, []);
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') {
        if (timer.current) window.clearTimeout(timer.current);
        timer.current = null;
        setOpen(false);
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open]);

  if (!isValidElement(children)) return children;
  const child = cloneElement(children, {
    'aria-describedby': describe
      ? cx(children.props['aria-describedby'], id)
      : children.props['aria-describedby'],
  });

  return (
    <span
      className={cx('sr-tooltip-anchor', className)}
      onMouseEnter={() => show(false)}
      onMouseLeave={hide}
      onFocus={() => show(true)}
      onBlur={hide}
    >
      {child}
      <span
        id={id}
        role="tooltip"
        className={cx('sr-tooltip', `sr-tooltip--${placement}`, open && 'is-open')}
        aria-hidden={!open}
      >
        {content}
      </span>
    </span>
  );
}
