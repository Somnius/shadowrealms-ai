/**
 * Classic (VtM Revised) dice: classify dice and label outcomes for overlays/history.
 * Mirrors backend/services/wod_dice.py `resolve_classic` (docs/rules/CLASSIC_REVISED.md):
 * - success on die >= difficulty (2–10, default 6)
 * - each 1 cancels one success
 * - botch ONLY if no die succeeded at all and at least one 1 showed (Willpower prevents it)
 * - specialty: natural 10s count and are rerolled (rerolled 10s explode again);
 *   rerolled 1s do not cancel
 * - Willpower: +1 automatic success that 1s cannot cancel
 * - degrees of success (Revised core): 4 net successes = exceptional, 5+ = phenomenal. The degree is
 *   always derived from net successes, so older rolls whose is_exceptional flag meant 5+ read right.
 */

import { t } from '../i18n';

export const EXCEPTIONAL_THRESHOLD = 4;
export const PHENOMENAL_THRESHOLD = 5;

/** 'none' | 'marginal' | 'moderate' | 'complete' | 'exceptional' | 'phenomenal' (net successes). */
export function classicDegree(successes) {
  const n = Number(successes) || 0;
  if (n <= 0) return 'none';
  if (n >= PHENOMENAL_THRESHOLD) return 'phenomenal';
  return ['marginal', 'moderate', 'complete', 'exceptional'][n - 1];
}

/** Pure resolution of already-rolled dice. */
export function resolveClassicDice(dice, difficulty = 6, { specialtyRerolls = [], willpower = false } = {}) {
  const d = (dice || []).map((x) => parseInt(x, 10) || 0);
  const rr = (specialtyRerolls || []).map((x) => parseInt(x, 10) || 0);
  const tn = parseInt(difficulty, 10) || 6;
  const rawSuccesses = d.filter((x) => x >= tn).length;
  const ones = d.filter((x) => x === 1).length;
  const rerollSuccesses = rr.filter((x) => x >= tn).length;
  const diceNet = Math.max(0, rawSuccesses + rerollSuccesses - ones);
  const successes = diceNet + (willpower ? 1 : 0);
  const isBotch = !willpower && rawSuccesses === 0 && ones > 0;
  return {
    rules_edition: 'classic',
    results: d,
    specialty_rerolls: rr,
    difficulty: tn,
    raw_successes: rawSuccesses,
    ones,
    successes,
    is_botch: isBotch,
    is_exceptional: successes === EXCEPTIONAL_THRESHOLD,
    is_phenomenal: successes >= PHENOMENAL_THRESHOLD,
    willpower: Boolean(willpower),
  };
}

/**
 * Classify one die for display.
 * @returns 'one' | 'ten' | 'success' | 'fail'
 */
export function classifyClassicDie(value, difficulty = 6) {
  const v = parseInt(value, 10) || 0;
  if (v === 1) return 'one';
  if (v === 10) return 'ten';
  if (v >= (parseInt(difficulty, 10) || 6)) return 'success';
  return 'fail';
}

/** Overlay/history label + tone for a classic roll result (API roll_result or marker). */
export function classicOutcome(result) {
  const r = result || {};
  const successes = Number(r.successes ?? r.net_successes ?? 0);
  const botch = Boolean(r.is_botch ?? r.botch);
  // From net successes, not the stored flag (older rolls flagged 5+ as exceptional).
  const degree = classicDegree(successes);
  if (botch) return { key: 'botch', label: t('dice:outcome.botch', 'Botch'), tone: 'danger', term: 'botch' };
  if (successes <= 0) return { key: 'failure', label: t('dice:outcome.failure', 'Failure'), tone: 'muted' };
  if (degree === 'phenomenal') {
    return {
      key: 'phenomenal',
      label: t('dice:outcome.phenomenalCount', 'Phenomenal success ({{count}})', { count: successes }),
      tone: 'gold',
    };
  }
  if (degree === 'exceptional') {
    return {
      key: 'exceptional',
      label: t('dice:outcome.exceptionalCount', 'Exceptional success ({{count}})', { count: successes }),
      tone: 'gold',
    };
  }
  return {
    key: 'success',
    label: t('dice:outcome.successCount', { one: 'Success ({{count}} success)', other: 'Success ({{count}} successes)' }, { count: successes }),
    tone: 'success',
  };
}

/** Short header line for overlays: "TN 6 · 3 net · specialty · Willpower". */
export function classicSummaryLine(r) {
  const parts = [
    t('dice:summary.tn', 'TN {{tn}}', { tn: r?.difficulty ?? 6 }),
    t('dice:summary.net', '{{count}} net', { count: Number(r?.successes ?? 0) }),
  ];
  if (r?.specialty) parts.push(t('dice:summary.specialty', 'specialty'));
  if (r?.willpower) parts.push(t('dice:summary.willpower', 'Willpower'));
  return parts.join(' · ');
}
