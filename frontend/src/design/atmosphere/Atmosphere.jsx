import React, { useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { LazyMotion, domAnimation, m } from 'motion/react';
import { useAmbient, useReducedMotionPref } from '../motion';
import { cx } from '../components/internal';
import './atmosphere.css';

/**
 * FogLayer: two slow drifting fog sheets (CSS gradients, transform-only animation).
 * Put it inside a positioned container; it fills it, ignores pointer events and is aria-hidden.
 * Pauses when off-screen or the tab is hidden; static under reduced motion.
 * Never put it behind chat text (design rule): use it on login, hall and empty states.
 */
export function FogLayer({ intensity = 0.1, tint = 'bone', speed = 1, className, style }) {
  const ref = useRef(null);
  const { paused, reduced } = useAmbient(ref);
  return (
    <div
      ref={ref}
      className={cx('sr-fog', `sr-fog--${tint}`, reduced && 'is-static', className)}
      data-paused={paused ? 'true' : undefined}
      style={{ '--fog-opacity': intensity, '--fog-speed': speed, ...style }}
      aria-hidden="true"
    >
      <div className="sr-fog__sheet sr-fog__sheet--a" />
      <div className="sr-fog__sheet sr-fog__sheet--b" />
    </div>
  );
}

/**
 * CandleGlow: warm flickering light pool. Position with x/y (CSS lengths or %).
 */
export function CandleGlow({ x = '50%', y = '50%', size = 320, color = 'ember', className, style }) {
  const ref = useRef(null);
  const { paused, reduced } = useAmbient(ref);
  return (
    <div
      ref={ref}
      className={cx('sr-candle-glow', `sr-candle-glow--${color}`, reduced && 'is-static', className)}
      data-paused={paused ? 'true' : undefined}
      style={{ '--glow-x': x, '--glow-y': y, '--glow-size': `${size}px`, ...style }}
      aria-hidden="true"
    >
      <div className="sr-candle-glow__core" />
    </div>
  );
}

/* deterministic pseudo random so drips don't jump between renders */
function seeded(seed) {
  let s = seed % 2147483647;
  if (s <= 0) s += 2147483646;
  return () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

function dripPath(x, w, len) {
  // A tear hanging from the top edge, with a rounded bulb at the end.
  const bulb = Math.max(w * 0.9, 2.2);
  return [
    `M${x - w} 0`,
    `C${x - w * 0.35} ${len * 0.35} ${x - bulb} ${len - bulb * 1.6} ${x - bulb} ${len - bulb * 0.6}`,
    `A${bulb} ${bulb} 0 0 0 ${x + bulb} ${len - bulb * 0.6}`,
    `C${x + bulb} ${len - bulb * 1.6} ${x + w * 0.35} ${len * 0.35} ${x + w} 0`,
    'Z',
  ].join(' ');
}

/**
 * BloodDrip: one-shot drips from the top edge of its (positioned) parent — for botch /
 * bestial failure. Replays whenever `playKey` changes. Calls onDone when finished.
 * Reduced motion: drips are drawn in their final state at once (no movement), onDone fires.
 */
export function BloodDrip({ playKey = 0, drips = 7, maxLength = 70, seed = 7, onDone, className }) {
  const reduced = useReducedMotionPref();
  const ref = useRef(null);
  const gradId = `sr-drip-${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`;
  const [width, setWidth] = useState(400);

  useLayoutEffect(() => {
    const el = ref.current;
    if (el && el.getBoundingClientRect) {
      const w = Math.round(el.getBoundingClientRect().width);
      if (w > 0) setWidth(w);
    }
  }, [playKey]);

  const shapes = useMemo(() => {
    const rnd = seeded(seed + playKey * 31);
    const list = [];
    for (let i = 0; i < drips; i += 1) {
      const x = ((i + 0.5) / drips) * width + (rnd() - 0.5) * (width / drips) * 0.6;
      const w = 2 + rnd() * 4;
      const len = maxLength * (0.35 + rnd() * 0.65);
      list.push({ x, w, len, delay: rnd() * 0.5, d: dripPath(x, w, len), falls: rnd() > 0.45 });
    }
    return list;
  }, [drips, maxLength, seed, playKey, width]);

  const doneRef = useRef(onDone);
  doneRef.current = onDone;
  useEffect(() => {
    if (reduced) {
      if (doneRef.current) doneRef.current();
      return undefined;
    }
    const t = window.setTimeout(() => doneRef.current && doneRef.current(), 1800);
    return () => window.clearTimeout(t);
  }, [reduced, playKey]);

  const height = maxLength + 40;
  return (
    <div ref={ref} className={cx('sr-blood-drip', className)} aria-hidden="true">
      <LazyMotion features={domAnimation}>
        <svg key={playKey} width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
          <defs>
            <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#5c0a17" />
              <stop offset="55%" stopColor="#8b0000" />
              <stop offset="100%" stopColor="#c2334d" />
            </linearGradient>
          </defs>
          <rect x="0" y="0" width={width} height="3" fill="#8b0000" />
          {shapes.map((s, i) =>
            reduced ? (
              <path key={i} d={s.d} fill={`url(#${gradId})`} />
            ) : (
              <g key={i}>
                <m.path
                  d={s.d}
                  fill={`url(#${gradId})`}
                  style={{ originY: 0, originX: `${s.x}px` }}
                  initial={{ scaleY: 0 }}
                  animate={{ scaleY: 1 }}
                  transition={{ duration: 0.9, delay: s.delay, ease: [0.55, 0, 0.9, 0.4] }}
                />
                {s.falls ? (
                  <m.circle
                    cx={s.x}
                    cy={s.len}
                    r={Math.max(1.6, s.w * 0.6)}
                    fill="#c2334d"
                    initial={{ opacity: 0, y: 0 }}
                    animate={{ opacity: [0, 1, 1, 0], y: [0, 0, 26, 40] }}
                    transition={{ duration: 0.6, delay: s.delay + 0.9, ease: 'easeIn', times: [0, 0.1, 0.8, 1] }}
                  />
                ) : null}
              </g>
            )
          )}
        </svg>
      </LazyMotion>
    </div>
  );
}
