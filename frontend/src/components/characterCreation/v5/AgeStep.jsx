import ResponsiveSheetBlock from '../ResponsiveSheetBlock';
import { V5_AGE_BRACKETS, V5_SECTION_IDS } from '../../../characterSheet/v5/constants';
import { ageAllowed } from '../../../characterSheet/v5/validation';
import { t } from '../../../i18n';
import { Term } from '../../../i18n/glossary';
import { ACCENT, InlineError, gridStyle, inputStyle, labelStyle, noteStyle, useForge } from './forgeUi';

/** Step 9 (core p. 137): how long ago the Embrace was; it sets generation, Blood Potency and XP. */
export default function AgeStep() {
  const f = useForge();
  const { derived } = f;
  return (
    <ResponsiveSheetBlock
      sectionId={V5_SECTION_IDS.age}
      title={t('wizard:v5.ageTitle', 'Age & Generation')}
      subtitle={t('wizard:v5.clanSub', 'Age sets the generation range and starting Blood Potency.')}
      accent={ACCENT}
    >
      <InlineError id={V5_SECTION_IDS.age} />
      <div style={gridStyle}>
        <div>
          <label htmlFor="v5-field-age" style={labelStyle}>{t('wizard:v5.age', 'Age')}</label>
          <select id="v5-field-age" value={f.age} onChange={(e) => f.changeAge(e.target.value)} style={inputStyle}>
            {Object.entries(V5_AGE_BRACKETS).map(([k, a]) => {
              const ok = ageAllowed(f.settings, k);
              return (
                <option key={k} value={k} disabled={!ok}>
                  {a.label}
                  {a.xp ? ` (${a.xp} XP)` : ''}
                  {ok ? '' : ` ${t('wizard:v5.notAllowed', '(not in this chronicle)')}`}
                </option>
              );
            })}
          </select>
        </div>
        <div>
          <label htmlFor="v5-field-generation" style={labelStyle}><Term id="generation" /></label>
          <select
            id="v5-field-generation"
            value={f.generation}
            onChange={(e) => f.setGeneration(parseInt(e.target.value, 10))}
            style={inputStyle}
          >
            {V5_AGE_BRACKETS[f.age].generations.map((g) => (
              <option key={g} value={g}>
                {t('wizard:v5.generationOption', '{{g}}th', { g })}
                {g >= 14 ? ' (thin-blood)' : ''}
              </option>
            ))}
          </select>
        </div>
      </div>
      <p style={{ ...noteStyle, marginTop: '12px' }}>
        <Term id="bloodPotency" /> <strong>{derived.blood_potency}</strong>
        {derived.blood_potency_range ? ` (${derived.blood_potency_range[0]}–${derived.blood_potency_range[1]})` : ''}
        {' · '}
        <Term id="humanity" /> <strong>{derived.humanity}</strong>
        {' · '}
        {t('wizard:v5.ageBudget', 'Advantages {{adv}} · Flaws at least {{flaws}}', { adv: derived.advantage_dots, flaws: derived.flaw_min_dots })}
      </p>
    </ResponsiveSheetBlock>
  );
}
