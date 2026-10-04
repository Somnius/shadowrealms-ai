/**
 * Phase 4 atmosphere pieces (integration layer). Everything here:
 * - is decorative (aria-hidden) unless it says otherwise,
 * - animates only transform / opacity / stroke-dashoffset,
 * - pauses when the tab is hidden or the element is off-screen (useAmbient),
 * - is static under atmosphere 'subtle' (ambient loops) and 'off' / reduced motion (everything).
 */
import React, { useEffect, useId, useMemo, useRef, useState } from 'react';
import { LazyMotion, domAnimation, m } from 'framer-motion';
import { lineRadial, curveLinearClosed } from 'd3-shape';
import { useAmbient, useMotionPreference, useReducedMotionPref } from '../motion';
import { cx } from '../components/internal';
import Glyph from '../glyphs/Glyph';
import { BloodDrip } from './Atmosphere';
import './ambience.css';

/* deterministic pseudo random (same idea as BloodDrip) */
function seeded(seed) {
  let s = Math.abs(Math.floor(seed)) % 2147483647;
  if (s <= 0) s += 2147483646;
  return () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

/** Static edge darkening. Put it in a positioned container. */
export function Vignette({ strength = 0.6, className }) {
  return <div className={cx('sr-vignette', className)} style={{ '--vignette': strength }} aria-hidden="true" />;
}

/** Film grain: an SVG noise tile; it jitters in 'full', holds still otherwise. */
export function Grain({ opacity = 0.06, className }) {
  const ref = useRef(null);
  const { paused, reduced } = useAmbient(ref);
  return (
    <div
      ref={ref}
      className={cx('sr-grain', reduced && 'is-static', className)}
      data-paused={paused ? 'true' : undefined}
      style={{ '--grain-opacity': opacity }}
      aria-hidden="true"
    />
  );
}

/**
 * CandleHalo: wraps an avatar; while `lit` a warm candle light flickers around it.
 * 'subtle' / 'off': a steady glow (still shows the state, no movement).
 */
export function CandleHalo({ lit = true, size = 32, tone = 'ember', className, children }) {
  const ref = useRef(null);
  const { paused, reduced } = useAmbient(ref);
  return (
    <span
      ref={ref}
      className={cx('sr-halo', `sr-halo--${tone}`, lit && 'is-lit', reduced && 'is-static', className)}
      data-paused={paused ? 'true' : undefined}
      style={{ '--halo-size': `${size}px` }}
    >
      {lit ? <span className="sr-halo__light" aria-hidden="true" /> : null}
      <span className="sr-halo__content">{children}</span>
    </span>
  );
}

/** Jagged crack lines from an impact point (botch / bestial failure). */
function crackPaths(seed, width, height) {
  const rnd = seeded(seed);
  const ox = width * (0.35 + rnd() * 0.3);
  const oy = height * (0.25 + rnd() * 0.3);
  const paths = [];
  const branches = 5;
  for (let b = 0; b < branches; b += 1) {
    let angle = (b / branches) * Math.PI * 2 + rnd() * 0.6;
    let x = ox;
    let y = oy;
    let d = `M${ox.toFixed(1)} ${oy.toFixed(1)}`;
    const steps = 4 + Math.floor(rnd() * 3);
    const len = Math.max(width, height) * (0.08 + rnd() * 0.08);
    for (let i = 0; i < steps; i += 1) {
      angle += (rnd() - 0.5) * 0.9;
      x += Math.cos(angle) * len * (0.7 + rnd() * 0.6);
      y += Math.sin(angle) * len * (0.5 + rnd() * 0.5);
      d += `L${x.toFixed(1)} ${y.toFixed(1)}`;
    }
    paths.push({ d, w: 1.6 - b * 0.15 });
    // a small side branch
    if (rnd() > 0.4) {
      const bx = ox + (x - ox) * 0.5;
      const by = oy + (y - oy) * 0.5;
      const a2 = angle + (rnd() > 0.5 ? 1 : -1) * (0.8 + rnd() * 0.5);
      const ex = bx + Math.cos(a2) * len * 1.2;
      const ey = by + Math.sin(a2) * len * 0.9;
      paths.push({ d: `M${bx.toFixed(1)} ${by.toFixed(1)}L${ex.toFixed(1)} ${ey.toFixed(1)}`, w: 0.9 });
    }
  }
  return { paths, ox, oy };
}

export function CrackOverlay({ playKey = 0, seed = 13, className }) {
  const reduced = useReducedMotionPref();
  const W = 400;
  const H = 200;
  const { paths } = useMemo(() => crackPaths(seed + playKey * 7, W, H), [seed, playKey]);
  return (
    <svg
      className={cx('sr-crack', className)}
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      aria-hidden="true"
      focusable="false"
      data-static={reduced ? 'true' : undefined}
    >
      <LazyMotion features={domAnimation}>
        <g key={playKey}>
          {paths.map((p, i) =>
            reduced ? (
              <path key={i} d={p.d} strokeWidth={p.w} />
            ) : (
              <m.path
                key={i}
                d={p.d}
                strokeWidth={p.w}
                initial={{ pathLength: 0, opacity: 0 }}
                animate={{ pathLength: 1, opacity: 1 }}
                transition={{ duration: 0.32, delay: 0.05 + i * 0.03, ease: [0.2, 0.8, 0.2, 1] }}
              />
            )
          )}
        </g>
      </LazyMotion>
    </svg>
  );
}

/**
 * The "mood" of a roll result, for effects:
 * 'botch' (classic) · 'bestial' / 'messy' / 'critical' (V5) · 'exceptional' (classic) · 'win' · 'fail' · null.
 */
export function rollMood(result) {
  const r = result || {};
  if (r.rules_edition === 'v5') {
    const s = Number(r.successes ?? 0);
    const d = Number(r.difficulty ?? 1);
    const win = r.outcome ? r.outcome === 'win' : s >= d && s > 0;
    if (win && r.is_messy_critical) return 'messy';
    if (win && r.is_critical) return 'critical';
    if (win) return 'win';
    if (r.is_bestial_failure) return 'bestial';
    return 'fail';
  }
  if (r.is_botch || r.botch) return 'botch';
  const s = Number(r.successes ?? 0);
  if (s <= 0) return 'fail';
  if (r.is_exceptional || r.is_critical) return 'exceptional';
  return 'win';
}

export const FOUL_MOODS = ['botch', 'bestial'];
export const GLORY_MOODS = ['critical', 'exceptional', 'messy'];

/**
 * RollFx: one-shot effect layer over a positioned dice container.
 * botch / bestial: blood drips from the top edge + a crack; messy: gold-to-blood sweep + a few drips;
 * critical / exceptional: a gold flare. Reduced motion → the static end state (crack and drips
 * drawn, no movement). `play` false (an old card in the history) → only a few dried drips.
 */
export function RollFx({ mood, playKey = 0, play = true, compact = false, className }) {
  const reduced = useReducedMotionPref();
  if (!mood || mood === 'win' || mood === 'fail') return null;
  const foul = FOUL_MOODS.includes(mood);
  if (!play) {
    // History: a quiet mark only (a few dried drips), no flash or crack.
    if (!foul && mood !== 'messy') return null;
    return (
      <div className={cx('sr-rollfx', `sr-rollfx--${mood}`, 'is-static', 'is-history', className)} aria-hidden="true" data-mood={mood}>
        <StaticDrips count={foul ? 4 : 2} />
      </div>
    );
  }
  const still = reduced;
  return (
    <div className={cx('sr-rollfx', `sr-rollfx--${mood}`, still && 'is-static', className)} aria-hidden="true" data-mood={mood}>
      {foul ? (
        <>
          <span className="sr-rollfx__flash" />
          <CrackOverlay playKey={playKey} seed={mood === 'botch' ? 31 : 17} />
          {still ? (
            <StaticDrips count={compact ? 4 : 6} />
          ) : (
            <BloodDrip playKey={playKey} drips={compact ? 4 : 7} maxLength={compact ? 26 : 54} seed={mood === 'botch' ? 5 : 11} />
          )}
        </>
      ) : null}
      {mood === 'messy' ? (
        <>
          <span className="sr-rollfx__sweep" />
          {still ? <StaticDrips count={3} /> : <BloodDrip playKey={playKey} drips={3} maxLength={compact ? 18 : 32} seed={23} />}
        </>
      ) : null}
      {mood === 'critical' || mood === 'exceptional' ? <span className="sr-rollfx__flare" /> : null}
    </div>
  );
}

/** Final drip shapes without framer (history cards, reduced motion). */
function StaticDrips({ count = 5 }) {
  const rnd = seeded(count * 97);
  const drips = Array.from({ length: count }, (_, i) => ({
    left: `${((i + 0.5) / count) * 100 + (rnd() - 0.5) * 8}%`,
    h: 8 + rnd() * 16,
  }));
  return (
    <span className="sr-rollfx__static-drips">
      {drips.map((d, i) => (
        <span key={i} style={{ left: d.left, height: `${d.h}px` }} />
      ))}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Chronicle sigil                                                      */
/* ------------------------------------------------------------------ */

const TAU = Math.PI * 2;
const LINE_GLYPH = {
  vampire: 'line-vampire',
  werewolf: 'line-werewolf',
  mage: 'line-mage',
  wraith: 'line-wraith',
  changeling: 'line-changeling',
};

function sigilRing(edition) {
  if (edition === 'v5') {
    // thorned ring (sharp, modern edition)
    const pts = [];
    const thorns = 16;
    for (let i = 0; i < thorns * 2; i += 1) pts.push([(i / (thorns * 2)) * TAU, i % 2 === 0 ? 30 : 27]);
    return { outer: lineRadial().curve(curveLinearClosed)(pts), inner: null };
  }
  // classic: double ring with rune ticks (older, engraved feel)
  const circle = (r) => `M${-r} 0A${r} ${r} 0 1 0 ${r} 0A${r} ${r} 0 1 0 ${-r} 0`;
  let ticks = '';
  for (let i = 0; i < 12; i += 1) {
    const a = (i / 12) * TAU;
    const r0 = 25.5;
    const r1 = i % 3 === 0 ? 30.5 : 28.5;
    ticks += `M${(Math.sin(a) * r0).toFixed(2)} ${(-Math.cos(a) * r0).toFixed(2)}L${(Math.sin(a) * r1).toFixed(2)} ${(-Math.cos(a) * r1).toFixed(2)}`;
  }
  return { outer: circle(30.5), inner: `${circle(25.5)}${ticks}` };
}

/**
 * ChronicleSigil: the game line's mark inside an edition ring (thorns for V5, engraved double ring
 * for the classic editions). The ring is drawn on once when it comes into view; on hover / focus of
 * the closest `.sr-sigil-host` the ring turns and the line's own motif plays (vampire: a drop falls,
 * werewolf: the moon waxes, mage: a spark orbits, wraith: the veil drifts, changeling: thorns sway).
 * Decorative unless `title` is given.
 */
export function ChronicleSigil({ line, edition = 'classic', size = 56, title, className }) {
  const ref = useRef(null);
  const { atmosphere } = useMotionPreference();
  const { paused } = useAmbient(ref);
  const [drawn, setDrawn] = useState(false);
  const titleId = useId();
  const ring = useMemo(() => sigilRing(edition === 'v5' ? 'v5' : 'classic'), [edition]);
  const glyph = LINE_GLYPH[line] || 'logo-mark';
  const still = atmosphere === 'off';

  // Draw-on once, the first time it is on screen.
  useEffect(() => {
    if (drawn || still) return undefined;
    const el = ref.current;
    if (!el || typeof window.IntersectionObserver !== 'function') {
      setDrawn(true);
      return undefined;
    }
    const io = new window.IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) {
        setDrawn(true);
        io.disconnect();
      }
    });
    io.observe(el);
    return () => io.disconnect();
  }, [drawn, still]);

  return (
    <span
      ref={ref}
      className={cx('sr-csigil', `sr-csigil--${line || 'none'}`, `sr-csigil--${edition === 'v5' ? 'v5' : 'classic'}`, still && 'is-static', drawn && 'is-drawn', className)}
      data-paused={paused ? 'true' : undefined}
      data-line={line || undefined}
      style={{ width: size, height: size }}
      role={title ? 'img' : undefined}
      aria-labelledby={title ? titleId : undefined}
      aria-hidden={title ? undefined : true}
    >
      {title ? (
        <span id={titleId} className="sr-visually-hidden">
          {title}
        </span>
      ) : null}
      <svg className="sr-csigil__ring" viewBox="-32 -32 64 64" width={size} height={size} focusable="false" aria-hidden="true">
        <g className="sr-csigil__spin">
          <path className="sr-csigil__outer" d={ring.outer} pathLength="1" />
          {ring.inner ? <path className="sr-csigil__inner" d={ring.inner} pathLength="1" /> : null}
        </g>
        {line === 'vampire' ? <circle className="sr-csigil__drop" cx="0" cy="13" r="1.8" /> : null}
        {line === 'werewolf' ? <circle className="sr-csigil__moon" cx="0" cy="0" r="17" /> : null}
        {line === 'mage' ? (
          <g className="sr-csigil__orbit">
            <circle className="sr-csigil__spark" cx="0" cy="-22" r="1.6" />
          </g>
        ) : null}
        {line === 'wraith' ? <path className="sr-csigil__veil" d="M-18 10Q-9 4 0 10T18 10" /> : null}
      </svg>
      <span className="sr-csigil__mark">
        <Glyph name={glyph} size={Math.round(size * 0.46)} />
      </span>
    </span>
  );
}

/**
 * RouteTransition: short fade + 6 px rise when `routeKey` changes (framer LazyMotion, ~180 ms).
 * Enter only (no exit), so the old page is never kept mounted. Off under reduced motion.
 * The wrapper is a flex column that fills its parent, so page layout is unchanged.
 */
export function RouteTransition({ routeKey, className, children }) {
  const reduced = useReducedMotionPref();
  // Same element type in both modes, so switching the atmosphere never remounts the page.
  return (
    <LazyMotion features={domAnimation}>
      <m.div
        key={routeKey}
        className={cx('sr-route', className)}
        data-route={routeKey}
        initial={reduced ? false : { opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: reduced ? 0 : 0.18, ease: [0.2, 0.8, 0.2, 1] }}
      >
        {children}
      </m.div>
    </LazyMotion>
  );
}
