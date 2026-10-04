import React from 'react';
import { V5_DIFFICULTY_TABLE, V5_MAX_HUNGER } from '../../rules/v5Rules';

const fieldLabel = {
  display: 'block',
  color: '#b5b5c3',
  fontSize: '12px',
  marginBottom: '6px',
  fontFamily: 'Cinzel, serif',
};
const selectStyle = {
  width: '100%',
  marginBottom: '12px',
  padding: '10px 12px',
  background: '#0f1729',
  border: '1px solid #2a2a4e',
  borderRadius: '6px',
  color: '#e0e0e0',
  fontSize: '15px',
  fontFamily: 'Crimson Text, serif',
};
const checkRow = (disabled) => ({
  display: 'flex',
  alignItems: 'center',
  gap: '10px',
  color: '#b5b5c3',
  fontSize: '13px',
  marginBottom: '12px',
  cursor: disabled ? 'default' : 'pointer',
  fontFamily: 'Crimson Text, serif',
});
const helpStyle = {
  color: '#8b8b9f',
  fontSize: '13px',
  marginBottom: '16px',
  fontFamily: 'Crimson Text, serif',
  lineHeight: 1.5,
};

/** Help text for the roll modal, per edition. */
export function RollHelp({ edition }) {
  if (edition === 'v5') {
    return (
      <p style={helpStyle}>
        <strong>V5</strong>: pool of <strong>d10</strong>, each <strong>6+</strong> is a success and every
        pair of 10s counts as 4. Difficulty is the number of successes you need. Your current
        <strong> Hunger</strong> replaces that many dice with Hunger dice (messy criticals and bestial
        failures). After the roll you can spend Willpower to reroll up to 3 normal dice.
      </p>
    );
  }
  return (
    <p style={helpStyle}>
      <strong>Classic (Revised)</strong>: pool of <strong>d10</strong>, difficulty (target number) usually
      6–9. Each die ≥ difficulty is a success; <strong>1s cancel</strong> successes. A botch needs no
      successes at all and at least one 1. Specialty: 10s are rerolled for more successes. Willpower:
      one automatic success (declare before rolling).
    </p>
  );
}

/**
 * Edition-specific roll inputs.
 * classic: difficulty (TN 2–10), specialty, willpower
 * v5: difficulty (successes needed 0–10), hunger 0–5, rouse check button
 */
export default function RollEditionFields({
  edition,
  disabled,
  classicDifficulty,
  setClassicDifficulty,
  specialty,
  setSpecialty,
  willpower,
  setWillpower,
  v5Difficulty,
  setV5Difficulty,
  hunger,
  setHunger,
  hungerSource,
  onRouse,
  rousing,
}) {
  if (edition === 'v5') {
    return (
      <>
        <label style={fieldLabel} htmlFor="roll-v5-difficulty">
          Difficulty (successes needed)
        </label>
        <select
          id="roll-v5-difficulty"
          value={v5Difficulty}
          onChange={(e) => setV5Difficulty(Number(e.target.value))}
          disabled={disabled}
          style={selectStyle}
        >
          {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => (
            <option key={n} value={n}>
              {n}
              {n === 0 ? ' (just count successes)' : ''}
              {V5_DIFFICULTY_TABLE[String(Math.min(n, 7))] && n > 0
                ? ` — ${V5_DIFFICULTY_TABLE[String(Math.min(n, 7))]}`
                : ''}
            </option>
          ))}
        </select>
        <label style={fieldLabel} htmlFor="roll-v5-hunger">
          Hunger {hungerSource ? <span style={{ color: '#64748b' }}>({hungerSource})</span> : null}
        </label>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px', flexWrap: 'wrap' }}>
          <select
            id="roll-v5-hunger"
            value={hunger}
            onChange={(e) => setHunger(Number(e.target.value))}
            disabled={disabled}
            style={{ ...selectStyle, width: 'auto', minWidth: '90px', marginBottom: 0 }}
          >
            {Array.from({ length: V5_MAX_HUNGER + 1 }, (_, n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
          <span aria-hidden="true" style={{ color: '#dc2626', letterSpacing: '2px' }}>
            {'●'.repeat(hunger)}
            <span style={{ color: '#4b5563' }}>{'○'.repeat(Math.max(0, V5_MAX_HUNGER - hunger))}</span>
          </span>
          {onRouse ? (
            <button
              type="button"
              onClick={onRouse}
              disabled={disabled || rousing}
              title="One die: 6+ no Hunger gain, otherwise Hunger +1"
              style={{
                marginLeft: 'auto',
                padding: '8px 12px',
                background: '#3f1d1d',
                color: '#fecaca',
                border: '1px solid #dc2626',
                borderRadius: '6px',
                cursor: disabled || rousing ? 'not-allowed' : 'pointer',
                fontFamily: 'Cinzel, serif',
                fontSize: '12px',
              }}
            >
              {rousing ? 'Rousing…' : 'Rouse check'}
            </button>
          ) : null}
        </div>
      </>
    );
  }
  return (
    <>
      <label style={fieldLabel} htmlFor="roll-classic-difficulty">
        Difficulty (target number, 2–10)
      </label>
      <select
        id="roll-classic-difficulty"
        value={classicDifficulty}
        onChange={(e) => setClassicDifficulty(Number(e.target.value))}
        disabled={disabled}
        style={selectStyle}
      >
        {[2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => (
          <option key={n} value={n}>
            {n}
            {n === 6 ? ' (common default)' : ''}
          </option>
        ))}
      </select>
      <label style={checkRow(disabled)}>
        <input type="checkbox" checked={specialty} onChange={(e) => setSpecialty(e.target.checked)} disabled={disabled} />
        Specialty (10s are rerolled for extra successes)
      </label>
      <label style={checkRow(disabled)}>
        <input type="checkbox" checked={willpower} onChange={(e) => setWillpower(e.target.checked)} disabled={disabled} />
        Spend Willpower (+1 automatic success, can’t be cancelled)
      </label>
    </>
  );
}
