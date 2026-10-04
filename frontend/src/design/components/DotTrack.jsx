import React, { useId } from 'react';
import { cx } from './internal';
import './display.css';
import { t } from '../../i18n';

/**
 * Accessible rating dots (attributes, abilities, disciplines, Hunger, Willpower...).
 *
 * Editable: role="slider" on the track. Keys: Right/Up +1, Left/Down -1, Home = min, End = max,
 * digits 0-9 jump. Clicking dot n sets n; clicking the current top dot clears it to n-1.
 * Read-only: role="img" with "Label: 3 of 5".
 *
 * Props: value, max (5), min (0), onChange, label (required for a11y), readOnly,
 * locked (dots up to this value are shown as fixed, e.g. base/free dots; value can't go below it),
 * shape 'dot' | 'square', tone 'blood' | 'gold' | 'arcane', showValue, valueText(fn).
 */
export default function DotTrack({
  value = 0,
  max = 5,
  min = 0,
  onChange,
  label,
  readOnly = false,
  locked = 0,
  shape = 'dot',
  tone = 'blood',
  showValue = false,
  valueText,
  hideLabel = false,
  className,
  ...rest
}) {
  const labelId = useId();
  const floor = Math.max(min, locked);
  const clamp = (v) => Math.min(max, Math.max(floor, v));
  const editable = !readOnly && typeof onChange === 'function';
  const text = valueText ? valueText(value, max) : t('common:dots.value', '{{value}} of {{max}}', { value, max });

  const set = (v) => {
    const next = clamp(v);
    if (next !== value && editable) onChange(next);
  };

  const onKeyDown = (event) => {
    if (!editable) return;
    let next = null;
    switch (event.key) {
      case 'ArrowRight':
      case 'ArrowUp':
        next = value + 1;
        break;
      case 'ArrowLeft':
      case 'ArrowDown':
        next = value - 1;
        break;
      case 'Home':
        next = floor;
        break;
      case 'End':
        next = max;
        break;
      default:
        if (/^[0-9]$/.test(event.key)) next = Number(event.key);
    }
    if (next != null) {
      event.preventDefault();
      set(next);
    }
  };

  const dots = [];
  for (let i = 1; i <= max; i += 1) {
    const filled = i <= value;
    dots.push(
      <span
        key={i}
        className="sr-dots__hit"
        data-dot={i}
        onClick={
          editable
            ? () => {
                set(i === value ? i - 1 : i);
              }
            : undefined
        }
        aria-hidden="true"
      >
        <span className={cx('sr-dots__dot', filled && 'is-filled', i <= locked && 'is-locked')} />
      </span>
    );
  }

  const trackProps = editable
    ? {
        role: 'slider',
        tabIndex: 0,
        'aria-valuemin': floor,
        'aria-valuemax': max,
        'aria-valuenow': value,
        'aria-valuetext': text,
        onKeyDown,
      }
    : { role: 'img', 'aria-label': label ? `${label}: ${text}` : text };

  return (
    <div className={cx('sr-dots', `sr-dots--${shape}`, `sr-dots--${tone}`, !editable && 'sr-dots--readonly', className)} {...rest}>
      {label ? (
        <span id={labelId} className={cx('sr-dots__label', hideLabel && 'sr-visually-hidden')} aria-hidden={!editable || undefined}>
          {label}
        </span>
      ) : null}
      <span className="sr-dots__track" aria-labelledby={editable && label ? labelId : undefined} {...trackProps}>
        {dots}
      </span>
      {showValue ? (
        <span className="sr-dots__value" aria-hidden="true">
          {value}/{max}
        </span>
      ) : null}
    </div>
  );
}
