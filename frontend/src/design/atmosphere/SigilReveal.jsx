import { useId, useMemo, useRef } from 'react';
import { LazyMotion, domAnimation, m } from 'motion/react';
import { lineRadial, curveLinearClosed, curveCatmullRomClosed } from 'd3-shape';
import { useInView, useReducedMotionPref } from '../motion';
import { cx } from '../components/internal';
import './atmosphere.css';

const TAU = Math.PI * 2;

/** Builds the ShadowRealms sigil (original art) as path strings, in a 100x100 box. */
export function buildSigilPaths({ thorns = 12 } = {}) {
  // Thorned ring: alternating radii, straight segments -> sharp thorns.
  const ringPts = [];
  for (let i = 0; i < thorns * 2; i += 1) {
    ringPts.push([(i / (thorns * 2)) * TAU, i % 2 === 0 ? 47 : 41.5]);
  }
  const thornRing = lineRadial().curve(curveLinearClosed)(ringPts);
  // Smooth inner ring.
  const innerPts = [];
  for (let i = 0; i < 36; i += 1) innerPts.push([(i / 36) * TAU, 36]);
  const innerRing = lineRadial().curve(curveCatmullRomClosed)(innerPts);
  return {
    // lineRadial is centred on 0,0: the SVG translates by 50,50.
    thornRing,
    innerRing,
    triangle: 'M-24 -14 L24 -14 L0 28 Z',
    crescent: 'M6 -33 A9 9 0 1 0 6 -17 A7.2 7.2 0 0 1 6 -33 Z',
    drop: 'M0 -12 C3.6 -7.4 6.2 -3.6 6.2 0.6 A6.2 6.2 0 0 1 -6.2 0.6 C-6.2 -3.6 -3.6 -7.4 0 -12 Z',
    runes: (() => {
      let d = '';
      for (let i = 0; i < 8; i += 1) {
        const a = (i / 8) * TAU + TAU / 16;
        const x0 = Math.sin(a) * 30;
        const y0 = -Math.cos(a) * 30;
        const x1 = Math.sin(a) * 33.5;
        const y1 = -Math.cos(a) * 33.5;
        d += `M${x0.toFixed(2)} ${y0.toFixed(2)}L${x1.toFixed(2)} ${y1.toFixed(2)}`;
      }
      return d;
    })(),
  };
}

/**
 * SigilReveal: the brand sigil drawn stroke by stroke (Motion pathLength), then the
 * blood drop fills in. Plays once when it scrolls into view; `replayKey` replays it.
 * Reduced motion: rendered complete, no animation.
 */
export default function SigilReveal({ size = 160, title = 'ShadowRealms', replayKey = 0, duration = 1.2, onComplete, className }) {
  const reduced = useReducedMotionPref();
  const ref = useRef(null);
  const inView = useInView(ref);
  const titleId = useId();
  const p = useMemo(() => buildSigilPaths(), []);
  const strokes = [
    { d: p.thornRing, cls: 'sr-sigil__thorns' },
    { d: p.innerRing, cls: 'sr-sigil__ring' },
    { d: p.runes, cls: 'sr-sigil__runes' },
    { d: p.triangle, cls: 'sr-sigil__tri' },
    { d: p.crescent, cls: 'sr-sigil__moon' },
  ];
  const step = duration / strokes.length;
  const play = !reduced && inView;

  return (
    <svg
      ref={ref}
      className={cx('sr-sigil', className)}
      viewBox="0 0 100 100"
      width={size}
      height={size}
      role={title ? 'img' : undefined}
      aria-labelledby={title ? titleId : undefined}
      aria-hidden={title ? undefined : true}
      focusable="false"
    >
      {title ? <title id={titleId}>{title}</title> : null}
      <LazyMotion features={domAnimation}>
        <g transform="translate(50 50)" key={replayKey}>
          {strokes.map((s, i) =>
            reduced ? (
              <path key={s.cls} d={s.d} className={s.cls} />
            ) : (
              <m.path
                key={s.cls}
                d={s.d}
                className={s.cls}
                initial={{ pathLength: 0, opacity: 0 }}
                animate={play ? { pathLength: 1, opacity: 1 } : { pathLength: 0, opacity: 0 }}
                transition={{ duration: step * 1.6, delay: i * step * 0.8, ease: [0.65, 0, 0.35, 1] }}
              />
            )
          )}
          {reduced ? (
            <path d={p.drop} className="sr-sigil__drop" />
          ) : (
            <m.path
              d={p.drop}
              className="sr-sigil__drop"
              initial={{ opacity: 0, scale: 0.4 }}
              animate={play ? { opacity: 1, scale: 1 } : { opacity: 0, scale: 0.4 }}
              transition={{ duration: 0.5, delay: duration, ease: [0.2, 0.8, 0.2, 1] }}
              onAnimationComplete={() => {
                if (play && onComplete) onComplete();
              }}
            />
          )}
        </g>
      </LazyMotion>
    </svg>
  );
}
