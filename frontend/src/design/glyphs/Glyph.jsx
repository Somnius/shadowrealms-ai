import React, { forwardRef, useId } from 'react';
import { GLYPHS } from './glyphData';
import './glyphs.css';

const SHAPE_KEYS = ['d', 'c', 'e', 'r'];

function renderShape(shape, i, { draw }) {
  const props = {};
  const cls = [shape.cls];
  if (shape.f) {
    props.fill = 'currentColor';
    props.stroke = 'none';
    cls.push('sr-glyph-solid');
  } else if (shape.a) {
    props.fill = 'var(--sr-glyph-accent, currentColor)';
    props.stroke = 'none';
    cls.push('sr-glyph-solid');
  } else if (shape.dash) {
    props.strokeDasharray = shape.dash;
  } else if (draw) {
    // Normalised length so the draw-on keyframes work on every stroke.
    props.pathLength = 1;
    cls.push('sr-glyph-stroke');
  }
  if (shape.o != null) props.opacity = shape.o;
  const className = cls.filter(Boolean).join(' ') || undefined;
  if (className) props.className = className;

  if (shape.d != null) return <path key={i} {...props} d={shape.d} />;
  if (shape.c) {
    const [cx, cy, r] = shape.c;
    return <circle key={i} {...props} cx={cx} cy={cy} r={r} />;
  }
  if (shape.e) {
    const [cx, cy, rx, ry] = shape.e;
    return <ellipse key={i} {...props} cx={cx} cy={cy} rx={rx} ry={ry} />;
  }
  if (shape.r) {
    const [x, y, w, h, rx] = shape.r;
    return <rect key={i} {...props} x={x} y={y} width={w} height={h} rx={rx} />;
  }
  return null;
}

/**
 * <Glyph name="candle" size={24} title="Loading" />
 *
 * - Decorative by default (aria-hidden). Pass `title` to expose it as an image with a name.
 * - `animate` turns on the glyph's built-in CSS animation (candle flicker, eye blink, AI sigil
 *   rune spin, drop fall). `draw` plays the stroke draw-on once. Both are static under
 *   reduced motion (handled in CSS).
 * - Colour is currentColor; filled accents use --sr-glyph-accent.
 */
const Glyph = forwardRef(function Glyph(
  { name, size = 24, title, strokeWidth = 1.75, animate = false, draw = false, className = '', style, ...rest },
  ref
) {
  const titleId = useId();
  const def = GLYPHS[name];
  if (!def) {
    if (process.env.NODE_ENV !== 'production') {
      // eslint-disable-next-line no-console
      console.warn(`[design] unknown glyph "${name}"`);
    }
    return null;
  }
  const classes = [
    'sr-glyph',
    `sr-glyph--${name}`,
    animate ? 'sr-glyph--animate' : '',
    draw ? 'sr-glyph--draw' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');
  const a11y = title ? { role: 'img', 'aria-labelledby': titleId } : { 'aria-hidden': true };
  return (
    <svg
      ref={ref}
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      focusable="false"
      className={classes}
      style={style}
      data-glyph={name}
      {...a11y}
      {...rest}
    >
      {title ? <title id={titleId}>{title}</title> : null}
      {def.shapes.filter((s) => SHAPE_KEYS.some((k) => s[k] != null)).map((s, i) => renderShape(s, i, { draw }))}
    </svg>
  );
});

export default Glyph;

/* ---- animated presets (thin wrappers so call sites read clearly) ---- */

/** Candle with a flickering flame (static under reduced motion). */
export function AnimatedCandle(props) {
  return <Glyph name="candle" animate {...props} />;
}

/** Eye that blinks every ~6 s. */
export function BlinkingEye(props) {
  return <Glyph name="eye" animate {...props} />;
}

/** AI Storyteller sigil: rune ring turns slowly, eye blinks. */
export function AiSigil(props) {
  return <Glyph name="ai-sigil" animate {...props} />;
}

/** Blood drop that swells and falls (loop). */
export function DrippingBlood(props) {
  return <Glyph name="blood-drop" animate {...props} />;
}

/** Any glyph drawn on once via stroke-dashoffset. */
export function SigilDraw({ name = 'logo-mark', ...props }) {
  return <Glyph name={name} draw {...props} />;
}
