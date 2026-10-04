import React, { useState } from 'react';
import DiceFace from './DiceFace';
import OutcomeBadges from './OutcomeBadges';
import { canSelectForReroll, v5SummaryLine } from '../../dice/v5DiceDisplay';
import { V5_WILLPOWER_REROLL_MAX } from '../../rules/v5Rules';
import { t } from '../../i18n';
import { Button, Glyph, IconButton } from '../../design';
import './dice.css';

/**
 * After a V5 roll by this player: pick up to 3 NORMAL dice and reroll them once
 * for 1 Willpower (Hunger dice can't be rerolled).
 *
 * Rendered in the layout flow just above the chat composer (not position: fixed), so it
 * pushes the message list up instead of covering the input or the Send button.
 *
 * `roll` = { roll_id, normal_dice, hunger_dice, difficulty, successes, outcome, ... }
 * `elsewhere` = the roll was made in another room; the reroll is posted there.
 */
export default function V5RerollPanel({ roll, onReroll, onDismiss, busy, elsewhere = false }) {
  const [selected, setSelected] = useState([]);
  if (!roll) return null;
  const toggle = (i) => {
    setSelected((prev) => {
      if (prev.includes(i)) return prev.filter((x) => x !== i);
      return canSelectForReroll(prev, i, V5_WILLPOWER_REROLL_MAX) ? [...prev, i] : prev;
    });
  };
  return (
    <div role="region" aria-label={t('dice:reroll.region', 'Willpower reroll')} data-testid="v5-reroll-panel" className="sr-reroll">
      <div className="sr-reroll__head">
        <strong className="sr-reroll__title">
          <Glyph name="d10-hunger" size={18} /> {t('dice:reroll.title', 'Your V5 roll')}
        </strong>
        <IconButton icon="close" size="sm" label={t('common:close', 'Close')} tooltip={false} onClick={onDismiss} />
      </div>
      {elsewhere ? <div className="sr-reroll__elsewhere">{t('dice:reroll.elsewhere', 'Rolled in another room; the reroll is posted there.')}</div> : null}
      <OutcomeBadges result={{ rules_edition: 'v5', ...roll }} />
      <div className="sr-reroll__summary">{v5SummaryLine(roll)}</div>
      <div className="sr-reroll__dice">
        {(roll.normal_dice || []).map((v, i) => (
          <DiceFace
            key={`n${i}`}
            value={v}
            edition="v5"
            size={40}
            selected={selected.includes(i)}
            onClick={busy ? undefined : () => toggle(i)}
            title={t('dice:reroll.normalDie', 'Normal die {{value}}: click to pick it for the reroll', { value: v })}
          />
        ))}
        {(roll.hunger_dice || []).map((v, i) => (
          <DiceFace key={`h${i}`} value={v} edition="v5" hunger size={40} title={t('dice:reroll.hungerDie', 'Hunger die {{value}} (can’t be rerolled)', { value: v })} />
        ))}
      </div>
      <div className="sr-reroll__foot">
        <span className="sr-reroll__picked">
          {t('dice:reroll.picked', '{{n}}/{{max}} picked', { n: selected.length, max: V5_WILLPOWER_REROLL_MAX })}
        </span>
        <span className="sr-reroll__cost">{t('dice:reroll.cost', 'Costs 1 Willpower')}</span>
        <Button
          variant="arcane"
          size="sm"
          icon="reroll"
          disabled={selected.length === 0}
          loading={busy}
          loadingLabel={t('dice:reroll.busy', 'Rerolling…')}
          onClick={() => onReroll(selected)}
        >
          {t('dice:reroll.submit', 'Reroll with Willpower')}
        </Button>
      </div>
    </div>
  );
}
