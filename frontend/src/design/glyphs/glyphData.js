/**
 * ShadowRealms original glyph set. Hand-authored for this repo (same licence as the repo).
 *
 * Grid: 24x24, stroke 1.75, round caps/joins, currentColor.
 * Shape format (compact, rendered by <Glyph>):
 *   { d }                path
 *   { c: [cx, cy, r] }   circle
 *   { e: [cx, cy, rx, ry] } ellipse
 *   { r: [x, y, w, h, rx] } rect
 * Flags: f = filled with currentColor (no stroke), a = filled with --sr-glyph-accent (no stroke),
 *        dash = stroke-dasharray (user units), cls = extra class (used by animated variants),
 *        o = opacity.
 *
 * Originality rule: clan/discipline sigils are abstract and must NOT redraw the composition of
 * official White Wolf / Paradox logos (no rose, dragon, rune, eye for Salubri, crown for Ventrue,
 * circle-A for Brujah). Ids are generic, the art is ours.
 */

const C = 12;
const n = (v) => Math.round(v * 100) / 100;
const pt = (r, deg, cx = C, cy = C) => {
  const a = (deg * Math.PI) / 180;
  return [n(cx + r * Math.cos(a)), n(cy + r * Math.sin(a))];
};

/** Circular arc path from angle a0 to a1 (degrees, clockwise on screen). */
function arc(r, a0, a1, cx = C, cy = C) {
  const [x0, y0] = pt(r, a0, cx, cy);
  const [x1, y1] = pt(r, a1, cx, cy);
  const large = Math.abs(a1 - a0) > 180 ? 1 : 0;
  return `M${x0} ${y0}A${r} ${r} 0 ${large} 1 ${x1} ${y1}`;
}

/** Radial ticks: count ticks between radii r0..r1, starting at angle start. */
function ticks(count, r0, r1, start = -90, cx = C, cy = C) {
  let d = '';
  for (let i = 0; i < count; i += 1) {
    const deg = start + (360 / count) * i;
    const [x0, y0] = pt(r0, deg, cx, cy);
    const [x1, y1] = pt(r1, deg, cx, cy);
    d += `M${x0} ${y0}L${x1} ${y1}`;
  }
  return d;
}

/** Gear outline with `teeth` teeth. */
function gear(teeth, rOut, rIn) {
  const step = 360 / teeth;
  let d = '';
  for (let i = 0; i < teeth; i += 1) {
    const base = -90 + i * step;
    const pts = [
      pt(rIn, base - step * 0.5),
      pt(rIn, base - step * 0.28),
      pt(rOut, base - step * 0.18),
      pt(rOut, base + step * 0.18),
      pt(rIn, base + step * 0.28),
    ];
    for (let j = 0; j < pts.length; j += 1) {
      d += `${i === 0 && j === 0 ? 'M' : 'L'}${pts[j][0]} ${pts[j][1]}`;
    }
  }
  return `${d}Z`;
}

/** Star polygon with `points` points. */
function star(points, rOut, rIn, cx = C, cy = C, start = -90) {
  let d = '';
  for (let i = 0; i < points * 2; i += 1) {
    const r = i % 2 === 0 ? rOut : rIn;
    const [x, y] = pt(r, start + (180 / points) * i, cx, cy);
    d += `${i === 0 ? 'M' : 'L'}${x} ${y}`;
  }
  return `${d}Z`;
}

/** Archimedean spiral from rStart to ~0. */
function spiral(turns, rStart) {
  const steps = Math.round(turns * 24);
  let d = '';
  for (let i = 0; i <= steps; i += 1) {
    const t = i / steps;
    const r = rStart * (1 - t) + 0.6 * t;
    const [x, y] = pt(r, -90 + 360 * turns * t);
    d += `${i === 0 ? 'M' : 'L'}${x} ${y}`;
  }
  return d;
}

/** Spider web: spokes + sagging rings. */
function web() {
  const spokes = 8;
  const rings = [3.2, 6.2, 9.2];
  let d = ticks(spokes, 0.6, 10.2, -90);
  rings.forEach((r) => {
    for (let i = 0; i < spokes; i += 1) {
      const a0 = -90 + (360 / spokes) * i;
      const a1 = a0 + 360 / spokes;
      const [x0, y0] = pt(r, a0);
      const [x1, y1] = pt(r, a1);
      const [cx, cy] = pt(r * 0.78, (a0 + a1) / 2);
      d += `M${x0} ${y0}Q${cx} ${cy} ${x1} ${y1}`;
    }
  });
  return d;
}

const DROP = 'M12 2.8C12 2.8 5.6 10.1 5.6 14.6a6.4 6.4 0 0 0 12.8 0C18.4 10.1 12 2.8 12 2.8Z';
const smallDrop = (x, y, s = 1) =>
  `M${x} ${y}c${n(0.9 * s)} ${n(1.15 * s)} ${n(1.35 * s)} ${n(1.95 * s)} ${n(1.35 * s)} ${n(2.6 * s)}a${n(
    1.35 * s
  )} ${n(1.35 * s)} 0 0 1 ${n(-2.7 * s)} 0c0 ${n(-0.65 * s)} ${n(0.45 * s)} ${n(-1.45 * s)} ${n(1.35 * s)} ${n(-2.6 * s)}Z`;
