import React from 'react';
import { classicOutcome } from '../../dice/classicDiceDisplay';
import { v5Badges } from '../../dice/v5DiceDisplay';

const TONES = {
  success: { bg: 'rgba(34,197,94,0.15)', fg: '#86efac', bd: '#16a34a' },
  gold: { bg: 'rgba(250,204,21,0.15)', fg: '#fde047', bd: '#ca8a04' },
  blood: { bg: 'rgba(220,38,38,0.22)', fg: '#fecaca', bd: '#dc2626' },
  danger: { bg: 'rgba(127,29,29,0.3)', fg: '#fca5a5', bd: '#991b1b' },
  muted: { bg: 'rgba(100,116,139,0.18)', fg: '#cbd5e1', bd: '#64748b' },
};

/** Outcome pills for a roll result of either edition. */
export default function OutcomeBadges({ result }) {
  const badges = result?.rules_edition === 'v5' ? v5Badges(result) : [classicOutcome(result)];
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', justifyContent: 'center' }}>
      {badges.map((b) => {
        const t = TONES[b.tone] || TONES.muted;
        return (
          <span
            key={b.key}
            data-testid={`outcome-${b.key}`}
            style={{
              padding: '4px 12px',
              borderRadius: '999px',
              background: t.bg,
              color: t.fg,
              border: `1px solid ${t.bd}`,
              fontFamily: 'Cinzel, serif',
              fontSize: '14px',
              fontWeight: 700,
            }}
          >
            {b.label}
          </span>
        );
      })}
    </div>
  );
}
