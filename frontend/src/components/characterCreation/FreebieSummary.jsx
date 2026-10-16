import { FREEBIE_COSTS, FREEBIE_POINTS } from '../../rules/classicRules';
import { t } from '../../i18n';

const costHint = (costs) => [
  ['Attribute', costs.attribute],
  ['Ability', costs.ability],
  ['Discipline', costs.discipline],
  ['Background', costs.background],
  ['Virtue', costs.virtue],
  ['Humanity', costs.humanity_or_path],
  ['Willpower', costs.willpower],
];

/**
 * Classic freebie point ledger (from computeClassicFreebies) + toggle for freebie mode.
 * `costs` / `base`: a ghoul's own (classicGhoul.js GHOUL_FREEBIE_RULES); a vampire's by default.
 */
export default function FreebieSummary({ freebies, freebieMode, setFreebieMode, isVampire, costs = FREEBIE_COSTS, base = FREEBIE_POINTS }) {
  const over = freebies.remaining < 0;
  return (
    <div
      style={{
        padding: '12px 14px',
        background: 'rgba(15,23,41,0.92)',
        border: `1px solid ${over ? 'var(--sr-blood-700)' : 'var(--sr-night-700)'}`,
        borderRadius: '8px',
      }}
    >
      <label style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--sr-bone-100)', cursor: 'pointer' }}>
        <input
          type="checkbox"
          checked={freebieMode}
          onChange={(e) => setFreebieMode(e.target.checked)}
        />
        <span>
          {t('wizard:freebies.spend', 'Spend freebie points')}{' '}
          <strong style={{ color: over ? 'var(--sr-blood-300)' : 'var(--sr-ok-400)' }}>
            {freebies.spent} / {freebies.available}
          </strong>
          {freebies.flaws.flawBonus > 0 ? (
            <span style={{ color: 'var(--sr-bone-300)', fontSize: '12px' }}>
              {' '}
              {t('wizard:freebies.fromFlaws', '({{base}} + {{n}} from Flaws)', { base, n: freebies.flaws.flawBonus })}
            </span>
          ) : null}
        </span>
      </label>
      <p style={{ color: 'var(--sr-bone-500)', fontSize: '12px', margin: '6px 0 0' }}>
        {t('wizard:freebies.help', 'Place your creation dots first. Freebie mode lifts the limits (abilities above 3, extra dots); anything beyond the creation budgets is priced here. Costs per dot: {{costs}}. Merits cost their points; Flaws give up to 7 more.', {
          costs: costHint(costs).filter(([l]) => isVampire || l === 'Attribute' || l === 'Ability')
            .map(([l, c]) => `${l} ${c}`)
            .join(' · '),
        })}
      </p>
      {freebies.lines.length ? (
        <ul style={{ margin: '8px 0 0', paddingLeft: '1.2rem', color: 'var(--sr-bone-300)', fontSize: '12px' }}>
          {freebies.lines.map((l) => (
            <li key={l.key}>
              {t('wizard:freebies.line', { one: '{{label}}: {{count}} dot → {{cost}} pts', other: '{{label}}: {{count}} dots → {{cost}} pts' }, { label: l.label, count: l.dots, cost: l.cost })}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
