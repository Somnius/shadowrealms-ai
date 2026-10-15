import { t } from '../../../i18n';
import { inputStyle, labelStyle, useForge } from './forgeUi';

const dots = (n) => (n ? '●'.repeat(n) : '');
const optLabel = (o) => `${o.name}${o.note ? ` (${o.note})` : ''}${o.dots ? ` ${dots(o.dots)}` : ''}`;

/** One grant as words: "Contacts (criminal) ●●●", "Dark Secret ●● or Shunned ●●", "3 dots between Fame and Herd". */
export function grantText(g) {
  if (g.pick === 'one_of') return g.options.map(optLabel).join(` ${t('wizard:v5.grantOr', 'or')} `);
  if (g.pick === 'split') {
    return t('wizard:v5.grantSplit', '{{n}} dots between {{list}}', {
      n: g.dots_total,
      list: g.options.map((o) => o.name).join(` ${t('wizard:v5.grantAnd', 'and')} `),
    });
  }
  return g.options.map(optLabel).join(', ');
}

/**
 * The predator type's advantages or flaws, with a control for every choice the player makes:
 * one option of a "one of", the dots of a split, or the dots of an option the book prints none for.
 */
export default function PredatorGrants({ grants, prefix, title }) {
  const f = useForge();
  const choices = f.predatorChoices;
  const set = (patch) => f.setPredatorChoices((prev) => ({ ...prev, ...patch }));
  if (!grants.length) return null;
  return (
    <div>
      <span style={labelStyle}>{title}</span>
      {grants.map((g, gi) => {
        const key = `${prefix}${gi}`;
        if (g.pick === 'one_of') {
          return (
            <div key={key} role="radiogroup" aria-label={grantText(g)} style={{ marginBottom: '6px' }}>
              {g.options.map((o, oi) => (
                <label key={oi} style={{ display: 'block', cursor: 'pointer' }}>
                  <input type="radio" name={`v5-grant-${key}`} checked={choices[key] === oi} onChange={() => set({ [key]: oi })} /> {optLabel(o)}
                </label>
              ))}
            </div>
          );
        }
        if (g.pick === 'split') {
          const split = choices[key] || {};
          const total = g.options.reduce((s, _, oi) => s + (Number(split[oi]) || 0), 0);
          return (
            <div key={key} style={{ marginBottom: '6px' }}>
              <div>{grantText(g)}</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center', marginTop: '4px' }}>
                {g.options.map((o, oi) => (
                  <label key={oi} style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                    {o.name}
                    <input
                      type="number"
                      min={0}
                      max={g.dots_total}
                      value={split[oi] ?? 0}
                      aria-label={t('wizard:v5.grantSplitDots', '{{name}} dots', { name: o.name })}
                      onChange={(e) => set({ [key]: { ...split, [oi]: Math.max(0, Math.min(g.dots_total, parseInt(e.target.value, 10) || 0)) } })}
                      style={{ ...inputStyle, width: '64px', padding: '4px 6px' }}
                    />
                  </label>
                ))}
                <span style={{ color: total === g.dots_total ? 'var(--sr-ok-400)' : 'var(--sr-blood-300)', fontSize: '12px' }}>
                  {total}/{g.dots_total}
                </span>
              </div>
            </div>
          );
        }
        return (
          <div key={key} style={{ marginBottom: '6px' }}>
            {g.options.map((o, oi) =>
              o.dots == null ? (
                <label key={oi} style={{ display: 'flex', gap: '6px', alignItems: 'center', flexWrap: 'wrap' }}>
                  {optLabel(o)}
                  <input
                    type="number"
                    min={1}
                    max={5}
                    value={choices[`${key}:${oi}:dots`] ?? ''}
                    aria-label={t('wizard:v5.grantDots', '{{name}} dots', { name: o.name })}
                    onChange={(e) => set({ [`${key}:${oi}:dots`]: parseInt(e.target.value, 10) || '' })}
                    style={{ ...inputStyle, width: '64px', padding: '4px 6px' }}
                  />
                  <span style={{ fontSize: '12px', color: 'var(--sr-bone-500)' }}>
                    {t('wizard:v5.grantNoRating', 'the book prints no rating: ask your Storyteller')}
                  </span>
                </label>
              ) : (
                <div key={oi}>{optLabel(o)}</div>
              )
            )}
          </div>
        );
      })}
    </div>
  );
}
