import React, { useState } from 'react';
import DiceFace from './DiceFace';
import OutcomeBadges from './OutcomeBadges';
import { canSelectForReroll, v5SummaryLine } from '../../dice/v5DiceDisplay';
import { V5_WILLPOWER_REROLL_MAX } from '../../rules/v5Rules';

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
    <div
      role="region"
      aria-label="Willpower reroll"
      data-testid="v5-reroll-panel"
      style={{
        boxSizing: 'border-box',
        width: '100%',
        maxHeight: '40vh',
        overflowY: 'auto',
        marginBottom: '12px',
        background: 'rgba(15, 23, 41, 0.97)',
        border: '1px solid #dc2626',
        borderRadius: '12px',
        padding: '10px 14px',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
        <strong style={{ color: '#fecaca', fontFamily: 'Cinzel, serif', fontSize: '14px' }}>Your V5 roll</strong>
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Close"
          style={{ background: 'transparent', color: '#94a3b8', border: 'none', cursor: 'pointer', fontSize: '18px' }}
        >
          ×
        </button>
      </div>
      {elsewhere ? (
        <div style={{ color: '#fbbf24', fontSize: '12px', textAlign: 'center', marginBottom: '6px' }}>
          Rolled in another room; the reroll is posted there.
        </div>
      ) : null}
      <OutcomeBadges result={{ rules_edition: 'v5', ...roll }} />
      <div style={{ color: '#94a3b8', fontSize: '12px', textAlign: 'center', margin: '6px 0 10px' }}>
        {v5SummaryLine(roll)}
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', justifyContent: 'center' }}>
        {(roll.normal_dice || []).map((v, i) => (
          <DiceFace
            key={`n${i}`}
            value={v}
            edition="v5"
            size={36}
            selected={selected.includes(i)}
            onClick={busy ? undefined : () => toggle(i)}
            title={`Normal die ${v} — click to pick for the reroll`}
          />
        ))}
        {(roll.hunger_dice || []).map((v, i) => (
          <DiceFace key={`h${i}`} value={v} edition="v5" hunger size={36} title={`Hunger die ${v} (can't be rerolled)`} />
        ))}
      </div>
      <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end', alignItems: 'center', marginTop: '12px' }}>
        <span style={{ color: '#64748b', fontSize: '12px', marginRight: 'auto' }}>
          {selected.length}/{V5_WILLPOWER_REROLL_MAX} picked
        </span>
        <button
          type="button"
          disabled={busy || selected.length === 0}
          onClick={() => onReroll(selected)}
          style={{
            padding: '8px 12px',
            background: busy || selected.length === 0 ? '#4a4a5e' : '#9d4edd',
            color: 'white',
            border: 'none',
            borderRadius: '6px',
            cursor: busy || selected.length === 0 ? 'not-allowed' : 'pointer',
            fontFamily: 'Cinzel, serif',
            fontSize: '12px',
          }}
        >
          {busy ? 'Rerolling…' : 'Reroll with Willpower'}
        </button>
      </div>
    </div>
  );
}