const D10 = 'M12 2.2L21 9.8L20 15.2L12 21.8L4 15.2L3 9.8Z';
const D10_FACETS = 'M12 2.2L7.6 12L12 15L16.4 12ZM3 9.8L7.6 12M21 9.8L16.4 12M12 15V21.8';
const ALMOND = 'M2.5 12C5.8 6.8 18.2 6.8 21.5 12C18.2 17.2 5.8 17.2 2.5 12Z';
const MOON = { c: [12, 12, 8.5] };

export const GLYPHS = {
  /* ---------------- dice ---------------- */
  d10: { label: 'Ten-sided die', group: 'dice', shapes: [{ d: D10 }, { d: D10_FACETS, o: 0.75 }] },
  'd10-crit': {
    label: 'Critical die',
    group: 'dice',
    shapes: [{ d: D10 }, { d: 'M3 9.8L7.6 12M21 9.8L16.4 12M12 15V21.8M7.6 12L12 15L16.4 12', o: 0.75 }, { d: star(4, 3.6, 1.1, 12, 9.4), a: 1 }],
  },
  'd10-hunger': {
    label: 'Hunger die',
    group: 'dice',
    shapes: [
      { d: D10 },
      { d: 'M3 9.8L7.6 12M21 9.8L16.4 12M7.6 12L12 15L16.4 12M12 15V21.8', o: 0.75 },
      { d: 'M9.6 6.8Q12 8.2 14.4 6.8L12 12.6Z', a: 1 },
    ],
  },
  'd10-botch': {
    label: 'Botched die',
    group: 'dice',
    shapes: [
      { d: D10 },
      { d: 'M3 9.8L7.6 12M21 9.8L16.4 12M12 15V21.8', o: 0.75 },
      { d: 'M12 2.2L10.6 6.4L13 8.4L10.8 11.2L12.6 13.4' },
      { d: smallDrop(16.2, 14.2, 1), a: 1 },
    ],
  },

  /* ---------------- blood & body ---------------- */
  'blood-drop': {
    label: 'Blood drop',
    group: 'horror',
    shapes: [{ d: DROP, cls: 'sr-glyph-fillable' }, { d: 'M8.9 14.4a3.2 3.2 0 0 0 2.4 3.3' }],
  },
  fangs: {
    label: 'Fangs',
    group: 'horror',
    shapes: [
      { d: 'M3 7.2Q12 12.4 21 7.2' },
      { d: 'M7.4 9.3L9 16.2L10.4 10.4' },
      { d: 'M16.6 9.3L15 16.2L13.6 10.4' },
      { d: 'M5 17.4Q12 22.2 19 17.4' },
    ],
  },
  eye: {
    label: 'Eye',
    group: 'horror',
    shapes: [
      { d: ALMOND },
      { c: [12, 12, 3.3] },
      { d: 'M12 9.4Q13.1 12 12 14.6Q10.9 12 12 9.4Z', a: 1 },
    ],
  },
  'eye-shut': {
    label: 'Closed eye',
    group: 'horror',
    shapes: [{ d: 'M2.5 10.5C5.8 15.4 18.2 15.4 21.5 10.5' }, { d: 'M5.6 13.4L4 16M9 14.8L8.3 17.7M12 15.3V18.3M15 14.8L15.7 17.7M18.4 13.4L20 16' }],
  },
  skull: {
    label: 'Skull',
    group: 'horror',
    shapes: [
      {
        d: 'M12 2.5C7.1 2.5 4.5 6 4.5 10c0 2.6 1.2 4.3 2.8 5.3V19a1.5 1.5 0 0 0 1.5 1.5h6.4a1.5 1.5 0 0 0 1.5-1.5v-3.7c1.6-1 2.8-2.7 2.8-5.3C19.5 6 16.9 2.5 12 2.5Z',
      },
      { c: [9, 11, 1.8], a: 1 },
      { c: [15, 11, 1.8], a: 1 },
      { d: 'M12 13.4L11 15.3H13Z', f: 1 },
      { d: 'M10.2 17.6V20.4M12 17.6V20.4M13.8 17.6V20.4' },
    ],
  },
  candle: {
    label: 'Candle',
    group: 'horror',
    shapes: [
      { d: 'M9.5 21V11.2h5V21' },
      { d: 'M14.5 13.2c0 1.6-1.3 1.6-1.3 0' },
      { d: 'M6.5 21h11' },
      { d: 'M12 11.2V9.6' },
      { d: 'M12 2.6c1.8 2.1 2.4 3.5 2.4 4.5a2.4 2.4 0 0 1-4.8 0c0-1 .6-2.4 2.4-4.5Z', a: 1, cls: 'sr-glyph-flame' },
    ],
  },
  raven: {
    label: 'Raven',
    group: 'horror',
    shapes: [
      {
        d: 'M4 13.2C6 9.2 9.8 7.6 13 8.1L15.4 5.6C16.5 4.6 18.4 4.8 19 6L21.2 7L19.1 7.8C19.1 11 17 14 13.5 15.5L9 17.1L4.4 20L6 16Z',
      },
      { c: [17.2, 6.4, 0.75], f: 1 },
      { d: 'M8 12.6C10 11.1 13 11.1 15 12' },
      { d: 'M11.6 16.4L11.1 19.6M13.6 15.6L14 19.6M8.5 19.6H18' },
    ],
  },
  bat: {
    label: 'Bat',
    group: 'horror',
    shapes: [
      {
        d: 'M12 9.2C10.5 7.2 8 6.6 2 7.6C4 9.1 4.5 10.6 4 12.6C5.5 11.6 7 11.6 8 12.9C9 11.9 10.3 12.1 12 14.6C13.7 12.1 15 11.9 16 12.9C17 11.6 18.5 11.6 20 12.6C19.5 10.6 20 9.1 22 7.6C16 6.6 13.5 7.2 12 9.2Z',
      },
      { d: 'M10.9 8.4L10.5 6.6L11.5 7.6H12.5L13.5 6.6L13.1 8.4' },
    ],
  },
  chalice: {
    label: 'Chalice',
    group: 'horror',
    shapes: [
      { d: 'M6 3.5h12c0 5-2.5 8.5-6 8.5S6 8.5 6 3.5Z' },
      { d: 'M12 12v6' },
      { d: 'M8 20.5c0-1.5 1.8-2.5 4-2.5s4 1 4 2.5Z' },
      { d: smallDrop(12, 5.2, 0.95), a: 1 },
    ],
  },
  'vitae-sigil': {
    label: 'Vitae sigil (original)',
    group: 'horror',
    shapes: [
      { d: 'M12 10.6C9.6 8.7 9 6.7 9 5.6a3 3 0 0 1 6 0c0 1.1-.6 3.1-3 5Z' },
      { d: 'M12 10.6V21M7 13.6h10' },
      { d: 'M8.4 18.4Q12 21.6 15.6 18.4' },
    ],
  },
  dagger: {
    label: 'Dagger',
    group: 'horror',
    shapes: [
      { d: 'M12 2.5L13.6 13H10.4Z' },
      { d: 'M12 5.2V11', o: 0.7 },
      { d: 'M7.4 13.8Q12 12.2 16.6 13.8' },
      { d: 'M12 13.4V18.8' },
      { c: [12, 20.3, 1.3] },
    ],
  },
  cross: {
    label: 'Cross',
    group: 'horror',
    shapes: [{ d: 'M12 2.5V21.5M6 8h12' }, { d: 'M10.6 21.5h2.8M6 6.8v2.4M18 6.8v2.4M10.8 2.5h2.4' }],
  },
  'thorned-rose': {
    label: 'Thorned bud (original)',
    group: 'horror',
    shapes: [
      { d: 'M12 3C9 3 7.6 5.4 7.6 7.4C7.6 9.9 9.6 11.4 12 11.4S16.4 9.9 16.4 7.4C16.4 5.4 15 3 12 3Z' },
      { d: 'M12 5.6c-1.4 0-2 1-2 1.9s.9 1.8 2 1.8 1.6-.7 1.6-1.5-.6-1.2-1.4-1.2' },
      { d: 'M12 11.4C11 15 13 17.5 12 21.5' },
      { d: 'M11.9 14L10.3 13.4M12.5 17L14.1 16.5M12.1 19.6L10.6 19.8' },
      { d: 'M12.3 16C14 14 16.5 14 17.5 15C16 16.7 14 17 12.3 16Z' },
    ],
  },
  coffin: {
    label: 'Coffin',
    group: 'horror',
    shapes: [{ d: 'M9 2.5h6l3 5-2.5 14h-7L6 7.5Z' }, { d: 'M12 7v7M9.8 9.4h4.4' }],
  },
  key: {
    label: 'Key',
    group: 'horror',
    shapes: [{ c: [7, 12, 3.5] }, { c: [7, 12, 1.1] }, { d: 'M10.5 12H21M18 12v3M15.5 12v2.2' }],
  },
  'lock-chain': {
    label: 'Locked',
    group: 'horror',
    shapes: [
      { r: [5, 10.5, 14, 10, 2] },
      { d: 'M8 10.5V7.5a4 4 0 0 1 8 0v3' },
      { c: [12, 14.6, 1.3], f: 1 },
      { d: 'M12 15.6V17.6' },
    ],
  },
  chain: {
    label: 'Chain',
    group: 'horror',
    shapes: [
      { d: 'M4.4 16.6l3-3a2.1 2.1 0 0 1 3 3l-3 3a2.1 2.1 0 0 1-3-3Z' },
      { d: 'M13.6 7.4l3-3a2.1 2.1 0 0 1 3 3l-3 3a2.1 2.1 0 0 1-3-3Z' },
      { d: 'M9.4 10.6l1.7-1.7a2.1 2.1 0 0 1 3 0M14.6 13.4l-1.7 1.7a2.1 2.1 0 0 1-3 0' },
    ],
  },
  scroll: {
    label: 'Scroll',
    group: 'horror',
    shapes: [
      { d: 'M8 5H18V17' },
      { d: 'M8 5a2 2 0 1 0-4 0v.5h4V18' },
      { d: 'M18 17v1a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-1h10v1a2 2 0 0 0 2 2' },
      { d: 'M10.6 9h5M10.6 12h5', o: 0.75 },
    ],
  },
  book: {
    label: 'Tome',
    group: 'horror',
    shapes: [
      { d: 'M5 4.5A1.5 1.5 0 0 1 6.5 3H19v15H6.5A1.5 1.5 0 0 0 5 19.5Z' },
      { d: 'M5 19.5A1.5 1.5 0 0 0 6.5 21H19v-3' },
      { d: 'M12 6.6l2 2.9-2 2.9-2-2.9Z' },
    ],
  },
  mask: {
    label: 'Mask',
    group: 'horror',
    shapes: [
      { d: 'M2.5 9C5 7 9 7.5 12 9.5C15 7.5 19 7 21.5 9C21.5 13.5 19 16 16 16C14 16 12.8 14.5 12 13C11.2 14.5 10 16 8 16C5 16 2.5 13.5 2.5 9Z' },
      { d: 'M6 11q1.7-1.3 3.4 0q-1.7 1.3-3.4 0Z', f: 1 },
      { d: 'M14.6 11q1.7-1.3 3.4 0q-1.7 1.3-3.4 0Z', f: 1 },
    ],
  },
  hood: {
    label: 'Hooded figure',
    group: 'horror',
    shapes: [
      { d: 'M4 21C4 13 6.5 3 12 3S20 13 20 21' },
      { d: 'M8 21C8 15 9.5 9.6 12 9.6S16 15 16 21' },
      { c: [10.6, 14, 0.8], a: 1 },
      { c: [13.4, 14, 0.8], a: 1 },
      { d: 'M3 21h18' },
    ],
  },
  crown: {
    label: 'Crown',
    group: 'horror',
    shapes: [{ d: 'M3.6 18L2.6 7.6L8 11.5L12 4.6L16 11.5L21.4 7.6L20.4 18Z' }, { d: 'M4 21h16' }, { c: [12, 14.6, 1], a: 1 }],
  },
  'crown-thorns': {
    label: 'Crown of thorns',
    group: 'horror',
    shapes: [
      { e: [12, 14, 8.5, 3.5] },
      { d: 'M5.6 11.7L4.6 9M9 10.7L8.6 7.6M12 10.5V7M15 10.7L15.4 7.6M18.4 11.7L19.4 9' },
      { d: 'M7 17.2L6.4 19.6M12 17.5V20.1M17 17.2L17.6 19.6' },
    ],
  },
  web: { label: 'Web', group: 'horror', shapes: [{ d: web() }] },
  hourglass: {
    label: 'Hourglass',
    group: 'horror',
    shapes: [
      { d: 'M6 3h12M6 21h12' },
      { d: 'M7.5 3C7.5 8 12 9.5 12 12S7.5 16 7.5 21M16.5 3C16.5 8 12 9.5 12 12S16.5 16 16.5 21' },
      { d: 'M9.4 19.6Q12 16.4 14.6 19.6Z', a: 1 },
    ],
  },
  quill: {
    label: 'Quill',
    group: 'horror',
    shapes: [
      { d: 'M20 3C12.5 4 7.5 9.5 6.5 16L5.5 21' },
      { d: 'M20 3C19.5 10 15 14.5 7 15.5' },
      { d: 'M10 11L14.5 10.5M12.5 7.8L17 7.5', o: 0.75 },
    ],
  },
  'ai-sigil': {
    label: 'AI Storyteller sigil',
    group: 'horror',
    shapes: [
      { c: [12, 12, 7.2] },
      { d: ticks(8, 8.7, 10.6), cls: 'sr-glyph-runes' },
      { d: 'M6.6 12C8.5 9.2 15.5 9.2 17.4 12C15.5 14.8 8.5 14.8 6.6 12Z', cls: 'sr-glyph-lid' },
      { c: [12, 12, 1.6], a: 1, cls: 'sr-glyph-lid' },
    ],
  },
  'logo-mark': {
    label: 'ShadowRealms mark',
    group: 'horror',
    shapes: [
      { c: [12, 12, 9.6] },
      { d: 'M5 8.2L12 20.4L19 8.2Z' },
      { d: 'M14.6 4.4a5 5 0 1 0 0 7.4a4 4 0 0 1 0-7.4Z', o: 0.85 },
      { d: smallDrop(12, 11.2, 0.95), a: 1 },
    ],
  },

  /* ---------------- moons ---------------- */
  'moon-new': { label: 'New moon', group: 'moon', shapes: [MOON] },
  'moon-crescent': {
    label: 'Crescent moon',
    group: 'moon',
    shapes: [MOON, { d: 'M12 3.5A8.5 8.5 0 0 1 12 20.5A5.2 8.5 0 0 0 12 3.5Z', a: 1 }],
  },
  'moon-half': { label: 'Half moon', group: 'moon', shapes: [MOON, { d: 'M12 3.5A8.5 8.5 0 0 1 12 20.5Z', a: 1 }] },
  'moon-gibbous': {
    label: 'Gibbous moon',
    group: 'moon',
    shapes: [MOON, { d: 'M12 3.5A8.5 8.5 0 0 1 12 20.5A5.2 8.5 0 0 1 12 3.5Z', a: 1 }],
  },
  'moon-full': { label: 'Full moon', group: 'moon', shapes: [{ c: [12, 12, 8.5], a: 1 }, MOON] },

  /* ---------------- rooms ---------------- */
  'room-ooc': {
    label: 'Out-of-character room (lantern)',
    group: 'room',
    shapes: [
      { d: 'M12 2.5V4M9.5 4h5' },
      { d: 'M8 6.5L9.5 4h5L16 6.5Z' },
      { r: [8, 6.5, 8, 11, 1] },
      { d: 'M7 17.5h10v2H7Z' },
      { d: 'M12 9.4c1 1.2 1.3 2 1.3 2.7a1.3 1.3 0 0 1-2.6 0c0-.7.3-1.5 1.3-2.7Z', a: 1, cls: 'sr-glyph-flame' },
    ],
  },
  'room-elysium': {
    label: 'Elysium',
    group: 'room',
    shapes: [{ d: 'M3 7L12 3.2L21 7Z' }, { d: 'M4 9h16M3.5 18h17M2.5 21h19' }, { d: 'M7 9v9M17 9v9M5.6 9.2h2.8M15.6 9.2h2.8' }],
  },
  'room-haven': {
    label: 'Haven',
    group: 'room',
    shapes: [
      { d: 'M3 11L12 3.5L21 11' },
      { d: 'M5 9.4V20.5h14V9.4' },
      { d: 'M13.2 10.4a3 3 0 1 0 0 5.2a2.4 2.4 0 0 1 0-5.2Z', a: 1 },
    ],
  },
  'room-street': {
    label: 'Street',
    group: 'room',
    shapes: [
      { d: 'M12 9.2V21M9 21h6' },
      { d: 'M8.6 4h6.8L14.4 9.2H9.6Z' },
      { d: 'M10.4 4L12 2.4L13.6 4' },
      { c: [12, 6.6, 1.2], a: 1, cls: 'sr-glyph-flame' },
    ],
  },

  /* ---------------- UI ---------------- */
  menu: { label: 'Menu', group: 'ui', shapes: [{ d: 'M4 6.5h16M4 12h16M4 17.5h16' }] },
  close: { label: 'Close', group: 'ui', shapes: [{ d: 'M6 6L18 18M18 6L6 18' }] },
  send: { label: 'Send', group: 'ui', shapes: [{ d: 'M3.5 11.4L20.5 4L14 20.5L11 13Z' }, { d: 'M11 13L20.5 4' }] },
  settings: { label: 'Settings', group: 'ui', shapes: [{ d: gear(8, 9.6, 7.2) }, { c: [12, 12, 3] }] },
  user: { label: 'User', group: 'ui', shapes: [{ c: [12, 8, 3.8] }, { d: 'M4.5 20.5c0-4 3.4-6.5 7.5-6.5s7.5 2.5 7.5 6.5' }] },
  users: {
    label: 'Users',
    group: 'ui',
    shapes: [{ c: [9, 8.5, 3.4] }, { d: 'M2.5 20c0-3.6 2.9-5.8 6.5-5.8s6.5 2.2 6.5 5.8' }, { d: 'M15 5.4a3.2 3.2 0 0 1 0 6.2M17.2 14.6c2.6.6 4.3 2.6 4.3 5.4' }],
  },
  logout: {
    label: 'Log out',
    group: 'ui',
    shapes: [{ d: 'M10 4H5.5A1.5 1.5 0 0 0 4 5.5v13A1.5 1.5 0 0 0 5.5 20H10' }, { d: 'M15 8l4 4-4 4M19 12H9' }],
  },
  globe: {
    label: 'Language',
    group: 'ui',
    shapes: [{ c: [12, 12, 9] }, { e: [12, 12, 4, 9] }, { d: 'M3 12h18M4.6 7.5h14.8M4.6 16.5h14.8' }],
  },
  bell: {
    label: 'Notifications',
    group: 'ui',
    shapes: [{ d: 'M6 16.5V11a6 6 0 0 1 12 0v5.5l1.5 2h-15Z' }, { d: 'M10 21a2 2 0 0 0 4 0M12 3v2' }],
  },
  search: { label: 'Search', group: 'ui', shapes: [{ c: [10.5, 10.5, 6.5] }, { d: 'M15.5 15.5L21 21' }] },
  'chevron-down': { label: 'Expand', group: 'ui', shapes: [{ d: 'M6 9l6 6 6-6' }] },
  'chevron-up': { label: 'Collapse', group: 'ui', shapes: [{ d: 'M6 15l6-6 6 6' }] },
  'chevron-left': { label: 'Back', group: 'ui', shapes: [{ d: 'M15 6l-6 6 6 6' }] },
  'chevron-right': { label: 'Next', group: 'ui', shapes: [{ d: 'M9 6l6 6-6 6' }] },
  check: { label: 'Done', group: 'ui', shapes: [{ d: 'M4.5 12.5l5 5L19.5 7' }] },
  plus: { label: 'Add', group: 'ui', shapes: [{ d: 'M12 5v14M5 12h14' }] },
  reroll: { label: 'Reroll', group: 'ui', shapes: [{ d: 'M18.6 9.2A7 7 0 1 0 19 13.6' }, { d: 'M19.2 4.6v4.8h-4.8' }] },
  dice: {
    label: 'Dice',
    group: 'dice',
    shapes: [
      { d: 'M9.6 3.2L15.6 8.2L15 11.8L9.6 16.2L4.2 11.8L3.6 8.2Z' },
      { d: 'M3.6 8.2L6.7 9.7M15.6 8.2L12.5 9.7M9.6 12V16.2', o: 0.6 },
      { d: 'M17 10.6L20.6 13.6L20 17L15.2 20.8L11.4 17.8', o: 0.85 },
    ],
  },
  minus: { label: 'Remove', group: 'ui', shapes: [{ d: 'M5 12h14' }] },
  trash: {
    label: 'Delete',
    group: 'ui',
    shapes: [{ d: 'M4 6.5h16M9 6.5v-2h6v2' }, { d: 'M6 6.5l1 14h10l1-14' }, { d: 'M10 10.5v6M14 10.5v6' }],
  },
  warning: {
    label: 'Warning',
    group: 'ui',
    shapes: [{ d: 'M12 3.5L21.5 20h-19Z' }, { d: 'M12 9.5v5' }, { c: [12, 17.3, 0.95], f: 1 }],
  },
  info: { label: 'Information', group: 'ui', shapes: [{ c: [12, 12, 9] }, { d: 'M12 11v6' }, { c: [12, 7.8, 0.95], f: 1 }] },
  ornament: {
    label: 'Ornament',
    group: 'ui',
    shapes: [{ d: 'M12 6l2.4 6-2.4 6-2.4-6Z' }, { d: 'M3 12h4.6M16.4 12H21' }, { c: [5.6, 12, 0.9], f: 1 }, { c: [18.4, 12, 0.9], f: 1 }],
  },

  /* ---------------- game lines ---------------- */
  'line-vampire': {
    label: 'Vampire',
    group: 'line',
    shapes: [{ d: 'M5 21V10Q5 4 12 2.5Q19 4 19 10V21' }, { d: smallDrop(12, 9, 1.7), a: 1 }, { d: 'M3.5 21h17' }],
  },
  'line-werewolf': {
    label: 'Werewolf',
    group: 'line',
    shapes: [{ d: arc(8.5, -40, 280) }, { d: 'M14.2 4.6L18.8 9.8M16.4 3.8L20 7.8M12.4 6.2L17.4 11.4', o: 0.9 }],
  },
  'line-mage': {
    label: 'Mage',
    group: 'line',
    shapes: [{ d: arc(9.2, -60, 240) }, { d: star(5, 5.6, 2.3), a: 1 }],
  },
  'line-wraith': {
    label: 'Wraith',
    group: 'line',
    shapes: [
      { d: 'M5 4C9 3 15 3 19 4C18 10 19 16 20 21C17 19.5 15 21 12 19.5C9 21 7 19.5 4 21C5 16 6 10 5 4Z' },
      { d: 'M10 4.6C9.5 10 10 15 9 20M14 4.6C14.5 10 14 15 15 20', o: 0.75 },
    ],
  },
  'line-changeling': {
    label: 'Changeling',
    group: 'line',
    shapes: [
      { d: 'M12 21C5 15 5.5 7 12 3C18.5 7 19 15 12 21Z' },
      { d: 'M12 6V21' },
      { d: 'M6.3 11L4.7 10.5M17.7 11L19.3 10.5M7.4 16L6 16.6M16.6 16L18 16.6' },
    ],
  },

  /* ---------------- clan sigils (original abstract) ---------------- */
  'clan-banu-haqim': {
    label: 'Banu Haqim (original sigil)',
    group: 'clan',
    shapes: [
      { d: 'M12 3.5V20M8.5 20.5h7' },
      { d: 'M3.5 9.6L20.5 6.4' },
      { d: 'M5 9.3v3.2M3 12.5h4a2 2 0 0 1-4 0Z' },
      { d: 'M19 6.7v3' },
      { d: smallDrop(19, 10.2, 1.1), a: 1 },
    ],
  },
  'clan-brujah': {
    label: 'Brujah (original sigil)',
    group: 'clan',
    shapes: [{ d: arc(8, -70, 100) }, { d: arc(8, 120, 250) }, { d: 'M14.8 2.6L10.6 10.2L14 12.2L9.4 21.4', cls: 'sr-glyph-accent-stroke' }],
  },
  'clan-gangrel': {
    label: 'Gangrel (original sigil)',
    group: 'clan',
    shapes: [{ d: 'M15.5 3.4A9 9 0 1 0 20.6 16A7.2 7.2 0 0 1 15.5 3.4Z' }, { d: 'M8 8.2Q9.6 12 9 16M11 7.6Q12.6 11.6 12 15.6M14 8.8Q15.2 12 14.8 15', o: 0.9 }],
  },
  'clan-hecata': {
    label: 'Hecata (original sigil)',
    group: 'clan',
    shapes: [
      { d: 'M5 6.6Q12 11.6 19 6.6' },
      { d: 'M8 8.9L7.2 10.6M12 9.8V11.6M16 8.9L16.8 10.6', o: 0.85 },
      { c: [12, 15, 2] },
      { d: 'M11 16.6L10 21h4L13 16.6' },
    ],
  },
  'clan-lasombra': {
    label: 'Lasombra (original sigil)',
    group: 'clan',
    shapes: [{ d: 'M4 5.5A8 8 0 0 0 20 5.5A8 6.2 0 0 1 4 5.5Z', a: 1 }, { d: 'M8.6 13q-1 3 .5 6.5M12 14v7M15.4 13q1 3-.5 6.5' }],
  },
  'clan-malkavian': {
    label: 'Malkavian (original sigil)',
    group: 'clan',
    shapes: [{ d: 'M8 3L17 4.5L19.5 13L14 21L5.5 17L4.5 9Z' }, { d: 'M11 11L8 3M11 11L19.5 13M11 11L5.5 17' }],
  },
  'clan-ministry': {
    label: 'Ministry (original sigil)',
    group: 'clan',
    shapes: [{ d: 'M12 2.5V21.5', o: 0.7 }, { d: 'M8 4.5C16 4.5 16 9.2 12 9.2S8 13.8 12 13.8S16 18.5 8.6 18.5' }],
  },
  'clan-nosferatu': {
    label: 'Nosferatu (original sigil)',
    group: 'clan',
    shapes: [
      { d: 'M12 3C7 3 4.5 6.5 4.5 11c0 5 3.5 9.5 7.5 10Z' },
      { d: 'M7.4 10q1.6-1.1 3.2 0q-1.6 1.1-3.2 0Z', f: 1 },
      { d: 'M12 3l-1.4 4.2 1.4 1.6-1.8 4.4 1.8 2', o: 0.85 },
      { d: 'M12 21C16 20.5 19.5 16 19.5 11C19.5 8 18.4 5.4 16.4 4.2', dash: '1.6 2.4' },
    ],
  },
  'clan-toreador': {
    label: 'Toreador (original sigil)',
    group: 'clan',
    shapes: [{ r: [4, 4, 16, 16, 1] }, { r: [6.6, 6.6, 10.8, 10.8, 0.5], o: 0.7 }, { d: 'M8.6 15C10 11 13 13 15.4 8.6', cls: 'sr-glyph-accent-stroke' }],
  },
  'clan-tremere': {
    label: 'Tremere (original sigil)',
    group: 'clan',
    shapes: [{ c: [9, 15, 4.8] }, { d: 'M11.6 11C12.6 7 15.5 4.4 20.5 6.4' }, { d: smallDrop(20.4, 8.2, 0.9), a: 1 }, { d: 'M5 21h8' }],
  },
  'clan-tzimisce': {
    label: 'Tzimisce (original sigil)',
    group: 'clan',
    shapes: [
      { d: 'M12 3V21' },
      { d: 'M12 6C8 6 5.6 8 5 11M12 6C16 6 18.4 8 19 11M12 10C8.6 10 6.6 12 6.3 15M12 10C15.4 10 17.4 12 17.7 15M12 14C9.6 14 8 15.5 7.8 18M12 14C14.4 14 16 15.5 16.2 18' },
    ],
  },
  'clan-ventrue': {
    label: 'Ventrue (original sigil)',
    group: 'clan',
    shapes: [{ c: [12, 12, 8.2] }, { c: [12, 12, 4.8] }, { d: 'M9 12.8Q12 16 15 12.8', cls: 'sr-glyph-accent-stroke' }, { d: 'M10.1 14.1l-.7-1.3M12 14.7v-1.5M13.9 14.1l.7-1.3', o: 0.85 }],
  },
  'clan-ravnos': {
    label: 'Ravnos (original sigil)',
    group: 'clan',
    shapes: [
      { d: 'M4 21L10 13.4M20 21L14 13.4' },
      { d: 'M12 20.6v-1.6M12 17.2v-1', o: 0.8 },
      { d: 'M12 2.5C15 5.5 16 8 14.5 10.5C13.5 12 10.5 12 9.5 10.5C8.5 8.5 9.5 7 10.5 6C10.5 7.5 11.5 8 12 7.5C12.5 6 12 4.5 12 2.5Z', a: 1, cls: 'sr-glyph-flame' },
    ],
  },
  'clan-salubri': {
    label: 'Salubri (original sigil)',
    group: 'clan',
    shapes: [
      {
        d: 'M7 12.4V6.6a1.2 1.2 0 0 1 2.4 0V11M9.4 10.6V4.6a1.2 1.2 0 0 1 2.4 0v6M11.8 10.6V5.2a1.2 1.2 0 0 1 2.4 0V11M14.2 11V7.2a1.2 1.2 0 0 1 2.4 0V14c0 4-2.5 7-5.5 7-2.3 0-3.7-1.3-5-3.5L4.4 13a1.3 1.3 0 0 1 2.2-1.3L7 12.4',
      },
      { c: [11.8, 15, 1.2], a: 1 },
    ],
  },
  'clan-caitiff': {
    label: 'Caitiff (original sigil)',
    group: 'clan',
    shapes: [{ d: arc(8, -80, 40) }, { d: arc(8, 62, 250) }],
  },
  'clan-thin-blood': {
    label: 'Thin-blood (original sigil)',
    group: 'clan',
    shapes: [{ d: DROP, dash: '2 2.3' }],
  },

  /* ---------------- disciplines (original) ---------------- */
  'disc-animalism': {
    label: 'Animalism',
    group: 'discipline',
    shapes: [
      { d: 'M7 16C7 12.5 9.5 11 12 11S17 12.5 17 16C17 18.5 15 19.5 12 19.5S7 18.5 7 16Z' },
      { c: [6.4, 9.6, 1.6] },
      { c: [10, 6.4, 1.6] },
      { c: [14, 6.4, 1.6] },
      { c: [17.6, 9.6, 1.6] },
      { d: 'M9.6 15.6Q12 13.6 14.4 15.6Q12 17.6 9.6 15.6Z', a: 1 },
    ],
  },
  'disc-auspex': {
    label: 'Auspex',
    group: 'discipline',
    shapes: [
      { d: 'M3.5 14C6.5 9.5 17.5 9.5 20.5 14C17.5 18.5 6.5 18.5 3.5 14Z' },
      { c: [12, 14, 2], a: 1 },
      { d: 'M12 3v3.5M5.5 5l2 2.8M18.5 5l-2 2.8' },
    ],
  },
  'disc-blood-sorcery': {
    label: 'Blood Sorcery',
    group: 'discipline',
    shapes: [{ c: [12, 12, 9] }, { d: ticks(6, 7.6, 10.4, -60) }, { d: smallDrop(12, 7.4, 2), a: 1 }],
  },
  'disc-celerity': {
    label: 'Celerity',
    group: 'discipline',
    shapes: [{ d: 'M3 8h9M2 12h11M3 16h9', o: 0.85 }, { d: 'M15 6.5L20.5 12L15 17.5' }],
  },
  'disc-dominate': {
    label: 'Dominate',
    group: 'discipline',
    shapes: [{ d: 'M4 9C7 5 17 5 20 9C17 13 7 13 4 9Z' }, { c: [12, 9, 1.8], a: 1 }, { d: 'M6 15.5L12 20.5L18 15.5' }],
  },
  'disc-fortitude': {
    label: 'Fortitude',
    group: 'discipline',
    shapes: [{ d: 'M12 2.5L19.5 5.5V11C19.5 16 16 19.5 12 21.5C8 19.5 4.5 16 4.5 11V5.5Z' }, { d: 'M12 5.5L10.5 10L13.5 12L11 17' }],
  },
  'disc-obfuscate': {
    label: 'Obfuscate',
    group: 'discipline',
    shapes: [{ c: [12, 8, 3.8], dash: '2 2' }, { d: 'M4.5 20.5c0-4 3.4-6.5 7.5-6.5s7.5 2.5 7.5 6.5', dash: '2 2' }],
  },
  'disc-oblivion': {
    label: 'Oblivion',
    group: 'discipline',
    shapes: [{ d: spiral(2.6, 9) }, { c: [12, 12, 1.1], a: 1 }],
  },
  'disc-potence': {
    label: 'Potence',
    group: 'discipline',
    shapes: [
      { d: 'M7.5 12V9.5a1.5 1.5 0 0 1 3 0V12M10.5 9.5V8a1.5 1.5 0 0 1 3 0v4M13.5 9a1.5 1.5 0 0 1 3 0v3' },
      { d: 'M16.5 10.5a1.5 1.5 0 0 1 3 0V14c0 3.6-2.6 6.5-6 6.5h-1.8C8.6 20.5 7 18 7 15.2V12' },
      { d: 'M7.2 14h4.3a1.5 1.5 0 0 0 0-3' },
      { d: 'M5 4.4Q12 1.4 19 4.4', o: 0.85 },
    ],
  },
  'disc-presence': {
    label: 'Presence',
    group: 'discipline',
    shapes: [
      { d: 'M5 17a7 7 0 0 1 14 0' },
      { d: (() => { let d = ''; [-170, -140, -110, -90, -70, -40, -10].forEach((deg) => { const [x0, y0] = pt(8.6, deg, 12, 17); const [x1, y1] = pt(11, deg, 12, 17); d += `M${x0} ${y0}L${x1} ${y1}`; }); return d; })(), o: 0.9 },
      { d: 'M3 20h18' },
    ],
  },
  'disc-protean': {
    label: 'Protean',
    group: 'discipline',
    shapes: [
      { d: 'M9.5 11C12 7 16 4.5 21 4C20 7 19.5 8 18 9C18.5 10 18 11.5 16.5 12C16.5 13 16 14 14.5 14.5C14 16 13 17 11 17' },
      { d: 'M9.5 11C7 12 5 14.5 4 18M10.2 14C8 15 6.6 16.7 5.8 19.5M11 17C9 17.5 7.5 19 7 21' },
    ],
  },
  'disc-thin-blood-alchemy': {
    label: 'Thin-blood Alchemy',
    group: 'discipline',
    shapes: [
      { d: 'M9.5 3h5M10.5 3V9L5 19a1.5 1.5 0 0 0 1.3 2.2h11.4A1.5 1.5 0 0 0 19 19L13.5 9V3' },
      { d: 'M7.4 15h9.2', o: 0.8 },
      { c: [11, 17.6, 0.8], a: 1 },
      { c: [13.8, 18.4, 0.6], a: 1 },
    ],
  },
};

export const GLYPH_NAMES = Object.keys(GLYPHS);

export const GLYPH_GROUPS = GLYPH_NAMES.reduce((acc, name) => {
  const g = GLYPHS[name].group;
  (acc[g] = acc[g] || []).push(name);
  return acc;
}, {});

/** Map clan / discipline / game-line ids used elsewhere in the app to glyph names. */
export function sigilFor(kind, id) {
  if (!id) return null;
  const slug = String(id)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
  const prefix = { clan: 'clan-', discipline: 'disc-', line: 'line-' }[kind];
  const name = `${prefix}${slug}`;
  return GLYPHS[name] ? name : null;
}
