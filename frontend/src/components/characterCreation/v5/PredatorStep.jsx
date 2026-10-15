import ResponsiveSheetBlock from '../ResponsiveSheetBlock';
import { THIN_BLOOD, V5_SECTION_IDS } from '../../../characterSheet/v5/constants';
import { t } from '../../../i18n';
import { Term } from '../../../i18n/glossary';
import PredatorOptions from './PredatorOptions';
import { ACCENT, InlineError, inputStyle, labelStyle, useForge } from './forgeUi';

/** Step 6 (core p. 136): the predator type, its specialty, its Discipline dot and its extras. */
export default function PredatorStep() {
  const f = useForge();
  const { pred, clan } = f;
  return (
    <ResponsiveSheetBlock
      sectionId={V5_SECTION_IDS.predator}
      title={<Term id="predator" />}
      subtitle={t('wizard:v5.predatorSub', "How you hunt: a specialty, one Discipline dot, and the type's extras.")}
      accent={ACCENT}
    >
      <InlineError id={V5_SECTION_IDS.predator} />
      <label htmlFor="v5-field-predator" style={labelStyle}><Term id="predator" /></label>
      <select
        id="v5-field-predator"
        value={f.predatorType}
        onChange={(e) => f.setPredatorType(e.target.value)}
        style={{ ...inputStyle, maxWidth: '420px', marginBottom: '12px' }}
      >
        <option value="">{clan === THIN_BLOOD ? t('wizard:v5.predatorNone', 'None (optional for thin-bloods)') : t('wizard:v5.choose', 'Choose…')}</option>
        <PredatorOptions clan={clan} settings={f.settings} />
      </select>
      {pred ? (
        <div style={{ color: 'var(--sr-bone-300)', fontSize: '13px', display: 'grid', gap: '10px' }}>
          <div style={{ color: 'var(--sr-bone-300)' }}>{t('wizard:v5.huntingPool', 'Hunting pool: {{pool}}', { pool: pred.pool })}</div>
          <div role="radiogroup" aria-labelledby="v5-predator-specialty-label">
            <span id="v5-predator-specialty-label" style={labelStyle}><Term id="specialty" /></span>
            {pred.specialty_choice.map((sc, i) => (
              <label key={sc} style={{ display: 'block', cursor: 'pointer' }}>
                <input
                  type="radio"
                  name="v5-predator-specialty"
                  checked={f.predatorSpecialty === i}
                  onChange={() => f.setPredatorSpecialty(i)}
                />{' '}
                {sc}
              </label>
            ))}
          </div>
          {clan !== THIN_BLOOD ? (
            <div>
              <label htmlFor="v5-field-predator-discipline" style={labelStyle}>{t('wizard:v5.disciplineDot', 'Discipline dot')}</label>
              <select
                id="v5-field-predator-discipline"
                value={f.predatorDiscipline}
                onChange={(e) => f.setPredatorDiscipline(e.target.value)}
                style={{ ...inputStyle, maxWidth: '300px', padding: '8px' }}
              >
                <option value="">{t('wizard:v5.choose', 'Choose…')}</option>
                {f.predDiscOptions.map((o) => (
                  <option key={o} value={o}>
                    {o}
                  </option>
                ))}
              </select>
            </div>
          ) : null}
          <div style={{ color: 'var(--sr-bone-300)' }}>
            {(pred.advantages || []).map((a) => `${a.name} ${'●'.repeat(a.dots)}`).join(', ') || t('wizard:v5.noAdvantages', 'No advantages')}
            {' · '}
            {(pred.flaws || []).map((x) => `${x.name} ${'●'.repeat(x.dots)}`).join(', ') || t('wizard:v5.noFlaws', 'no flaws')}
            {pred.humanity ? ` · Humanity ${pred.humanity > 0 ? '+' : ''}${pred.humanity}` : ''}
            {pred.blood_potency ? ` · Blood Potency +${pred.blood_potency}` : ''}
          </div>
          {(pred.flaws || []).length ? (
            <div style={{ color: 'var(--sr-gold-400)', fontSize: '12px' }}>
              {t('wizard:v5.predatorFlawsExtra', "These Flaws are extra: you still take {{min}} dots of Flaws of your own in Advantages.", { min: f.derived.flaw_min_dots })}
            </div>
          ) : null}
        </div>
      ) : null}
    </ResponsiveSheetBlock>
  );
}
