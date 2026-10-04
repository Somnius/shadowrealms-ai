/**
 * Dice for the theme preview: real resolution (src/dice/*), with an optional "forced" outcome so a
 * visitor can see every effect. A forced roll builds dice that really produce that outcome under
 * the real rules, then runs them through the same resolver the app uses; nothing is faked after
 * the dice are chosen. When the chosen pool can't produce the outcome (a messy critical with no
 * Hunger dice), the smallest change that makes it possible is applied and reported in `adjusted`.
 */
import { resolveClassicDice, classicOutcome } from '../../dice/classicDiceDisplay';
import { resolveV5Dice, v5Badges } from '../../dice/v5DiceDisplay';
import { rollMood } from '../../design';

export const CLASSIC_OUTCOMES = ['random', 'success', 'exceptional', 'failure', 'botch'];
export const V5_OUTCOMES = ['random', 'success', 'critical', 'messy', 'failure', 'bestial', 'total'];

/** Badge key (OutcomeBadges / v5Badges / classicOutcome) each forced outcome must produce. */
export const EXPECTED_KEY = {
  classic: { success: 'success', exceptional: 'exceptional', failure: 'failure', botch: 'botch' },
  v5: { success: 'win', critical: 'critical', messy: 'messy', failure: 'fail', bestial: 'bestial', total: 'total' },
};

const randInt = (lo, hi, rnd) => lo + Math.floor(rnd() * (hi - lo + 1));
const pick = (list, rnd) => list[Math.floor(rnd() * list.length)];

