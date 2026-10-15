import ResponsiveSheetBlock from '../ResponsiveSheetBlock';
import {
  V5_ATTRIBUTES,
  V5_FREE_SPECIALTY_SKILLS,
  V5_NAME_MAX,
  V5_SECTION_IDS,
  V5_SKILL_KEYS,
  V5_SKILL_LABELS,
  V5_XP_COSTS,
  V5_XP_MAX_DOTS,
} from '../../../characterSheet/v5/constants';
import { finalAttributes, finalSkills, xpDisciplineOptions, xpPreview } from '../../../characterSheet/v5/validation';
import { translateSheetError } from '../../../characterSheet/i18nErrors';
import { disciplineNames, ritualsOf } from '../../../characterSheet/v5/rulesData';
import { t } from '../../../i18n';
import { ACCENT, InlineError, inputStyle, rowStyle, useForge } from './forgeUi';

const XP_KINDS = ['attribute', 'skill', 'specialty', 'discipline', 'ritual'];
// Functions so t() runs at render time.
const XP_KIND_LABELS = {
  attribute: () => t('wizard:v5.xpKindAttribute', 'Attribute'),
  skill: () => t('wizard:v5.xpKindSkill', 'Skill'),
  specialty: () => t('wizard:v5.xpKindSpecialty', 'Specialty'),
  discipline: () => t('wizard:v5.xpKindDiscipline', 'Discipline'),
  ritual: () => t('wizard:v5.xpKindRitual', 'Ritual'),
};
const ATTRIBUTE_PAIRS = [...V5_ATTRIBUTES.physical, ...V5_ATTRIBUTES.social, ...V5_ATTRIBUTES.mental];
const SKILL_PAIRS = V5_SKILL_KEYS.map((k) => [k, V5_SKILL_LABELS[k]]);
const EMPTY_DRAFT = { kind: 'attribute', trait: '', skill: '', specialty: '', level: 1 };
const xpButtonStyle = { padding: '8px 14px', fontSize: '12px', background: 'var(--sr-night-800)', color: 'var(--sr-arcane-300)', border: '1px solid var(--sr-arcane-700)', borderRadius: '6px', cursor: 'pointer' };

