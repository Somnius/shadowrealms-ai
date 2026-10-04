/**
 * Dice animation markers: the JSON posted to a room (ai_message_kind `dice_animation:<id>`)
 * so every client can play the same overlay. Built from a roll result of either edition.
 */
import { V5, editionOf } from '../rules/rulesEdition';

export const MAX_PREVIEW_DICE = 10;

const num = (v, d = 0) => {
  const n = Number(v);
  return Number.isFinite(n) ? n : d;
};

/**
 * Normalize a roll result from POST /roll, /reroll, or a `/ai roll` slash payload.
 */
export function normalizeRollResult(raw) {
  const r = raw || {};
  const edition = editionOf(r.rules_edition);
  if (edition === V5) {
    const normal = Array.isArray(r.normal_dice) ? r.normal_dice : [];
    const hunger = Array.isArray(r.hunger_dice) ? r.hunger_dice : [];
    return {
      rules_edition: V5,
      normal_dice: normal,
      hunger_dice: hunger,
      difficulty: num(r.difficulty, 1),
      successes: num(r.successes ?? r.net_successes),
      margin: num(r.margin, num(r.successes ?? r.net_successes) - num(r.difficulty, 1)),
      outcome: r.outcome === 'win' ? 'win' : 'fail',
      is_critical: Boolean(r.is_critical),
      is_messy_critical: Boolean(r.is_messy_critical),
      is_bestial_failure: Boolean(r.is_bestial_failure),
      is_total_failure: Boolean(r.is_total_failure),
      is_botch: false,
    };
  }
  const results = Array.isArray(r.results) ? r.results : Array.isArray(r.dice) ? r.dice : [];
  return {
    rules_edition: 'classic',
    results,
    difficulty: num(r.difficulty, 6),
    successes: num(r.successes ?? r.net_successes),
    is_botch: Boolean(r.is_botch ?? r.botch),
    is_exceptional: Boolean(r.is_exceptional),
    specialty: Boolean(r.specialty),
    // Extra dice rolled for natural 10s with a specialty (CLASSIC_REVISED.md §1).
    specialty_rerolls: Array.isArray(r.specialty_rerolls) ? r.specialty_rerolls : [],
    willpower: Boolean(r.willpower),
  };
}

/**
 * Build the marker object for a roll result.
 * V5 previews keep every Hunger die visible (normal dice are trimmed first).
 */
export function buildDiceMarker(rawResult, { animationId, startedAtMs, durationMs = 3000 } = {}) {
  const r = normalizeRollResult(rawResult);
  const base = {
    animation_id: animationId,
    started_at_ms: startedAtMs,
    duration_ms: durationMs,
    rules_edition: r.rules_edition,
    difficulty: r.difficulty,
    successes: r.successes,
    is_botch: r.is_botch,
  };
  if (r.rules_edition === V5) {
    const hunger = r.hunger_dice.slice(0, MAX_PREVIEW_DICE);
    const normal = r.normal_dice.slice(0, Math.max(0, MAX_PREVIEW_DICE - hunger.length));
    const total = r.normal_dice.length + r.hunger_dice.length;
    return {
      ...base,
      dice_preview: [...normal, ...hunger],
      hunger_flags: [...normal.map(() => false), ...hunger.map(() => true)],
      extra_dice_count: Math.max(0, total - normal.length - hunger.length),
      pool_size: total,
      margin: r.margin,
      outcome: r.outcome,
      is_critical: r.is_critical,
      is_messy_critical: r.is_messy_critical,
      is_bestial_failure: r.is_bestial_failure,
      is_total_failure: r.is_total_failure,
    };
  }
  const preview = r.results.slice(0, MAX_PREVIEW_DICE);
  return {
    ...base,
    dice_preview: preview,
    extra_dice_count: Math.max(0, r.results.length - preview.length),
    pool_size: r.results.length,
    // Older clients read is_critical; for classic it means "exceptional".
    is_critical: r.is_exceptional,
    is_exceptional: r.is_exceptional,
    specialty: r.specialty,
    specialty_rerolls: r.specialty_rerolls.slice(0, MAX_PREVIEW_DICE),
    willpower: r.willpower,
  };
}

/** Read a marker (any version) back into overlay fields. Old markers have no edition → classic. */
export function overlayFromMarker(m) {
  const marker = m || {};
  const edition = editionOf(marker.rules_edition);
  const diceFinal = Array.isArray(marker.dice_preview)
    ? marker.dice_preview
    : Array.isArray(marker.diceFinal)
      ? marker.diceFinal
      : [];
  const flags = Array.isArray(marker.hunger_flags) ? marker.hunger_flags : [];
  return {
    rulesEdition: edition,
    difficulty: num(marker.difficulty, edition === V5 ? 1 : 6),
    diceFinal,
    hungerFlags: diceFinal.map((_, i) => Boolean(flags[i])),
    extraDiceCount: num(marker.extra_dice_count ?? marker.extraDiceCount),
    successes: num(marker.successes),
    poolSize: num(marker.pool_size ?? marker.poolSize, diceFinal.length),
    // Classic specialty rerolls (shown apart from the pool, marked as rerolls).
    specialtyRerolls:
      edition === V5 || !Array.isArray(marker.specialty_rerolls) ? [] : marker.specialty_rerolls,
    // Outcome fields (whichever apply to the edition)
    result: {
      rules_edition: edition,
      difficulty: num(marker.difficulty, edition === V5 ? 1 : 6),
      successes: num(marker.successes),
      margin: marker.margin,
      outcome: marker.outcome,
      is_botch: Boolean(marker.is_botch || marker.isBotch),
      is_critical: Boolean(marker.is_critical || marker.isCritical),
      is_exceptional: Boolean(marker.is_exceptional),
      is_messy_critical: Boolean(marker.is_messy_critical),
      is_bestial_failure: Boolean(marker.is_bestial_failure),
      is_total_failure: Boolean(marker.is_total_failure),
      specialty: Boolean(marker.specialty),
      willpower: Boolean(marker.willpower),
      hunger_dice: diceFinal.filter((_, i) => flags[i]),
    },
  };
}
