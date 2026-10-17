import { cx } from './internal';
import './display.css';

/**
 * Progress bar: role="progressbar" with aria-valuenow/min/max. value and max are numbers; when
 * value is null the bar is indeterminate (no aria-valuenow, a slow sweep, static under reduced motion).
 * label names it for screen readers; valueText (e.g. "Night 3 of 12") is read instead of the percent.
 */
export default function ProgressBar({ value = null, max = 100, label, valueText, tone = 'blood', className }) {
  const known = typeof value === 'number' && Number.isFinite(value) && max > 0;
  const clamped = known ? Math.min(Math.max(value, 0), max) : 0;
  const pct = known ? (clamped / max) * 100 : 0;
  return (
    <div
      className={cx('sr-progress', `sr-progress--${tone}`, !known && 'is-indeterminate', className)}
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={known ? max : undefined}
      aria-valuenow={known ? clamped : undefined}
      aria-valuetext={valueText || undefined}
    >
      <span className="sr-progress__fill" style={known ? { width: `${pct}%` } : undefined} />
    </div>
  );
}
