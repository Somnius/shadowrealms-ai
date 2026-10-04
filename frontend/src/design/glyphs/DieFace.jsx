import React from 'react';
import './glyphs.css';

const OUTLINE = 'M12 2.2L21 9.8L20 15.2L12 21.8L4 15.2L3 9.8Z';
const FACETS = 'M3 9.8L7.6 12M21 9.8L16.4 12M12 15V21.8';

/**
 * A d10 face showing a value.
 *
 * - hunger: Hunger die (V5) — blood-tinted body and a fang notch.
 * - state: 'success' | 'fail' | 'crit' | 'one' (drives colour; also exposed as data-state).
 * - title: accessible name; defaults to e.g. "Hunger die: 10, critical".
 * - decorative: hide from assistive tech when the parent already describes the roll.
 */
export default function DieFace({ value, hunger = false, state, size = 40, title, decorative = false, className = '', ...rest }) {
  const resolved =
    state || (value === 10 ? 'crit' : value === 1 ? 'one' : value >= 6 ? 'success' : 'fail');
  const name =
    title ||
    `${hunger ? 'Hunger die' : 'Die'}: ${value}${
      { crit: ', critical', one: ', one', success: ', success', fail: '' }[resolved] || ''
    }`;
  const a11y = decorative ? { 'aria-hidden': true } : { role: 'img', 'aria-label': name };
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      className={`sr-die sr-die--${resolved}${hunger ? ' sr-die--hunger' : ''} ${className}`.trim()}
      data-state={resolved}
      data-hunger={hunger ? 'true' : undefined}
      focusable="false"
      {...a11y}
      {...rest}
    >
      <path className="sr-die__body" d={OUTLINE} />
      <path className="sr-die__facets" d={FACETS} fill="none" />
      {hunger ? <path className="sr-die__fang" d="M10.6 21L12 18.4L13.4 21" /> : null}
      <text
        className="sr-die__value"
        x="12"
        y="12.2"
        textAnchor="middle"
        dominantBaseline="central"
        aria-hidden="true"
      >
        {value}
      </text>
    </svg>
  );
}
