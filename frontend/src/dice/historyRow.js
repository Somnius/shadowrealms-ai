/**
 * One-line description of a stored dice_rolls row (GET /campaigns/<id>/rolls) per edition.
 */
import { editionOf, V5 } from '../rules/rulesEdition';
import { classicOutcome } from './classicDiceDisplay';
import { resolveV5Dice, v5Badges } from './v5DiceDisplay';
import { t } from '../i18n';

const list = (a) => (Array.isArray(a) ? a.join(', ') : String(a ?? ''));

const successesText = (n) =>
  t('dice:summary.successes', { one: '{{count}} success', other: '{{count}} successes' }, { count: Number(n) || 0 });

export function describeRollRow(row) {
  const r = row || {};
  const mods = r.modifiers && typeof r.modifiers === 'object' ? r.modifiers : {};
  const edition = editionOf(mods.rules_edition);

  if (r.roll_type === 'rouse') {
    const die = Array.isArray(r.results) ? r.results[0] : r.results;
    const ok = Number(r.successes) > 0;
    const hb = mods.hunger_before;
    const ha = mods.hunger_after;
    const hunger = hb != null && ha != null ? ` · ${t('dice:history.hungerChange', 'Hunger {{before}} → {{after}}', { before: hb, after: ha })}` : '';
    const result = ok ? t('dice:history.rouseOk', 'no Hunger gain') : t('dice:history.rouseFailed', 'failed');
    return t('dice:history.rouse', 'V5 Rouse check → [{{die}}] → {{result}}', { die, result }) + hunger;
  }

  if (edition === V5) {
    const normal = Array.isArray(mods.normal_dice) ? mods.normal_dice : [];
    const hungerDice = Array.isArray(mods.hunger_dice) ? mods.hunger_dice : [];
    const res = resolveV5Dice(normal, hungerDice, r.difficulty);
    const tags = v5Badges(res).map((b) => b.label).join(' · ');
    const rr = mods.rerolled ? ` · ${t('dice:history.wpReroll', 'Willpower reroll')}` : '';
    return (
      t('dice:history.v5Head', 'V5 · pool {{pool}} (Hunger {{hunger}}), need {{difficulty}}', {
        pool: r.dice_pool,
        hunger: hungerDice.length,
        difficulty: r.difficulty,
      }) +
      ` → [${list(normal)}]${hungerDice.length ? ` ${t('dice:history.hungerDice', 'hunger [{{dice}}]', { dice: list(hungerDice) })}` : ''}` +
      ` → ${successesText(r.successes)} · ${tags}${rr}`
    );
  }

  const extras = [];
  if (mods.specialty) extras.push(t('dice:summary.specialty', 'specialty'));
  if (mods.willpower) extras.push(t('dice:summary.willpower', 'Willpower'));
  const rerolls = Array.isArray(mods.specialty_rerolls) && mods.specialty_rerolls.length
    ? ` ${t('dice:history.rerolls', '+rerolls [{{dice}}]', { dice: list(mods.specialty_rerolls) })}`
    : '';
  const out = classicOutcome({
    successes: r.successes,
    is_botch: r.is_botch,
    is_exceptional: r.is_critical,
  });
  return (
    t('dice:history.classicHead', 'Pool {{pool}}, TN {{difficulty}}', { pool: r.dice_pool, difficulty: r.difficulty }) +
    `${extras.length ? `, ${extras.join(', ')}` : ''}` +
    ` → [${list(r.results)}]${rerolls} → ${successesText(r.successes)} · ${out.label}`
  );
}