function shuffle(list, rnd) {
  const a = list.slice();
  for (let i = a.length - 1; i > 0; i -= 1) {
    const j = Math.floor(rnd() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

/* ------------------------------------------------------------------ */
/* Classic (Revised)                                                   */
/* ------------------------------------------------------------------ */

/** Values that fail without being a 1, for target number tn (tn >= 3). */
const classicFail = (tn, rnd) => randInt(2, tn - 1, rnd);
const classicHit = (tn, rnd) => randInt(tn, 10, rnd);

function classicDiceFor(outcome, pool, tn, rnd) {
  const n = pool;
  switch (outcome) {
    case 'botch': {
      // No die reaches tn, at least one 1.
      const ones = randInt(1, Math.min(2, n), rnd);
      return shuffle([...Array(ones).fill(1), ...Array.from({ length: n - ones }, () => classicFail(tn, rnd))], rnd);
    }
    case 'failure': {
      // Net 0 without a botch: hits cancelled by the same number of 1s, or nothing at all.
      const pairs = n >= 2 && rnd() < 0.7 ? randInt(1, Math.floor(n / 2), rnd) : 0;
      return shuffle(
        [
          ...Array.from({ length: pairs }, () => classicHit(tn, rnd)),
          ...Array(pairs).fill(1),
          ...Array.from({ length: n - 2 * pairs }, () => classicFail(tn, rnd)),
        ],
        rnd
      );
    }
    case 'exceptional': {
      // 5+ net successes.
      const hits = randInt(5, n, rnd);
      const ones = Math.min(n - hits, hits - 5 > 0 ? randInt(0, hits - 5, rnd) : 0);
      return shuffle(
        [
          ...Array.from({ length: hits }, () => classicHit(tn, rnd)),
          ...Array(ones).fill(1),
          ...Array.from({ length: n - hits - ones }, () => classicFail(tn, rnd)),
        ],
        rnd
      );
    }
    case 'success':
    default: {
      // 1–4 net successes.
      const net = randInt(1, Math.min(4, n), rnd);
      const ones = n - net >= 2 && rnd() < 0.4 ? 1 : 0;
      const hits = net + ones;
      return shuffle(
        [
          ...Array.from({ length: hits }, () => classicHit(tn, rnd)),
          ...Array(ones).fill(1),
          ...Array.from({ length: n - hits - ones }, () => classicFail(tn, rnd)),
        ],
        rnd
      );
    }
  }
}

/**
 * Classic roll. params: { pool 1–10, difficulty 3–10, outcome } → { result, outcomeKey, mood, adjusted, params }.
 */
export function rollClassic({ pool = 5, difficulty = 6, outcome = 'random' } = {}, rnd = Math.random) {
  let n = Math.max(1, Math.min(10, Math.round(pool)));
  const tn = Math.max(3, Math.min(10, Math.round(difficulty)));
  const adjusted = [];
  let dice;
  if (outcome === 'random' || !EXPECTED_KEY.classic[outcome]) {
    dice = Array.from({ length: n }, () => randInt(1, 10, rnd));
  } else {
    if (outcome === 'exceptional' && n < 5) {
      n = 5;
      adjusted.push({ field: 'pool', value: n });
    }
    dice = classicDiceFor(outcome, n, tn, rnd);
  }
  const result = resolveClassicDice(dice, tn);
  return {
    edition: 'classic',
    params: { pool: n, difficulty: tn },
    result,
    outcomeKey: classicOutcome(result).key,
    mood: rollMood(result),
    adjusted,
  };
}

/* ------------------------------------------------------------------ */
/* V5                                                                  */
/* ------------------------------------------------------------------ */

const v5Fail = (rnd) => randInt(2, 5, rnd); // fails, never a 1 (no accidental bestial)
const v5Hit = (rnd) => randInt(6, 9, rnd); // succeeds, never a 10 (no accidental pair)

/**
 * Build V5 dice for an outcome. Returns { normal, hunger } or null if impossible with these numbers.
 * n = pool, h = Hunger dice (<= n), d = difficulty.
 */
function v5DiceFor(outcome, n, h, d, rnd) {
  const k = n - h; // normal dice
  const fill = (count, fn) => Array.from({ length: count }, () => fn(rnd));
  switch (outcome) {
    case 'total':
      // Zero successes, no Hunger 1 (that would also be bestial).
      return { normal: fill(k, (r) => randInt(1, 5, r)), hunger: fill(h, v5Fail) };
    case 'bestial': {
      if (h < 1) return null;
      // A failed roll with a Hunger 1; keep successes under the difficulty.
      const maxHits = Math.max(0, Math.min(d - 1, n - 1));
      const hits = maxHits > 0 && rnd() < 0.6 ? randInt(1, maxHits, rnd) : 0;
      const hungerOnes = 1;
      const normalHits = Math.min(hits, k);
      const hungerHits = Math.min(hits - normalHits, h - hungerOnes);
      return {
        normal: shuffle([...fill(normalHits, v5Hit), ...fill(k - normalHits, (r) => randInt(1, 5, r))], rnd),
        hunger: shuffle([1, ...fill(hungerHits, v5Hit), ...fill(h - hungerOnes - hungerHits, v5Fail)], rnd),
      };
    }
    case 'failure': {
      // 1..d-1 successes, no Hunger 1, no pair of 10s.
      if (d < 2 || n < 1) return null;
      const hits = randInt(1, Math.min(d - 1, n), rnd);
      const normalHits = Math.min(hits, k);
      const hungerHits = hits - normalHits;
      return {
        normal: shuffle([...fill(normalHits, v5Hit), ...fill(k - normalHits, (r) => randInt(1, 5, r))], rnd),
        hunger: shuffle([...fill(hungerHits, v5Hit), ...fill(h - hungerHits, v5Fail)], rnd),
      };
    }
    case 'success': {
      // Win without a pair of 10s: at most one 10, successes >= d.
      if (n < Math.max(1, d)) return null;
      const hits = randInt(Math.max(1, d), n, rnd);
      const normalHits = Math.min(hits, k);
      const hungerHits = hits - normalHits;
      const normal = shuffle([...fill(normalHits, v5Hit), ...fill(k - normalHits, v5Fail)], rnd);
      const hunger = shuffle([...fill(hungerHits, v5Hit), ...fill(h - hungerHits, v5Fail)], rnd);
      // A single 10 on a normal die is fine (no pair).
      const firstHit = normal.findIndex((v) => v >= 6);
      if (firstHit >= 0 && rnd() < 0.4) normal[firstHit] = 10;
      return { normal, hunger };
    }
    case 'critical': {
      // A pair of 10s on normal dice, no Hunger 10, a win.
      if (k < 2) return null;
      const extraNeeded = Math.max(0, d - 4);
      if (n - 2 < extraNeeded) return null;
      const extra = randInt(extraNeeded, Math.min(n - 2, extraNeeded + 2), rnd);
      const normalExtra = Math.min(extra, k - 2);
      const hungerExtra = extra - normalExtra;
      return {
        normal: shuffle([10, 10, ...fill(normalExtra, v5Hit), ...fill(k - 2 - normalExtra, v5Fail)], rnd),
        hunger: shuffle([...fill(hungerExtra, v5Hit), ...fill(h - hungerExtra, v5Fail)], rnd),
      };
    }
    case 'messy': {
      // A pair of 10s with at least one on a Hunger die, a win.
      if (h < 1 || n < 2) return null;
      const extraNeeded = Math.max(0, d - 4);
      if (n - 2 < extraNeeded) return null;
      const both = h >= 2 && (k < 1 || rnd() < 0.35);
      const normalTens = both ? 0 : 1;
      const hungerTens = both ? 2 : 1;
      const extra = randInt(extraNeeded, Math.min(n - 2, extraNeeded + 2), rnd);
      const normalExtra = Math.min(extra, k - normalTens);
      const hungerExtra = extra - normalExtra;
      return {
        normal: shuffle([...Array(normalTens).fill(10), ...fill(normalExtra, v5Hit), ...fill(k - normalTens - normalExtra, v5Fail)], rnd),
        hunger: shuffle([...Array(hungerTens).fill(10), ...fill(hungerExtra, v5Hit), ...fill(h - hungerTens - hungerExtra, v5Fail)], rnd),
      };
    }
    default:
      return null;
  }
}

/** Smallest parameter changes to try, in order, when an outcome is impossible as set. */
function v5Candidates(outcome, n, h, d) {
  const out = [{ n, h, d }];
  const add = (c) => out.push({ n: Math.min(10, c.n), h: Math.min(5, Math.min(c.h, Math.min(10, c.n))), d: c.d });
  if (outcome === 'bestial' || outcome === 'messy') {
    add({ n: Math.max(n, 2), h: Math.max(h, 1), d });
  }
  if (outcome === 'critical') {
    add({ n, h: Math.max(0, Math.min(h, n - 2)), d });
    add({ n: Math.max(n, h + 2), h, d });
  }
  if (outcome === 'failure') add({ n, h, d: Math.max(d, 2) });
  if (outcome === 'success') {
    add({ n: Math.max(n, d), h, d });
    add({ n, h, d: Math.min(d, n) });
  }
  if (outcome === 'critical' || outcome === 'messy') {
    add({ n: Math.max(n, Math.max(2, d - 2)), h: Math.max(h, outcome === 'messy' ? 1 : 0), d });
    add({ n: 10, h: outcome === 'messy' ? Math.max(1, Math.min(h, 5)) : Math.min(h, 5), d: Math.min(d, 6) });
  }
  return out;
}

/**
 * V5 roll. params: { pool 1–10, hunger 0–5, difficulty 1–8, outcome } → same shape as rollClassic.
 */
export function rollV5({ pool = 5, hunger = 2, difficulty = 3, outcome = 'random' } = {}, rnd = Math.random) {
  const n0 = Math.max(1, Math.min(10, Math.round(pool)));
  const h0 = Math.max(0, Math.min(5, Math.round(hunger), n0));
  const d0 = Math.max(1, Math.min(8, Math.round(difficulty)));
  let dice = null;
  let used = { n: n0, h: h0, d: d0 };
  if (outcome === 'random' || !EXPECTED_KEY.v5[outcome]) {
    dice = {
      normal: Array.from({ length: n0 - h0 }, () => randInt(1, 10, rnd)),
      hunger: Array.from({ length: h0 }, () => randInt(1, 10, rnd)),
    };
  } else {
    for (const c of v5Candidates(outcome, n0, h0, d0)) {
      dice = v5DiceFor(outcome, c.n, c.h, c.d, rnd);
      if (dice) {
        used = c;
        break;
      }
    }
  }
  const adjusted = [];
  if (used.n !== n0) adjusted.push({ field: 'pool', value: used.n });
  if (used.h !== h0) adjusted.push({ field: 'hunger', value: used.h });
  if (used.d !== d0) adjusted.push({ field: 'difficulty', value: used.d });
  const result = resolveV5Dice(dice.normal, dice.hunger, used.d);
  return {
    edition: 'v5',
    params: { pool: used.n, hunger: used.h, difficulty: used.d },
    result,
    outcomeKey: v5Badges(result)[0].key,
    mood: rollMood(result),
    adjusted,
  };
}

/** For "random" picks in the scripted chat and tests. */
export const pickOutcome = (edition, rnd = Math.random) =>
  pick((edition === 'v5' ? V5_OUTCOMES : CLASSIC_OUTCOMES).filter((o) => o !== 'random'), rnd);

/** A small seeded generator (tests, scripted chat). */
export function seededRandom(seed = 1) {
  let s = Math.abs(Math.floor(seed)) % 2147483647 || 1;
  return () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
}
