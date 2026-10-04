import React from 'react';
import { FREEBIE_COSTS } from '../../rules/classicRules';

const COST_HINT = [
  ['Attribute', FREEBIE_COSTS.attribute],
  ['Ability', FREEBIE_COSTS.ability],
  ['Discipline', FREEBIE_COSTS.discipline],
  ['Background', FREEBIE_COSTS.background],
  ['Virtue', FREEBIE_COSTS.virtue],
  ['Humanity', FREEBIE_COSTS.humanity_or_path],
  ['Willpower', FREEBIE_COSTS.willpower],
];

/**
 * Classic freebie point ledger (from computeClassicFreebies) + toggle for freebie mode.
 */
export default function FreebieSummary({ freebies, freebieMode, setFreebieMode, isVampire }) {
  const over = freebies.remaining < 0;
  return (
    <div
      style={{
        padding: '12px 14px',
        background: 'rgba(15,23,41,0.92)',
        border: `1px solid ${over ? '#b91c1c' : '#2a2a4e'}`,
        borderRadius: '8px',
      }}
    >
      <label style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#e2e8f0', cursor: 'pointer' }}>
        <input
          type="checkbox"
          checked={freebieMode}
          onChange={(e) => setFreebieMode(e.target.checked)}
        />
        <span>
          Spend freebie points{' '}
          <strong style={{ color: over ? '#fca5a5' : '#86efac' }}>
            {freebies.spent} / {freebies.available}
          </strong>
          {freebies.flaws.flawBonus > 0 ? (
            <span style={{ color: '#94a3b8', fontSize: '12px' }}>
              {' '}
              (15 + {freebies.flaws.flawBonus} from Flaws)
            </span>
          ) : null}
        </span>
      </label>
      <p style={{ color: '#8b8b9f', fontSize: '12px', margin: '6px 0 0' }}>
        Place your creation dots first. Freebie mode lifts the limits (abilities above 3, extra
        dots); anything beyond the creation budgets is priced here. Costs per dot:{' '}
        {COST_HINT.filter(([l]) => isVampire || l === 'Attribute' || l === 'Ability')
          .map(([l, c]) => `${l} ${c}`)
          .join(' · ')}
        . Merits cost their points; Flaws give up to 7 more.
      </p>
      {freebies.lines.length ? (
        <ul style={{ margin: '8px 0 0', paddingLeft: '1.2rem', color: '#cbd5e1', fontSize: '12px' }}>
          {freebies.lines.map((l) => (
            <li key={l.key}>
              {l.label}: {l.dots} {l.dots === 1 ? 'dot' : 'dots'} → {l.cost} pts
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