/** Starting experience of the chosen age (neonates 15 XP, ancillae 35), one dot at a time. */
export default function ExperienceStep() {
  const f = useForge();
  const { sheet, xp, xpTotal, bsLevel, discRows, setXpDraft, setXpPurchases } = f;
  if (xpTotal <= 0) return null;
  const xpKinds = XP_KINDS.filter((k) => k !== 'ritual' || bsLevel >= 1);
  // A ritual draft falls back to Attribute when Blood Sorcery is gone.
  const draft = xpKinds.includes(f.xpDraft.kind) ? f.xpDraft : EMPTY_DRAFT;
  const draftPurchase =
    draft.kind === 'specialty'
      ? { kind: 'specialty', skill: draft.skill, trait: draft.trait }
      : draft.kind === 'ritual'
        ? { kind: 'ritual', trait: draft.trait, level: Number(draft.level) }
        : draft.kind === 'skill' && draft.specialty.trim()
          ? { kind: 'skill', trait: draft.trait, specialty: draft.specialty }
          : { kind: draft.kind, trait: draft.trait };
  const draftReady = draft.kind === 'specialty' ? Boolean(draft.skill && draft.trait.trim()) : Boolean(draft.trait.trim());
  const draftPreview = draftReady ? xpPreview(sheet, draftPurchase, disciplineNames()) : null;
  const xpAttrs = finalAttributes(sheet);
  const xpSkills = finalSkills(sheet).skills;
  // A first dot in Academics/Craft/Performance/Science brings a free specialty: ask for its name.
  const draftNeedsFreeSpecialty =
    draft.kind === 'skill' && V5_FREE_SPECIALTY_SKILLS.includes(draft.trait) && xpSkills[draft.trait] === 0;

  return (
    <ResponsiveSheetBlock
      sectionId={V5_SECTION_IDS.experience}
      title={t('wizard:v5.xpTitle', 'Starting experience')}
      subtitle={t('wizard:v5.xpSub', 'Optional: {{total}} XP to spend now, one dot at a time. Attributes new × {{attr}}, Skills new × {{skill}}, a new specialty {{spec}}, clan Disciplines new × {{clan}}, other Disciplines new × {{other}} (Caitiff new × {{caitiff}}), rituals level × {{ritual}}. Unspent XP is kept.', {
        total: xpTotal,
        attr: V5_XP_COSTS.attribute,
        skill: V5_XP_COSTS.skill,
        spec: V5_XP_COSTS.specialty,
        clan: V5_XP_COSTS.clan_discipline,
        other: V5_XP_COSTS.other_discipline,
        caitiff: V5_XP_COSTS.caitiff_discipline,
        ritual: V5_XP_COSTS.ritual,
      })}
      accent={ACCENT}
    >
      <InlineError id={V5_SECTION_IDS.experience} />
      <p
        id="v5-xp-count"
        aria-live="polite"
        style={{ color: xp.spent > xp.total ? 'var(--sr-blood-300)' : 'var(--sr-ok-400)', fontSize: '12px', margin: '0 0 10px' }}
      >
        {t('wizard:v5.xpCount', 'Spent {{spent}} of {{total}} XP · {{left}} left', { spent: xp.spent, total: xp.total, left: xp.unspent })}
      </p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center', marginBottom: '12px' }}>
        <select
          aria-label={t('wizard:v5.xpKind', 'What to buy')}
          value={draft.kind}
          onChange={(e) => setXpDraft({ ...EMPTY_DRAFT, kind: e.target.value })}
          style={{ ...inputStyle, flex: '0 1 160px', width: 'auto', padding: '8px' }}
        >
          {xpKinds.map((k) => (
            <option key={k} value={k}>
              {XP_KIND_LABELS[k]()}
            </option>
          ))}
        </select>
        {['attribute', 'skill', 'discipline'].includes(draft.kind) ? (
          <select
            aria-label={XP_KIND_LABELS[draft.kind]()}
            value={draft.trait}
            onChange={(e) => setXpDraft({ ...draft, trait: e.target.value, specialty: '' })}
            style={{ ...inputStyle, flex: '1 1 200px', width: 'auto', padding: '8px' }}
          >
            <option value="">{t('wizard:v5.choose', 'Choose…')}</option>
            {(draft.kind === 'attribute'
              ? ATTRIBUTE_PAIRS.map(([k, label]) => [k, label, xpAttrs[k]])
              : draft.kind === 'skill'
                ? SKILL_PAIRS.map(([k, label]) => [k, label, xpSkills[k]])
                : xpDisciplineOptions(sheet, disciplineNames()).map((d) => [d, d, discRows.find((r) => r.name === d)?.level || 0])
            ).map(([k, label, now]) => (
              <option key={k} value={k} disabled={now >= V5_XP_MAX_DOTS}>
                {label} ({now})
              </option>
            ))}
          </select>
        ) : null}
        {draftNeedsFreeSpecialty ? (
          <input
            aria-label={t('wizard:v5.xpFreeSpecialty', 'Free {{skill}} specialty', { skill: V5_SKILL_LABELS[draft.trait] })}
            value={draft.specialty}
            maxLength={V5_NAME_MAX}
            placeholder={t('wizard:v5.xpFreeSpecialtyPlaceholder', 'its free specialty (required)')}
            onChange={(e) => setXpDraft({ ...draft, specialty: e.target.value })}
            style={{ ...inputStyle, flex: '2 1 200px', width: 'auto', padding: '8px' }}
          />
        ) : null}
        {draft.kind === 'specialty' ? (
          <>
            <select
              aria-label={t('wizard:v5.xpSpecialtySkill', 'Specialty skill')}
              value={draft.skill}
              onChange={(e) => setXpDraft({ ...draft, skill: e.target.value })}
              style={{ ...inputStyle, flex: '1 1 160px', width: 'auto', padding: '8px' }}
            >
              <option value="">{t('wizard:v5.skillPick', 'Skill…')}</option>
              {SKILL_PAIRS.filter(([k]) => xpSkills[k] > 0).map(([k, label]) => (
                <option key={k} value={k}>
                  {label}
                </option>
              ))}
            </select>
            <input
              aria-label={t('wizard:v5.xpSpecialtyName', 'Specialty name')}
              value={draft.trait}
              maxLength={V5_NAME_MAX}
              placeholder={t('wizard:v5.specialtyPlaceholder', 'Specialty (e.g. Grappling)')}
              onChange={(e) => setXpDraft({ ...draft, trait: e.target.value })}
              style={{ ...inputStyle, flex: '2 1 200px', width: 'auto', padding: '8px' }}
            />
          </>
        ) : null}
        {draft.kind === 'ritual' ? (
          <>
            {ritualsOf('ritual', bsLevel).length ? (
              <select
                aria-label={t('wizard:v5.xpRitualName', 'Ritual name')}
                value={draft.trait}
                onChange={(e) => {
                  const r = ritualsOf('ritual', bsLevel).find((x) => x.name === e.target.value);
                  setXpDraft({ ...draft, trait: e.target.value, level: r ? r.level : draft.level });
                }}
                style={{ ...inputStyle, flex: '2 1 200px', width: 'auto', padding: '8px' }}
              >
                <option value="">{t('wizard:v5.choose', 'Choose…')}</option>
                {ritualsOf('ritual', bsLevel).map((r) => (
                  <option key={r.id || r.name} value={r.name}>
                    {t('wizard:v5.powerOption', '{{name}} (level {{level}})', { name: r.name, level: r.level })}
                  </option>
                ))}
              </select>
            ) : (
              <input
                aria-label={t('wizard:v5.xpRitualName', 'Ritual name')}
                value={draft.trait}
                maxLength={V5_NAME_MAX}
                onChange={(e) => setXpDraft({ ...draft, trait: e.target.value })}
                style={{ ...inputStyle, flex: '2 1 200px', width: 'auto', padding: '8px' }}
              />
            )}
            <select
              aria-label={t('wizard:v5.xpRitualLevel', 'Ritual level')}
              value={draft.level}
              onChange={(e) => setXpDraft({ ...draft, level: Number(e.target.value) })}
              style={{ ...inputStyle, flex: '0 1 110px', width: 'auto', padding: '8px' }}
            >
              {Array.from({ length: Math.min(V5_XP_MAX_DOTS, Math.max(1, bsLevel)) }, (_, i) => i + 1).map((lv) => (
                <option key={lv} value={lv}>
                  {t('wizard:v5.xpLevelOption', 'Level {{n}}', { n: lv })}
                </option>
              ))}
            </select>
          </>
        ) : null}
        <button
          type="button"
          disabled={!draftPreview || Boolean(draftPreview.error)}
          onClick={() => {
            setXpPurchases((prev) => [...prev, draftPurchase]);
            if (draft.kind === 'specialty' || draft.kind === 'ritual') setXpDraft({ ...draft, trait: '' });
            else if (draftNeedsFreeSpecialty) setXpDraft({ ...draft, specialty: '' });
          }}
          style={xpButtonStyle}
        >
          {draftPreview ? t('wizard:v5.xpBuy', 'Buy ({{cost}} XP)', { cost: draftPreview.cost }) : t('wizard:v5.xpBuyPick', 'Buy')}
        </button>
      </div>
      {draftPreview?.error ? (
        <p role="alert" style={{ color: 'var(--sr-blood-300)', fontSize: '12px', margin: '0 0 10px' }}>{translateSheetError(draftPreview.error)}</p>
      ) : null}
      {xp.log.length ? (
        <ul aria-label={t('wizard:v5.xpBought', 'Bought with XP')} style={{ listStyle: 'none', padding: 0, margin: 0 }}>
          {xp.log.map((e) => (
            <li key={e.purchase} style={{ ...rowStyle, color: 'var(--sr-bone-100)', fontSize: '13px' }}>
              <span>
                {e.kind === 'ritual'
                  ? t('wizard:v5.xpRitualEntry', '{{name}}, Level {{level}}', { name: e.what, level: e.to })
                  : e.kind === 'specialty'
                    ? e.what
                    : `${e.what} ${e.from} → ${e.to}${e.specialty ? ` (${e.specialty})` : ''}`}
                <span style={{ color: 'var(--sr-ok-400)' }}> · {e.cost} XP</span>
              </span>
              <button
                type="button"
                aria-label={t('wizard:v5.xpRemove', 'Remove {{what}}', { what: e.what })}
                onClick={() => setXpPurchases((prev) => prev.filter((_, j) => j !== e.purchase))}
                style={{ padding: '4px 10px', background: 'var(--sr-night-800)', color: 'var(--sr-bone-300)', border: '1px solid var(--sr-night-600)', borderRadius: '6px', cursor: 'pointer' }}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p style={{ color: 'var(--sr-bone-300)', fontSize: '12px', margin: 0 }}>{t('wizard:v5.xpNothing', 'Nothing bought yet.')}</p>
      )}
    </ResponsiveSheetBlock>
  );
}
