import { THIN_BLOOD } from '../../../characterSheet/v5/constants';
import { t } from '../../../i18n';
import PredatorOptions from './PredatorOptions';
import { grantText } from './PredatorGrants';
import { predatorSpecialtyLabels } from '../../../characterSheet/v5/validation';
import { inputStyle, labelStyle, noteStyle, useForge } from './forgeUi';

/**
 * Read-only look at what a predator type gives, shown in the Disciplines step so the player sees
 * its Discipline dot before picking. The type itself is chosen in the Predator step (core p. 136
 * order); this select sets the same value.
 */
export default function PredatorPreview() {
  const f = useForge();
  const { pred, clan } = f;
  return (
    <div
      aria-label={t('wizard:v5.predatorPreview', 'Predator type preview')}
      role="region"
      style={{ marginTop: '18px', padding: '12px 14px', border: '1px dashed var(--sr-night-600)', borderRadius: '8px' }}
    >
      <label htmlFor="v5-field-predator-preview" style={labelStyle}>
        {t('wizard:v5.predatorPreviewPickV2', 'Preview a predator type (this also sets it for the next step)')}
      </label>
      <select
        id="v5-field-predator-preview"
        value={f.predatorType}
        onChange={(e) => f.setPredatorType(e.target.value)}
        style={{ ...inputStyle, maxWidth: '420px', padding: '8px', marginBottom: pred ? '10px' : 0 }}
      >
        <option value="">{t('wizard:v5.choose', 'Choose…')}</option>
        <PredatorOptions clan={clan} settings={f.settings} />
      </select>
      {pred ? (
        <ul style={{ ...noteStyle, margin: 0, paddingLeft: '18px' }}>
          {clan !== THIN_BLOOD ? (
            <li>
              {t('wizard:v5.previewDiscipline', 'One Discipline dot: {{list}}', {
                list: f.predDiscOptions.join(', ') || t('wizard:v5.previewNone', 'none for this clan'),
              })}
            </li>
          ) : null}
          <li>{t('wizard:v5.previewSpecialty', 'One specialty: {{list}}', { list: predatorSpecialtyLabels(pred).join(', ') })}</li>
          {pred.advantages.length ? (
            <li>{t('wizard:v5.previewAdvantages', 'Advantages: {{list}}', { list: pred.advantages.map(grantText).join('; ') })}</li>
          ) : null}
          {pred.flaws.length ? (
            <li>
              {t('wizard:v5.previewFlaws', 'Flaws: {{list}} (extra, on top of your own {{min}})', {
                list: pred.flaws.map(grantText).join('; '),
                min: f.derived.flaw_min_dots,
              })}
            </li>
          ) : null}
          {pred.humanity ? <li>Humanity {pred.humanity > 0 ? '+' : ''}{pred.humanity}</li> : null}
          {pred.blood_potency ? <li>Blood Potency +{pred.blood_potency}</li> : null}
        </ul>
      ) : null}
    </div>
  );
}
