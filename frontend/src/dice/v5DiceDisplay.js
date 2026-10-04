/**
 * V5 dice: classify dice and label outcomes for overlays/history.
 * Mirrors backend/services/v5_dice.py `resolve_v5` (docs/rules/V5.md §1):
 * - pool of d10 including min(hunger, pool) Hunger dice; 6+ is a success
 * - each PAIR of 10s (normal + Hunger together) adds 2 more (a pair = 4 successes)
 * - difficulty = successes needed (default 1; 0 = just count); win = successes >= difficulty
 *   and at least one success (0 successes is a total failure, never a win)
 * - critical = at least one pair of 10s and a win
 * - messy critical = a critical where a 10 is on a Hunger die
 * - bestial failure = a failed roll where any Hunger die shows 1
 * - no botch, 1s cancel nothing
 */
import { V5_SUCCESS_ON } from '../rules/v5Rules';
import { t } from '../i18n';

export function resolveV5Dice(normalDice, hungerDice, difficulty = 1) {
  const normal = (normalDice || []).map((x) => parseInt(x, 10) || 0);
  const hunger = (hungerDice || []).map((x) => parseInt(x, 10) || 0);
  const diff = Number.isFinite(Number(difficulty)) ? Number(difficulty) : 1;
  const all = [...normal, ...hunger];
  const base = all.filter((d) => d >= V5_SUCCESS_ON).length;
  const tensNormal = normal.filter((d) => d === 10).length;
  const tensHunger = hunger.filter((d) => d === 10).length;
  const pairs = Math.floor((tensNormal + tensHunger) / 2);
  const successes = base + 2 * pairs;
  const win = successes >= diff && successes > 0;
  const isCritical = win && pairs >= 1;
  return {
    rules_edition: 'v5',
    results: all,
    normal_dice: normal,
    hunger_dice: hunger,
    difficulty: diff,
    successes,
    critical_pairs: pairs,
    margin: successes - diff,
    outcome: win ? 'win' : 'fail',
    is_critical: isCritical,
    is_messy_critical: isCritical && tensHunger > 0,
    is_bestial_failure: !win && hunger.some((d) => d === 1),
    is_total_failure: successes === 0,
    is_botch: false,
  };
}

/**
 * Classify one die. `hunger` marks a Hunger die.
 * @returns {{ kind: 'normal'|'hunger', state: 'ten'|'success'|'fail'|'bestial' }}
 *  'bestial' = a Hunger die showing 1 (the skull); a normal 1 is just 'fail'.
 */
export function classifyV5Die(value, hunger = false) {
  const v = parseInt(value, 10) || 0;
  const kind = hunger ? 'hunger' : 'normal';
  if (v === 10) return { kind, state: 'ten' };
  if (v >= V5_SUCCESS_ON) return { kind, state: 'success' };
  if (hunger && v === 1) return { kind, state: 'bestial' };
  return { kind, state: 'fail' };
}

/** Normal dice first, then Hunger dice, each tagged. */
export function v5DiceList(normalDice, hungerDice) {
  return [
    ...(normalDice || []).map((v, i) => ({ value: v, hunger: false, index: i })),
    ...(hungerDice || []).map((v, i) => ({ value: v, hunger: true, index: i })),
  ];
}

/** Main outcome label + tone for a V5 roll result (API roll_result, slash roll, or marker). */
export function v5Outcome(result) {
  const r = result || {};
  const successes = Number(r.successes ?? r.net_successes ?? 0);
  const win = r.outcome ? r.outcome === 'win' : successes >= Number(r.difficulty ?? 1) && successes > 0;
  if (win && r.is_messy_critical) {
    return { key: 'messy', label: t('dice:outcome.messyCritical', 'Messy critical'), tone: 'blood', term: 'messyCritical' };
  }
  if (win && r.is_critical) return { key: 'critical', label: t('dice:outcome.criticalWin', 'Critical win'), tone: 'gold', term: 'criticalWin' };
  if (win) return { key: 'win', label: t('dice:outcome.win', 'Win'), tone: 'success' };
  if (r.is_bestial_failure) {
    return { key: 'bestial', label: t('dice:outcome.bestialFailure', 'Bestial failure'), tone: 'blood', term: 'bestialFailure' };
  }
  if (r.is_total_failure || successes === 0) {
    return totalFailure();
  }
  return { key: 'fail', label: t('dice:outcome.failure', 'Failure'), tone: 'muted' };
}

function totalFailure() {
  return { key: 'total', label: t('dice:outcome.totalFailure', 'Total failure'), tone: 'danger', term: 'totalFailure' };
}

/** All badges that apply (outcome first). */
export function v5Badges(result) {
  const r = result || {};
  const out = [v5Outcome(r)];
  // A bestial failure can also be a total failure; show both.
  if (out[0].key === 'bestial' && (r.is_total_failure || Number(r.successes) === 0)) {
    out.push(totalFailure());
  }
  return out;
}

/** "3 successes vs 2 · margin +1 · Hunger 2" */
export function v5SummaryLine(r) {
  const s = Number(r?.successes ?? 0);
  const d = Number(r?.difficulty ?? 1);
  const hungerCount = Array.isArray(r?.hunger_dice) ? r.hunger_dice.length : Number(r?.hunger ?? 0);
  const parts = [t('dice:summary.successes', { one: '{{count}} success', other: '{{count}} successes' }, { count: s })];
  if (d > 0) {
    const m = s - d;
    parts[0] += t('dice:summary.vs', ' vs {{difficulty}}', { difficulty: d });
    parts.push(t('dice:summary.margin', 'margin {{margin}}', { margin: `${m >= 0 ? '+' : ''}${m}` }));
  }
  parts.push(t('dice:summary.hunger', 'Hunger {{count}}', { count: hungerCount }));
  return parts.join(' · ');
}

/**
 * Which normal-die indices the player may choose for a Willpower reroll.
 * Book advice: reroll failures (or a lone 10 to chase a critical). We allow any normal die.
 */
export function canSelectForReroll(selected, index, max = 3) {
  if (selected.includes(index)) return true;
  return selected.length < max;
}
