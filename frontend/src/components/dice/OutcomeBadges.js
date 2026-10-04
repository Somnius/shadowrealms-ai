import React from 'react';
import { Badge } from '../../design';
import { classicOutcome } from '../../dice/classicDiceDisplay';
import { v5Badges } from '../../dice/v5DiceDisplay';
import { t as tr } from '../../i18n';
import { termHint } from '../../i18n/glossary';
import './dice.css';

/** Explanation for an outcome that is a game term (kept in English): glossary first, then dice:hint.* */
export function outcomeHint(term) {
  if (!term) return '';
  return termHint(term) || tr(`dice:hint.${term}`, '');
}

const TONE = { success: 'ok', gold: 'gold', blood: 'blood', danger: 'danger', muted: 'neutral' };
/** Original glyph per outcome key (decorative: the label carries the meaning). */
export const OUTCOME_GLYPH = {
  messy: 'fangs',
  critical: 'd10-crit',
  win: 'd10',
  bestial: 'd10-hunger',
  total: 'skull',
  fail: 'eye-shut',
  failure: 'eye-shut',
  botch: 'd10-botch',
  exceptional: 'd10-crit',
  success: 'd10',
};

/** Outcome pills for a roll result of either edition. `size="lg"` for the dice overlay. */
export default function OutcomeBadges({ result, size = 'md' }) {
  const badges = result?.rules_edition === 'v5' ? v5Badges(result) : [classicOutcome(result)];
  return (
    <div className={`sr-outcomes sr-outcomes--${size}`}>
      {badges.map((b) => (
        <Badge
          key={b.key}
          tone={TONE[b.tone] || 'neutral'}
          icon={OUTCOME_GLYPH[b.key]}
          className="sr-outcome"
          data-testid={`outcome-${b.key}`}
          data-outcome={b.key}
          lang={b.term ? 'en' : undefined}
          title={outcomeHint(b.term) || undefined}
        >
          {b.label}
        </Badge>
      ))}
    </div>
  );
}
