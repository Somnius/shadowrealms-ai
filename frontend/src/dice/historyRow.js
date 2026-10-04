/**
 * One-line description of a stored dice_rolls row (GET /campaigns/<id>/rolls) per edition.
 */
import { editionOf, V5 } from '../rules/rulesEdition';
import { classicOutcome } from './classicDiceDisplay';
import { resolveV5Dice, v5Badges } from './v5DiceDisplay';

const list = (a) => (Array.isArray(a) ? a.join(', ') : String(a ?? ''));

export function describeRollRow(row) {
  const r = row || {};
  const mods = r.modifiers && typeof r.modifiers === 'object' ? r.modifiers : {};
  const edition = editionOf(mods.rules_edition);

  if (r.roll_type === 'rouse') {
    const die = Array.isArray(r.results) ? r.results[0] : r.results;
    const ok = Number(r.successes) > 0;
    const hb = mods.hunger_before;
    const ha = mods.hunger_after;
    const hunger = hb != null && ha != null ? ` · Hunger ${hb} → ${ha}` : '';
    return `V5 Rouse check → [${die}] → ${ok ? 'no Hunger gain' : 'failed'}${hunger}`;
  }

  if (edition === V5) {
    const normal = Array.isArray(mods.normal_dice) ? mods.normal_dice : [];
    const hungerDice = Array.isArray(mods.hunger_dice) ? mods.hunger_dice : [];
    const res = resolveV5Dice(normal, hungerDice, r.difficulty);
    const tags = v5Badges(res).map((b) => b.label).join(' · ');
    const rr = mods.rerolled ? ' · Willpower reroll' : '';
    return (
      `V5 · pool ${r.dice_pool} (Hunger ${hungerDice.length}), need ${r.difficulty}` +
      ` → [${list(normal)}]${hungerDice.length ? ` hunger [${list(hungerDice)}]` : ''}` +
      ` → ${r.successes} successes · ${tags}${rr}`
    );
  }

  const extras = [];
  if (mods.specialty) extras.push('specialty');
  if (mods.willpower) extras.push('Willpower');
  const rerolls = Array.isArray(mods.specialty_rerolls) && mods.specialty_rerolls.length
    ? ` +rerolls [${list(mods.specialty_rerolls)}]`
    : '';
  const out = classicOutcome({
    successes: r.successes,
    is_botch: r.is_botch,
    is_exceptional: r.is_critical,
  });
  return (
    `Pool ${r.dice_pool}, TN ${r.difficulty}${extras.length ? `, ${extras.join(', ')}` : ''}` +
    ` → [${list(r.results)}]${rerolls} → ${r.successes} successes · ${out.label}`
  );
}
