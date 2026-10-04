/** WCAG 2.x contrast, computed live from the token values (so the numbers can't go stale). */

export function parseColor(value) {
  const v = String(value || '').trim();
  let m = v.match(/^#([0-9a-f]{3})$/i);
  if (m) return m[1].split('').map((c) => parseInt(c + c, 16));
  m = v.match(/^#([0-9a-f]{6})/i);
  if (m) return [0, 2, 4].map((i) => parseInt(m[1].slice(i, i + 2), 16));
  m = v.match(/^rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)/i);
  if (m) return [m[1], m[2], m[3]].map(Number);
  return null;
}

function channel(c) {
  const s = c / 255;
  return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
}

export function luminance(rgb) {
  const [r, g, b] = rgb.map(channel);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function contrastRatio(a, b) {
  const ca = Array.isArray(a) ? a : parseColor(a);
  const cb = Array.isArray(b) ? b : parseColor(b);
  if (!ca || !cb) return null;
  const la = luminance(ca);
  const lb = luminance(cb);
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

/** Ratio as shown: rounded down to 2 decimals, so 4.499 reads 4.49 (a fail), never 4.50. */
export function formatRatio(ratio) {
  if (!ratio) return '–';
  return (Math.floor(ratio * 100 + 1e-9) / 100).toFixed(2);
}

/** 'AAA' (7+), 'AA' (4.5+), 'AA large' (3+) or 'decor'. */
export function wcagLevel(ratio) {
  if (ratio == null) return '';
  if (ratio >= 7) return 'AAA';
  if (ratio >= 4.5) return 'AA';
  if (ratio >= 3) return 'AA large';
  return 'decor';
}

/** A CSS custom property's current value (falls back to the given hex outside a browser). */
export function readToken(name, fallback) {
  try {
    const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return v && parseColor(v) ? v : fallback;
  } catch {
    return fallback;
  }
}
