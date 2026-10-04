import Glyph from '../glyphs/Glyph';
import { cx } from './internal';
import './display.css';

/**
 * Loading indicator.
 * variant: 'drop' (falling blood drop, default) | 'candle' (flickering candle) | 'ring' (thin rune ring)
 * Static under reduced motion. Announced as role="status" with `label` unless `decorative`.
 */
export default function Spinner({ variant = 'drop', size = 24, label = 'Loading', decorative = false, className }) {
  const glyph =
    variant === 'candle' ? (
      <Glyph name="candle" size={size} animate />
    ) : variant === 'ring' ? (
      <Glyph name="ai-sigil" size={size} animate />
    ) : (
      <Glyph name="blood-drop" size={size} animate style={{ '--sr-glyph-fill': 'var(--sr-blood-600)' }} />
    );
  if (decorative) {
    return (
      <span className={cx('sr-spinner', `sr-spinner--${variant}`, className)} aria-hidden="true">
        {glyph}
      </span>
    );
  }
  return (
    <span className={cx('sr-spinner', `sr-spinner--${variant}`, className)} role="status">
      {glyph}
      <span className="sr-visually-hidden">{label}</span>
    </span>
  );
}
