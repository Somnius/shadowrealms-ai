import ResponsiveSheetBlock from '../ResponsiveSheetBlock';
import DotTrack from '../DotTrack';
import {
  V5_SECTION_IDS,
  V5_SKILLS,
  V5_SKILL_DISTRIBUTIONS,
  V5_SKILL_KEYS,
  V5_SKILL_LABELS,
} from '../../../characterSheet/v5/constants';
import { freeSpecialtyCount } from '../../../characterSheet/v5/validation';
import { t } from '../../../i18n';
import { Term } from '../../../i18n/glossary';
import { ACCENT, InlineError, SpreadChips, addButtonStyle, inputStyle, labelStyle, rowStyle, smallButtonStyle, useForge } from './forgeUi';

/** Step 4 (core p. 136): a Skill distribution, then the free specialties. */
export default function SkillsStep() {
  const f = useForge();
  const { skills, specialties, setSpecialties } = f;
  return (
    <ResponsiveSheetBlock
      sectionId={V5_SECTION_IDS.skills}
      title={<Term id="skills" />}
      subtitle={t('wizard:v5.skillsSub', 'Pick a distribution, then free specialties.')}
      accent={ACCENT}
    >
      <InlineError id={V5_SECTION_IDS.skills} />
      <label htmlFor="v5-field-distribution" style={labelStyle}>{t('wizard:v5.distribution', 'Distribution')}</label>
      <select
        id="v5-field-distribution"
        value={f.skillDistribution}
        onChange={(e) => f.setSkillDistribution(e.target.value)}
        style={{ ...inputStyle, maxWidth: '420px', marginBottom: '12px' }}
      >
        {Object.entries(V5_SKILL_DISTRIBUTIONS).map(([k, d]) => (
          <option key={k} value={k}>
            {d.label}:{' '}
            {Object.keys(d.counts)
              .map(Number)
              .sort((a, b) => b - a)
              .map((r) => `${d.counts[r]}×${r}`)
              .join(', ')}
          </option>
        ))}
      </select>
      <SpreadChips status={f.skillStatus} />
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '18px' }}>
        {['physical', 'social', 'mental'].map((cat) => (
          <div key={cat} style={{ flex: '1 1 220px', minWidth: 0 }}>
            <div style={{ textAlign: 'center', fontFamily: 'var(--sr-font-display)', fontSize: '12px', color: ACCENT, marginBottom: '10px', textTransform: 'capitalize' }}>
              {cat}
            </div>
            {V5_SKILLS[cat].map(([k, label]) => (
              <div key={k} style={rowStyle}>
                <span style={{ color: 'var(--sr-bone-300)', fontSize: '12px' }}>{label}</span>
                <DotTrack
                  label={label}
                  value={skills[k]}
                  maxRank={f.skillMax}
                  accent="var(--sr-gold-400)"
                  onChange={(n) => f.setSkills((prev) => ({ ...prev, [k]: n }))}
                />
              </div>
            ))}
          </div>
        ))}
      </div>
      <div style={{ marginTop: '16px' }}>
        <div style={{ color: 'var(--sr-bone-300)', fontSize: '12px', marginBottom: '8px' }}>
          {t('wizard:v5.specialtiesHelp', 'Specialties: {{n}} free (one each for rated Academics, Craft, Performance, Science, plus one of your choice). The predator type adds one more below.', { n: freeSpecialtyCount(skills) })}
        </div>
        {specialties.map((sp, i) => (
          <div key={i} style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '8px' }}>
            <select
              aria-label={t('wizard:v5.specialtySkill', 'Specialty {{n}} skill', { n: i + 1 })}
              value={sp.skill}
              onChange={(e) => setSpecialties((prev) => prev.map((x, j) => (j === i ? { ...x, skill: e.target.value } : x)))}
              style={{ ...inputStyle, flex: '1 1 160px', width: 'auto', padding: '8px' }}
            >
              <option value="">{t('wizard:v5.skillPick', 'Skill…')}</option>
              {V5_SKILL_KEYS.filter((k) => skills[k] > 0).map((k) => (
                <option key={k} value={k}>
                  {V5_SKILL_LABELS[k]}
                </option>
              ))}
            </select>
            <input
              aria-label={t('wizard:v5.specialtyName', 'Specialty {{n}} name', { n: i + 1 })}
              value={sp.name}
              placeholder={t('wizard:v5.specialtyPlaceholder', 'Specialty (e.g. Grappling)')}
              onChange={(e) => setSpecialties((prev) => prev.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))}
              style={{ ...inputStyle, flex: '2 1 200px', width: 'auto', padding: '8px' }}
            />
            <button
              type="button"
              onClick={() => setSpecialties((prev) => prev.filter((_, j) => j !== i))}
              aria-label={t('wizard:v5.removeSpecialty', 'Remove specialty {{n}}', { n: i + 1 })}
              style={smallButtonStyle}
            >
              ×
            </button>
          </div>
        ))}
        {specialties.length < freeSpecialtyCount(skills) ? (
          <button type="button" onClick={() => setSpecialties((prev) => [...prev, { skill: '', name: '' }])} style={addButtonStyle}>
            {t('wizard:v5.addSpecialty', '+ Add specialty')}
          </button>
        ) : null}
      </div>
    </ResponsiveSheetBlock>
  );
}
