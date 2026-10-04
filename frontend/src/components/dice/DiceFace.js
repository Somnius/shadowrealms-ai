import { DieFace, Glyph } from '../../design';
import { classifyClassicDie } from '../../dice/classicDiceDisplay';
import { classifyV5Die } from '../../dice/v5DiceDisplay';
import { t } from '../../i18n';
import './dice.css';

/** Map an edition-specific classification onto the design DieFace states. */
export function dieState(value, { edition, difficulty, hunger = false } = {}) {
  const v = parseInt(value, 10) || 1;
  if (edition === 'v5') {
    const c = classifyV5Die(v, hunger).state;
    return c === 'ten' ? 'crit' : c === 'bestial' ? 'one' : c;
  }
  const c = classifyClassicDie(v, difficulty);
  return c === 'ten' ? 'crit' : c;
}

/**
 * One die: the design system's d10 (original glyph) in a small frame.
 * - V5 Hunger dice get the blood body and fang notch; a Hunger 1 also carries a skull mark (bestial).
 * - `reroll`: a classic specialty reroll die (dashed frame + corner mark).
 * - `onClick` makes it a toggle button (`selected` = aria-pressed), used by the V5 Willpower reroll.
 * - `rolling` / `landed` / `index` drive the tumble and landing animation in the dice overlay.
 * - `hidden`: show "?" instead of a value (rolling under reduced motion: no flickering numbers).
 */
export default function DiceFace({
  value,
  edition,
  difficulty,
  hunger = false,
  reroll = false,
  size = 54,
  selected = false,
  onClick,
  title,
  rolling = false,
  landed = false,
  index = 0,
  hidden = false,
}) {
  const v = parseInt(value, 10) || 1;
  const state = rolling ? 'rolling' : dieState(v, { edition, difficulty, hunger });
  const bestial = !rolling && edition === 'v5' && hunger && v === 1;
  const Tag = onClick ? 'button' : 'span';
  const cls = [
    'sr-ldie',
    hunger && 'is-hunger',
    reroll && 'is-reroll',
    selected && 'is-selected',
    onClick && 'is-button',
    rolling && 'is-rolling',
    landed && 'is-landed',
  ]
    .filter(Boolean)
    .join(' ');
  return (
    <Tag
      type={onClick ? 'button' : undefined}
      onClick={onClick}
      className={cls}
      data-state={state}
      style={{ '--die-size': `${size}px`, '--i': index }}
      title={
        hidden ? undefined : title ||
        (hunger
          ? t('dice:die.hunger', 'Hunger die: {{value}}', { value: v })
          : reroll
          ? t('dice:die.reroll', 'Specialty reroll: {{value}}', { value: v })
          : `${v}`)
      }
      aria-pressed={onClick ? selected : undefined}
      /* A clickable die is a toggle button: its title is its accessible name (the face is decorative). */
      aria-label={onClick && !hidden && title ? title : undefined}
    >
      <span className="sr-ldie__shadow" aria-hidden="true" />
      <span className="sr-ldie__body">
        <DieFace value={hidden ? '?' : v} hunger={hunger} state={state} size={size} decorative />
      </span>
      {bestial ? (
        <span className="sr-ldie__mark sr-ldie__mark--bestial" aria-hidden="true">
          <Glyph name="skull" size={Math.max(12, Math.round(size / 3.6))} />
        </span>
      ) : null}
      {reroll ? (
        <span className="sr-ldie__mark sr-ldie__mark--reroll" aria-hidden="true">
          <Glyph name="reroll" size={Math.max(10, Math.round(size / 4.5))} strokeWidth={2.2} />
        </span>
      ) : null}
    </Tag>
  );
}
