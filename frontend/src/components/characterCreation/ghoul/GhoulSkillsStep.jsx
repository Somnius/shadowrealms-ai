import ResponsiveSheetBlock from '../ResponsiveSheetBlock';
import DotTrack from '../DotTrack';
import { V5_SECTION_IDS, V5_SKILLS, V5_SKILL_DISTRIBUTIONS, V5_SKILL_KEYS, V5_SKILL_LABELS } from '../../../characterSheet/v5/constants';
import { GHOUL_TEMPLATES, PLAYER_GHOUL, ghoulSkillCounts, ghoulSpecialtyCount } from '../../../characterSheet/v5/ghoul';
import { ghoulTemplateName } from '../../../characterSheet/i18nErrors';
import { t } from '../../../i18n';
import { Term } from '../../../i18n/glossary';
import { ACCENT, InlineError, SpreadChips, addButtonStyle, inputStyle, labelStyle, rowStyle, smallButtonStyle, useForge } from '../v5/forgeUi';

const countsText = (counts) =>
  Object.keys(counts || {})
    .map(Number)
    .sort((a, b) => b - a)
    .map((r) => `${counts[r]}×${r}`)
    .join(', ');

/** Skills: the template's counts (core p. 185) or a player ghoul's distribution (PG p. 141), then specialties. */
export default function GhoulSkillsStep() {
  const f = useForge();
  const { skills, specialties, setSpecialties } = f;
  const player = f.template === PLAYER_GHOUL;
  const tpl = GHOUL_TEMPLATES[f.template];
  const allowed = ghoulSpecialtyCount(f.template, skills);
  return (
    <ResponsiveSheetBlock
      sectionId={V5_SECTION_IDS.skills}
      title={<Term id="skills" />}
      subtitle={
        player
          ? t('wizard:v5.skillsSub', 'Pick a distribution, then free specialties.')
          : t('wizard:ghoul.skillsTemplate', '{{template}}: {{counts}} (core p. 185).', { template: ghoulTemplateName(f.template), counts: countsText(ghoulSkillCounts(f.template)) })
      }
      accent={ACCENT}
    >
      <InlineError id={V5_SECTION_IDS.skills} />
      {player ? (
        <>
          <label htmlFor="ghoul-field-distribution" style={labelStyle}>{t('wizard:v5.distribution', 'Distribution')}</label>
          <select
            id="ghoul-field-distribution"
            value={f.skillDistribution}
            onChange={(e) => f.setSkillDistribution(e.target.value)}
            style={{ ...inputStyle, maxWidth: '420px', marginBottom: '12px' }}
          >
            {Object.entries(V5_SKILL_DISTRIBUTIONS).map(([k, d]) => (
              <option key={k} value={k}>
                {d.label}: {countsText(d.counts)}
              </option>
            ))}
          </select>
        </>
      ) : null}
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
        <div id="ghoul-specialties-help" style={{ color: 'var(--sr-bone-300)', fontSize: '12px', marginBottom: '8px' }}>
          {player
            ? t('wizard:ghoul.specialtiesPlayer', 'Specialties: {{n}} (one each for rated Academics, Craft, Performance, Science, plus one of your choice; Players Guide p. 141).', { n: allowed })
            : t('wizard:ghoul.specialtiesTemplate', "Specialties: {{n}} here: the template's {{own}} on Skills with dots, plus one for each rated Academics, Craft, Performance and Science.", { n: allowed, own: tpl ? tpl.specialties : 0 })}
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
              {V5_SKILL_KEYS.filter((k) => skills[k] > 0 || k === sp.skill).map((k) => (
                <option key={k} value={k}>
                  {V5_SKILL_LABELS[k]}
                </option>
              ))}
            </select>
            <input
              aria-label={t('wizard:v5.specialtyName', 'Specialty {{n}} name', { n: i + 1 })}
              value={sp.name}
              maxLength={100}
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
        {specialties.length < allowed ? (
          <button type="button" onClick={() => setSpecialties((prev) => [...prev, { skill: '', name: '' }])} style={addButtonStyle}>
            {t('wizard:v5.addSpecialty', '+ Add specialty')}
          </button>
        ) : null}
      </div>
    </ResponsiveSheetBlock>
  );
}
