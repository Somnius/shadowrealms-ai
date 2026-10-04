/**
 * Pure dice read-outs for the visualisation. They mirror the server rules
 * (backend/services/v5_dice.py resolve_v5, docs/dice-old-wod.md) but the server stays the
 * source of truth: when the API already returned flags, pass them in and they win.
 */
import { t } from '../../i18n';

/** V5: successes 6+, each pair of 10s adds 2, messy = critical with a Hunger 10, bestial = fail with a Hunger 1. */
export function analyzeV5({ normal = [], hunger = [], difficulty = 1, flags } = {}) {
  const dice = [
    ...normal.map((value, i) => ({ value: Number(value), hunger: false, index: i })),
    ...hunger.map((value, i) => ({ value: Number(value), hunger: true, index: i })),
  ];
  const base = dice.filter((d) => d.value >= 6).length;
  // Pair Hunger 10s first so a messy pair is visible.
  const tens = dice
    .map((d, i) => ({ d, i }))
    .filter(({ d }) => d.value === 10)
    .sort((a, b) => Number(b.d.hunger) - Number(a.d.hunger));
  const pairs = [];
  for (let k = 0; k + 1 < tens.length; k += 2) pairs.push([tens[k].i, tens[k + 1].i]);
  const successes = base + 2 * pairs.length;
  const win = successes >= difficulty && successes > 0;
  const tensHunger = dice.filter((d) => d.hunger && d.value === 10).length;
  const isCritical = win && pairs.length >= 1;
  const out = {
    edition: 'v5',
    dice: dice.map((d, i) => ({
      ...d,
      success: d.value >= 6,
      crit: d.value === 10,
      paired: pairs.some((p) => p.includes(i)),
      state: d.value === 10 ? 'crit' : d.value === 1 ? 'one' : d.value >= 6 ? 'success' : 'fail',
    })),
    pairs,
    difficulty,
    successes,
    margin: successes - difficulty,
    win,
    isCritical,
    isMessyCritical: isCritical && tensHunger > 0,
    isBestialFailure: !win && dice.some((d) => d.hunger && d.value === 1),
    isTotalFailure: successes === 0,
  };
  if (flags) {
    if (flags.successes != null) out.successes = flags.successes;
    if (flags.is_critical != null) out.isCritical = !!flags.is_critical;
    if (flags.is_messy_critical != null) out.isMessyCritical = !!flags.is_messy_critical;
    if (flags.is_bestial_failure != null) out.isBestialFailure = !!flags.is_bestial_failure;
    if (flags.is_total_failure != null) out.isTotalFailure = !!flags.is_total_failure;
    if (flags.outcome) out.win = flags.outcome === 'win';
    out.margin = out.successes - difficulty;
  }
  out.outcome = outcomeV5(out);
  return out;
}

function outcomeV5(r) {
  if (r.win && r.isMessyCritical) return 'messy-critical';
  if (r.win && r.isCritical) return 'critical';
  if (r.win) return 'success';
  if (r.isBestialFailure) return 'bestial-failure';
  if (r.isTotalFailure) return 'total-failure';
  return 'failure';
}

/**
 * Classic (Revised/V20): success >= difficulty, 1s cancel, botch only when no die succeeded and a 1
 * showed, specialty rerolls only add, Willpower adds 1 uncancellable success, exceptional = 5+.
 */
export function analyzeClassic({ dice = [], difficulty = 6, rerolls = [], willpower = false, flags } = {}) {
  const values = dice.map(Number);
  const raw = values.filter((v) => v >= difficulty).length;
  const rerollSucc = rerolls.map(Number).filter((v) => v >= difficulty).length;
  const ones = values.filter((v) => v === 1).length;
  let successes = Math.max(0, raw + rerollSucc - ones) + (willpower ? 1 : 0);
  let isBotch = !willpower && raw === 0 && ones > 0;
  if (flags) {
    if (flags.successes != null) successes = flags.successes;
    if (flags.is_botch != null) isBotch = !!flags.is_botch;
  }
  const isExceptional = flags && flags.is_exceptional != null ? !!flags.is_exceptional : successes >= 5;
  const out = {
    edition: 'classic',
    dice: [
      ...values.map((value, index) => ({
        value,
        index,
        reroll: false,
        success: value >= difficulty,
        state: value === 1 ? 'one' : value >= difficulty ? (value === 10 ? 'crit' : 'success') : 'fail',
      })),
      ...rerolls.map(Number).map((value, index) => ({
        value,
        index,
        reroll: true,
        success: value >= difficulty,
        state: value >= difficulty ? (value === 10 ? 'crit' : 'success') : 'fail',
      })),
    ],
    pairs: [],
    difficulty,
    successes,
    ones,
    willpower,
    isBotch,
    isExceptional,
    win: successes > 0,
  };
  out.outcome = isBotch ? 'botch' : successes === 0 ? 'failure' : isExceptional ? 'exceptional' : 'success';
  return out;
}

/** Outcome labels in the active language (game terms stay English, see i18n/glossary). */
export function outcomeLabels() {
  return {
    'messy-critical': t('dice:outcome.messyCritical', 'Messy critical'),
    critical: t('dice:outcome.criticalWin', 'Critical win'),
    success: t('dice:outcome.success', 'Success'),
    'bestial-failure': t('dice:outcome.bestialFailure', 'Bestial failure'),
    'total-failure': t('dice:outcome.totalFailure', 'Total failure'),
    failure: t('dice:outcome.failure', 'Failure'),
    botch: t('dice:outcome.botch', 'Botch'),
    exceptional: t('dice:outcome.exceptional', 'Exceptional success'),
  };
}

/** English labels (kept for callers that want fixed text). */
export const OUTCOME_LABELS = {
  'messy-critical': 'Messy critical',
  critical: 'Critical win',
  success: 'Success',
  'bestial-failure': 'Bestial failure',
  'total-failure': 'Total failure',
  failure: 'Failure',
  botch: 'Botch',
  exceptional: 'Exceptional success',
};
