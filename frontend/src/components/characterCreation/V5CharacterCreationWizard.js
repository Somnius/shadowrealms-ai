import { useMemo, useState } from 'react';
import { GothicBox } from '../GothicDecorations';
import DotTrack from './DotTrack';
import MeritFlawRows from './MeritFlawRows';
import ResponsiveSheetBlock from './ResponsiveSheetBlock';
import { createEmptyMeritRow } from '../../characterSheet/meritsFlaws';
import { editionLabel } from '../../rules/rulesEdition';
import {
  CAITIFF,
  THIN_BLOOD,
  V5_AGE_BRACKETS,
  V5_ATTRIBUTES,
  V5_BACKGROUNDS,
  V5_CLAN_NAMES,
  V5_DISCIPLINES,
  V5_DISCIPLINE_DOTS,
  V5_PREDATOR_TYPES,
  V5_SECTION_IDS,
  V5_SKILLS,
  V5_SKILL_DISTRIBUTIONS,
  V5_SKILL_KEYS,
  V5_SKILL_LABELS,
  V5_FLEDGLING_HUMANITY,
  V5_NAME_MAX,
  V5_STARTING_HUMANITY,
  V5_THIN_BLOOD_MERITS,
  V5_FREE_SPECIALTY_SKILLS,
  V5_XP_COSTS,
  V5_XP_MAX_DOTS,
  toKey,
} from '../../characterSheet/v5/constants';
import {
  attributeSpreadStatus,
  bloodSorceryLevel,
  buildV5Payload,
  clanInfo,
  creationDisciplineOptions,
  deriveV5,
  disciplineRows,
  emptyV5Attributes,
  emptyV5Skills,
  finalAttributes,
  finalSkills,
  fledglingHumanityAllowed,
  freeSpecialtyCount,
  startingRitualAllowed,
  predatorDisciplineOptions,
  predatorInfo,
  skillSpreadStatus,
  startingXp,
  validateV5Sheet,
  xpDisciplineOptions,
  xpLedger,
  xpPreview,
} from '../../characterSheet/v5/validation';
import { translateSheetError, translateSheetErrors } from '../../characterSheet/i18nErrors';
import { t } from '../../i18n';
import { Term } from '../../i18n/glossary';
import { authFetch } from '../../app/http';

const API_URL = '/api';
const ACCENT = 'var(--sr-blood-500)';

// Labels are functions so t() runs at render time. Game terms stay English.
const SECTION_ORDER = [
  [V5_SECTION_IDS.identity, () => t('wizard:section.identity', 'Identity')],
  [V5_SECTION_IDS.clan, () => 'Clan'],
  [V5_SECTION_IDS.attributes, () => 'Attributes'],
  [V5_SECTION_IDS.skills, () => 'Skills'],
  [V5_SECTION_IDS.disciplines, () => 'Disciplines'],
  [V5_SECTION_IDS.predator, () => 'Predator'],
  [V5_SECTION_IDS.advantages, () => 'Advantages'],
  [V5_SECTION_IDS.experience, () => 'XP'],
  [V5_SECTION_IDS.humanity, () => 'Humanity'],
  [V5_SECTION_IDS.story, () => t('wizard:section.story', 'Story')],
];

const inputStyle = {
  width: '100%',
  padding: '10px',
  background: 'var(--sr-night-850)',
  color: 'var(--sr-bone-100)',
  border: '2px solid var(--sr-night-700)',
  borderRadius: '8px',
};
const labelStyle = { color: 'var(--sr-arcane-300)', display: 'block', marginBottom: '6px', fontSize: '13px' };
const rowStyle = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: '8px',
  marginBottom: '8px',
  padding: '5px 8px',
  background: 'rgba(0,0,0,0.2)',
  borderRadius: '6px',
};
const gridStyle = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
  gap: '14px',
};

function scrollToSection(id) {
  const el = typeof document !== 'undefined' ? document.getElementById(id) : null;
  el?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function SpreadChips({ status }) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '14px' }}>
      {status.map(({ rating, need, have }) => {
        const ok = need === have;
        return (
          <span
            key={rating}
            style={{
              fontSize: '11px',
              padding: '4px 10px',
              borderRadius: '6px',
              background: ok ? 'rgba(34,197,94,0.12)' : 'rgba(248,113,113,0.08)',
              color: ok ? 'var(--sr-ok-400)' : 'var(--sr-blood-300)',
              border: `1px solid ${ok ? '#16653444' : '#991b1b33'}`,
            }}
          >
            {'●'.repeat(rating)} {have}/{need}
          </span>
        );
      })}
    </div>
  );
}

const DOT_COLOURS = { base: ACCENT, predator: 'var(--sr-gold-400)', xp: 'var(--sr-ok-400)' };

/**
 * Read-only Discipline dots, coloured by source: creation dots, the predator type's dot, XP dots.
 */
function SourceDots({ label, row, maxRank = 5 }) {
  const sources = [
    ...Array(row.base).fill('base'),
    ...Array(row.predator).fill('predator'),
    ...Array(row.xp).fill('xp'),
  ];
  return (
    <div
      role="group"
      aria-label={t('wizard:dots.labelled', '{{label}}: {{rank}} of {{max}}', { label, rank: row.level, max: maxRank })}
      style={{ display: 'flex', alignItems: 'center', gap: '5px' }}
    >
      {Array.from({ length: Math.max(maxRank, sources.length) }, (_, i) => {
        const src = sources[i];
        const c = src ? DOT_COLOURS[src] : null;
        return (
          <span
            key={i}
            data-dot={src || 'empty'}
            style={{
              width: '18px',
              height: '18px',
              borderRadius: '50%',
              boxSizing: 'border-box',
              border: `2px ${src && src !== 'base' ? 'dashed' : 'solid'} ${c || 'var(--sr-night-600)'}`,
              background: c ? `radial-gradient(circle at 30% 30%, ${c}, var(--sr-arcane-700))` : 'transparent',
            }}
          />
        );
      })}
    </div>
  );
}

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

const isBackgroundName = (name) =>
  V5_BACKGROUNDS.some((b) => String(name || '').toLowerCase().startsWith(b.toLowerCase()));

/**
 * V5 character forge (docs/rules/V5.md §4). Pure rules live in characterSheet/v5/validation.js.
 */
export default function V5CharacterCreationWizard({
  token,
  campaigns,
  campaignId,
  onCampaignChange,
  onDone,
  onCancel,
  showError,
  showSuccess,
}) {
  const [name, setName] = useState('');
  const [concept, setConcept] = useState('');
  const [sire, setSire] = useState('');
  const [ambition, setAmbition] = useState('');
  const [desire, setDesire] = useState('');
  const [clan, setClan] = useState('Brujah');
  const [age, setAge] = useState('neonate');
  const [generation, setGeneration] = useState(13);
  const [attributes, setAttributes] = useState(() => emptyV5Attributes());
  const [skillDistribution, setSkillDistribution] = useState('balanced');
  const [skills, setSkills] = useState(() => emptyV5Skills());
  const [specialties, setSpecialties] = useState([{ skill: '', name: '' }]);
  const [disciplines, setDisciplines] = useState([
    { name: '', level: V5_DISCIPLINE_DOTS[0], powers: [] },
    { name: '', level: V5_DISCIPLINE_DOTS[1], powers: [] },
  ]);
  const [predatorType, setPredatorType] = useState('');
  const [predatorSpecialty, setPredatorSpecialty] = useState(null);
  const [predatorDiscipline, setPredatorDiscipline] = useState('');
  // Powers for a predator Discipline that isn't one of the two picks: { [discipline]: [power] }.
  const [extraPowers, setExtraPowers] = useState({});
  // One optional Level 1 ritual with Blood Sorcery 1+ (V5.md §4 step 6).
  const [startingRitual, setStartingRitual] = useState('');
  const [meritRows, setMeritRows] = useState(() => [createEmptyMeritRow()]);
  const [meritNotes, setMeritNotes] = useState('');
  const [convictions, setConvictions] = useState([{ conviction: '', touchstone: '' }]);
  const [tenets, setTenets] = useState('');
  const [background, setBackground] = useState('');
  // Fledgling option: start at Humanity 8 instead of 7 (V5.md §2.6, §4 step 9).
  const [fledglingHumanity, setFledglingHumanity] = useState(false);
  // Thin-blood Merits/Flaws: no dot value, 1–3 of each in matching numbers.
  const [thinBloodMerits, setThinBloodMerits] = useState([{ name: '' }]);
  const [thinBloodFlaws, setThinBloodFlaws] = useState([{ name: '' }]);
  // Starting experience (neonates 15 XP, ancillae 35): one entry per dot, see v5/validation.js.
  const [xpPurchases, setXpPurchases] = useState([]);
  const [xpDraft, setXpDraft] = useState({ kind: 'attribute', trait: '', skill: '', specialty: '', level: 1 });
  const [fieldErrors, setFieldErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);

  const advantages = meritRows
    .filter((r) => String(r.name || '').trim() && Number(r.points) > 0)
    .map((r) => ({
      name: r.name,
      dots: Number(r.points),
      kind: isBackgroundName(r.name) ? 'background' : 'merit',
    }));
  const flaws = meritRows
    .filter((r) => String(r.name || '').trim() && Number(r.points) < 0)
    .map((r) => ({ name: r.name, dots: -Number(r.points) }));

  const sheet = {
    name,
    concept,
    sire,
    ambition,
    desire,
    chronicle_tenets: tenets,
    clan,
    age,
    generation,
    attributes,
    skillDistribution,
    skills,
    specialties: specialties.filter((x) => x.skill || String(x.name || '').trim()),
    disciplines: clan === THIN_BLOOD ? [] : disciplines,
    predatorType,
    predatorSpecialty,
    predatorDiscipline,
    extraPowers,
    startingRitual,
    advantages,
    flaws,
    convictions,
    fledglingHumanity,
    thinBloodMerits,
    thinBloodFlaws,
    xpPurchases,
  };
  const derived = deriveV5(sheet);
  const xp = xpLedger(sheet, V5_DISCIPLINES);
  const xpTotal = startingXp(sheet);
  const bsLevel = bloodSorceryLevel(sheet);
  const xpKinds = XP_KINDS.filter((k) => k !== 'ritual' || bsLevel >= 1);
  // A ritual draft falls back to Attribute when Blood Sorcery is gone.
  const draft = xpKinds.includes(xpDraft.kind) ? xpDraft : { kind: 'attribute', trait: '', skill: '', specialty: '', level: 1 };
  const draftPurchase =
    draft.kind === 'specialty'
      ? { kind: 'specialty', skill: draft.skill, trait: draft.trait }
      : draft.kind === 'ritual'
        ? { kind: 'ritual', trait: draft.trait, level: Number(draft.level) }
        : draft.kind === 'skill' && draft.specialty.trim()
          ? { kind: 'skill', trait: draft.trait, specialty: draft.specialty }
          : { kind: draft.kind, trait: draft.trait };
  const draftReady =
    draft.kind === 'specialty' ? Boolean(draft.skill && draft.trait.trim()) : Boolean(draft.trait.trim());
  const draftPreview = draftReady ? xpPreview(sheet, draftPurchase, V5_DISCIPLINES) : null;
  const xpAttrs = finalAttributes(sheet);
  const xpSkills = finalSkills(sheet).skills;
  // A first dot in Academics/Craft/Performance/Science brings a free specialty: ask for its name.
  const draftNeedsFreeSpecialty =
    draft.kind === 'skill' && V5_FREE_SPECIALTY_SKILLS.includes(draft.trait) && xpSkills[draft.trait] === 0;
  const clanRow = clanInfo(clan);
  const pred = predatorInfo(predatorType);
  const discOptions = creationDisciplineOptions(clan, V5_DISCIPLINES);
  const discRows = disciplineRows(sheet);
  const predDiscOptions = predatorDisciplineOptions(predatorType, clan);
  const dist = V5_SKILL_DISTRIBUTIONS[skillDistribution];
  const skillMax = Math.max(...Object.keys(dist.counts).map(Number));
  const attrStatus = useMemo(() => attributeSpreadStatus(attributes), [attributes]);
  const skillStatus = skillSpreadStatus(skills, skillDistribution);
  const advDots = advantages.reduce((s, a) => s + a.dots, 0);
  const flawDots =
    flaws.reduce((s, f) => s + f.dots, 0) + (pred?.flaws || []).reduce((s, f) => s + f.dots, 0);

  const changeAge = (next) => {
    setAge(next);
    if (!V5_AGE_BRACKETS[next].xp) setXpPurchases([]);
    const gens = V5_AGE_BRACKETS[next].generations;
    if (!gens.includes(Number(generation))) setGeneration(gens.includes(13) ? 13 : gens[gens.length - 1]);
  };

  const changeClan = (next) => {
    setClan(next);
    setDisciplines([
      { name: '', level: V5_DISCIPLINE_DOTS[0], powers: [] },
      { name: '', level: V5_DISCIPLINE_DOTS[1], powers: [] },
    ]);
    setPredatorDiscipline('');
    setExtraPowers({});
    setXpPurchases([]);
    if (next === THIN_BLOOD) {
      setAge('childer');
      setGeneration(14);
    } else if (Number(generation) >= 14) {
      setGeneration(13);
    }
  };

  const setDisc = (i, patch) =>
    setDisciplines((prev) => prev.map((d, j) => (j === i ? { ...d, ...patch } : d)));

  const handleSubmit = async () => {
    const err = translateSheetErrors(validateV5Sheet(sheet, V5_DISCIPLINES));
    if (!campaignId) err[V5_SECTION_IDS.identity] = t('wizard:error.chronicle', 'Choose a chronicle.');
    setFieldErrors(err);
    const first = SECTION_ORDER.find(([id]) => err[id]);
    if (first) {
      showError?.(err[first[0]]);
      scrollToSection(first[0]);
      return;
    }
    const payload = buildV5Payload(sheet);
    if (meritNotes.trim()) payload.merits_flaws.notes = meritNotes.trim();
    setSubmitting(true);
    try {
      const res = await authFetch(`${API_URL}/characters/`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name.trim(),
          campaign_id: parseInt(campaignId, 10),
          ...payload,
          background: background.trim(),
          sheet_locked: true,
          is_active: true,
        }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        showError?.(body.error || t('wizard:error.createFailed', 'Could not create character.'));
        return;
      }
      showSuccess?.(t('wizard:v5.created', 'Character embraced. Here is the chronicle: you can play right away.'));
      onDone?.(body, parseInt(campaignId, 10));
    } catch {
      showError?.(t('wizard:error.network', 'Network error while creating character.'));
    } finally {
      setSubmitting(false);
    }
  };

  const inlineErr = (id) =>
    fieldErrors[id] ? (
      <p style={{ color: 'var(--sr-danger-400)', fontSize: '13px', marginBottom: '12px' }}>{fieldErrors[id]}</p>
    ) : null;

  const textField = (idKey, label, value, setter, placeholder) => {
    const id = `v5-field-${toKey(idKey)}`;
    return (
      <div>
        <label htmlFor={id} style={labelStyle}>
          {label}
        </label>
        <input
          id={id}
          value={value}
          onChange={(e) => setter(e.target.value)}
          placeholder={placeholder}
          style={inputStyle}
        />
      </div>
    );
  };

  /** Free-text rows for thin-blood Merits or Flaws (names only, no dots). */
  const thinRows = (kind, rows, setRows) => {
    const [, hi] = V5_THIN_BLOOD_MERITS;
    return (
      <div style={{ flex: '1 1 240px', minWidth: 0 }}>
        <div id={`v5-thin-${kind}-label`} style={labelStyle}>
          Thin-blood {kind} ({rows.filter((r) => String(r.name || '').trim()).length})
        </div>
        {rows.map((r, i) => (
          <div key={i} style={{ display: 'flex', gap: '8px', marginBottom: '6px' }}>
            <input
              value={r.name}
              aria-label={`Thin-blood ${kind.replace(/s$/, '')} ${i + 1}`}
              placeholder={kind === 'Merits' ? t('wizard:v5.thinMeritPlaceholder', 'e.g. Day Drinker') : t('wizard:v5.thinFlawPlaceholder', 'e.g. Baby Teeth')}
              onChange={(e) =>
                setRows((prev) => prev.map((x, j) => (j === i ? { name: e.target.value } : x)))
              }
              style={{ ...inputStyle, flex: '1 1 auto', width: 'auto', padding: '8px' }}
            />
            {rows.length > 1 ? (
              <button
                type="button"
                aria-label={t('wizard:v5.removeThin', 'Remove thin-blood {{kind}} {{n}}', { kind: kind.replace(/s$/, ''), n: i + 1 })}
                onClick={() => setRows((prev) => prev.filter((_, j) => j !== i))}
                style={{ padding: '6px 10px', background: 'var(--sr-night-800)', color: 'var(--sr-bone-300)', border: '1px solid var(--sr-night-600)', borderRadius: '6px', cursor: 'pointer' }}
              >
                ×
              </button>
            ) : null}
          </div>
        ))}
        {rows.length < hi ? (
          <button
            type="button"
            onClick={() => setRows((prev) => [...prev, { name: '' }])}
            style={{ padding: '6px 12px', fontSize: '12px', background: 'transparent', color: 'var(--sr-arcane-300)', border: '1px dashed var(--sr-arcane-700)', borderRadius: '6px', cursor: 'pointer' }}
          >
            {kind === 'Merits' ? t('wizard:v5.addMerit', '+ Add Merit') : t('wizard:v5.addFlaw', '+ Add Flaw')}
          </button>
        ) : null}
      </div>
    );
  };

  return (
    <div style={{ maxWidth: '1040px', margin: '0 auto', padding: '20px 16px 60px' }}>
      <GothicBox theme="vampire">
        <div style={{ padding: '8px 8px 0' }}>
          <h2 style={{ fontFamily: 'var(--sr-font-display)', color: ACCENT, marginTop: 0, fontSize: '22px' }}>
            {t('wizard:v5.title', 'Character sheet forge · V5')}
          </h2>
          <p style={{ color: 'var(--sr-bone-500)', fontSize: '14px', lineHeight: 1.5 }}>
            {t('wizard:v5.intro', 'Vampire: The Masquerade 5th Edition creation: fixed attribute spread, a skill distribution, 2 + 1 Discipline dots, a predator type, 7 Advantage dots and at least 2 Flaw dots. No freebie points in V5.')}
          </p>
        </div>

        <div
          style={{
            position: 'sticky',
            top: 0,
            zIndex: 20,
            padding: '12px 16px',
            margin: '0 -4px 8px',
            background: 'linear-gradient(180deg, rgba(15,23,41,0.98) 70%, transparent)',
            borderBottom: '1px solid var(--sr-night-700)',
          }}
        >
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
            {SECTION_ORDER.filter(([id]) => id !== V5_SECTION_IDS.experience || xpTotal > 0).map(([id, label]) => (
              <button
                key={id}
                type="button"
                onClick={() => scrollToSection(id)}
                style={{
                  fontSize: '11px',
                  padding: '6px 12px',
                  borderRadius: '999px',
                  background: fieldErrors[id] ? 'rgba(248,113,113,0.15)' : 'var(--sr-night-800)',
                  // blood-400 on night-800 passes 4.5:1 at 11px (blood-500 was 4.15:1)
                  color: fieldErrors[id] ? 'var(--sr-blood-300)' : 'var(--sr-blood-400)',
                  border: `1px solid ${fieldErrors[id] ? 'var(--sr-blood-700)' : 'var(--sr-night-600)'}`,
                  cursor: 'pointer',
                  fontFamily: 'var(--sr-font-display)',
                }}
              >
                {label()}
              </button>
            ))}
          </div>
          <div style={{ marginTop: '10px', display: 'flex', flexWrap: 'wrap', gap: '12px', fontSize: '12px', color: 'var(--sr-bone-300)' }}>
            <span>
              <strong style={{ color: 'var(--sr-bone-100)' }}>{name || '—'}</strong>
              {concept ? ` · ${concept}` : ''}
            </span>
            <span style={{ color: ACCENT }}>{clan}</span>
            <span>
              <Term id="health">Health {derived.health}</Term> · <Term id="willpower">Willpower {derived.willpower}</Term> ·{' '}
              <Term id="humanity">Humanity {derived.humanity}</Term> · <Term id="bloodPotency">BP {derived.blood_potency}</Term> ·{' '}
              <Term id="hunger">Hunger {derived.hunger}</Term>
            </span>
          </div>
        </div>

        <div style={{ padding: '8px 16px 24px' }}>
          <ResponsiveSheetBlock sectionId={V5_SECTION_IDS.identity} title={t('wizard:section.identity', 'Identity')} subtitle={t('wizard:v5.identitySub', 'Chronicle and concept')} accent={ACCENT}>
            {inlineErr(V5_SECTION_IDS.identity)}
            <label htmlFor="v5-field-chronicle" style={labelStyle}>{t('wizard:field.chronicle', 'Chronicle')}</label>
            <select
              id="v5-field-chronicle"
              value={campaignId}
              onChange={(e) => onCampaignChange(e.target.value)}
              style={{ ...inputStyle, marginBottom: '16px' }}
            >
              {campaigns.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} — {c.game_system}
                  {String(c.game_system || '').toLowerCase() === 'vampire' ? ` (${editionLabel(c)})` : ''}
                </option>
              ))}
            </select>
            <div style={gridStyle}>
              {textField('Character name', t('wizard:field.name', 'Character name'), name, setName)}
              {textField('Concept', t('wizard:field.concept', 'Concept'), concept, setConcept, t('wizard:v5.conceptPlaceholder', 'e.g. burned-out paramedic'))}
              {textField('Sire', 'Sire', sire, setSire, t('wizard:v5.optional', 'optional'))}
              {textField('Ambition', 'Ambition', ambition, setAmbition, t('wizard:v5.ambitionPlaceholder', 'long-term goal'))}
              {textField('Desire', 'Desire', desire, setDesire, t('wizard:v5.desirePlaceholder', 'this session'))}
            </div>
          </ResponsiveSheetBlock>

          <ResponsiveSheetBlock
            sectionId={V5_SECTION_IDS.clan}
            title="Clan & Generation"
            subtitle={t('wizard:v5.clanSub', 'Age sets the generation range and starting Blood Potency.')}
            accent={ACCENT}
          >
            {inlineErr(V5_SECTION_IDS.clan)}
            <div style={gridStyle}>
              <div>
                <label htmlFor="v5-field-clan" style={labelStyle}><Term id="clan" /></label>
                <select id="v5-field-clan" value={clan} onChange={(e) => changeClan(e.target.value)} style={inputStyle}>
                  {V5_CLAN_NAMES.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor="v5-field-age" style={labelStyle}>{t('wizard:v5.age', 'Age')}</label>
                <select id="v5-field-age" value={age} onChange={(e) => changeAge(e.target.value)} style={inputStyle}>
                  {Object.entries(V5_AGE_BRACKETS).map(([k, a]) => (
                    <option key={k} value={k}>
                      {a.label}
                      {a.xp ? ` (${a.xp} XP)` : ''}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor="v5-field-generation" style={labelStyle}><Term id="generation" /></label>
                <select
                  id="v5-field-generation"
                  value={generation}
                  onChange={(e) => setGeneration(parseInt(e.target.value, 10))}
                  style={inputStyle}
                >
                  {V5_AGE_BRACKETS[age].generations.map((g) => (
                    <option key={g} value={g}>
                      {t('wizard:v5.generationOption', '{{g}}th', { g })}
                      {g >= 14 ? ' (thin-blood)' : ''}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            {clanRow ? (
              <p style={{ color: 'var(--sr-bone-300)', fontSize: '13px', marginTop: '12px', lineHeight: 1.5 }}>
                {clanRow.disciplines.length ? (
                  <>
                    <strong style={{ color: 'var(--sr-arcane-300)' }}>Disciplines:</strong> {clanRow.disciplines.join(', ')}.{' '}
                  </>
                ) : null}
                {clanRow.bane_summary ? (
                  <>
                    <strong style={{ color: 'var(--sr-arcane-300)' }}>Bane:</strong> {clanRow.bane_summary}.{' '}
                  </>
                ) : null}
                {clanRow.compulsion ? (
                  <>
                    <strong style={{ color: 'var(--sr-arcane-300)' }}>Compulsion:</strong> {clanRow.compulsion}.
                  </>
                ) : null}
              </p>
            ) : null}
          </ResponsiveSheetBlock>

          <ResponsiveSheetBlock
            sectionId={V5_SECTION_IDS.attributes}
            title={<Term id="attributes" />}
            subtitle={t('wizard:v5.attributesSub', 'One at 4, three at 3, four at 2, one at 1.')}
            accent={ACCENT}
          >
            {inlineErr(V5_SECTION_IDS.attributes)}
            <SpreadChips status={attrStatus} />
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '18px' }}>
              {['physical', 'social', 'mental'].map((cat) => (
                <div key={cat} style={{ flex: '1 1 200px', minWidth: 0 }}>
                  <div style={{ textAlign: 'center', fontFamily: 'var(--sr-font-display)', fontSize: '12px', color: ACCENT, marginBottom: '10px', textTransform: 'capitalize' }}>
                    {cat}
                  </div>
                  {V5_ATTRIBUTES[cat].map(([k, label]) => (
                    <div key={k} style={rowStyle}>
                      <span style={{ color: 'var(--sr-bone-100)', fontSize: '13px' }}>{label}</span>
                      <DotTrack
                        label={label}
                        value={attributes[k]}
                        maxRank={4}
                        accent={ACCENT}
                        onChange={(n) => setAttributes((prev) => ({ ...prev, [k]: Math.max(1, n) }))}
                      />
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </ResponsiveSheetBlock>

          <ResponsiveSheetBlock
            sectionId={V5_SECTION_IDS.skills}
            title={<Term id="skills" />}
            subtitle={t('wizard:v5.skillsSub', 'Pick a distribution, then free specialties.')}
            accent={ACCENT}
          >
            {inlineErr(V5_SECTION_IDS.skills)}
            <label htmlFor="v5-field-distribution" style={labelStyle}>{t('wizard:v5.distribution', 'Distribution')}</label>
            <select
              id="v5-field-distribution"
              value={skillDistribution}
              onChange={(e) => setSkillDistribution(e.target.value)}
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
            <SpreadChips status={skillStatus} />
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
                        maxRank={skillMax}
                        accent="var(--sr-gold-400)"
                        onChange={(n) => setSkills((prev) => ({ ...prev, [k]: n }))}
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
                    onChange={(e) =>
                      setSpecialties((prev) => prev.map((x, j) => (j === i ? { ...x, skill: e.target.value } : x)))
                    }
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
                    onChange={(e) =>
                      setSpecialties((prev) => prev.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))
                    }
                    style={{ ...inputStyle, flex: '2 1 200px', width: 'auto', padding: '8px' }}
                  />
                  <button
                    type="button"
                    onClick={() => setSpecialties((prev) => prev.filter((_, j) => j !== i))}
                    aria-label={t('wizard:v5.removeSpecialty', 'Remove specialty {{n}}', { n: i + 1 })}
                    style={{ padding: '6px 10px', background: 'var(--sr-night-800)', color: 'var(--sr-bone-300)', border: '1px solid var(--sr-night-600)', borderRadius: '6px', cursor: 'pointer' }}
                  >
                    ×
                  </button>
                </div>
              ))}
              {specialties.length < freeSpecialtyCount(skills) ? (
                <button
                  type="button"
                  onClick={() => setSpecialties((prev) => [...prev, { skill: '', name: '' }])}
                  style={{ padding: '6px 12px', fontSize: '12px', background: 'transparent', color: 'var(--sr-arcane-300)', border: '1px dashed var(--sr-arcane-700)', borderRadius: '6px', cursor: 'pointer' }}
                >
                  {t('wizard:v5.addSpecialty', '+ Add specialty')}
                </button>
              ) : null}
            </div>
          </ResponsiveSheetBlock>

          <ResponsiveSheetBlock
            sectionId={V5_SECTION_IDS.disciplines}
            title={<Term id="discipline">Disciplines</Term>}
            subtitle={
              clan === THIN_BLOOD
                ? t('wizard:v5.discThin', 'Thin-bloods start with no Disciplines.')
                : clan === CAITIFF
                  ? t('wizard:v5.discCaitiff', 'Any two Disciplines: one at 2 dots, one at 1. One power per dot.')
                  : t('wizard:v5.discClan', 'Two clan Disciplines: one at 2 dots, one at 1. One power per dot.')
            }
            accent={ACCENT}
          >
            {inlineErr(V5_SECTION_IDS.disciplines)}
            {discRows.map((row, i) => {
              const discLabel = row.name || `Discipline ${i + 1}`;
              const setPower = (p, value) => {
                const powers = [...row.powers];
                powers[p] = value;
                if (row.pick != null) setDisc(row.pick, { powers });
                else setExtraPowers((prev) => ({ ...prev, [row.name]: powers }));
              };
              return (
                <div key={row.pick != null ? `pick-${row.pick}` : `extra-${row.name}`} style={{ marginBottom: '14px' }}>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center' }}>
                    {row.pick != null ? (
                      <select
                        aria-label={t('wizard:v5.discAt', { one: 'Discipline at {{count}} dot', other: 'Discipline at {{count}} dots' }, { count: row.base })}
                        value={row.name}
                        onChange={(e) => {
                          // A new name starts with no powers, except the ones already typed on
                          // that Discipline's own (predator/XP) row, which this pick now absorbs.
                          const next = e.target.value;
                          const absorbed = discRows.find((r) => r.pick == null && r.name === next);
                          setDisc(row.pick, { name: next, powers: absorbed ? absorbed.powers : [] });
                        }}
                        style={{ ...inputStyle, flex: '1 1 200px', width: 'auto', padding: '8px' }}
                      >
                        <option value="">{t('wizard:v5.discAtPick', { one: 'Discipline at {{count}} dot…', other: 'Discipline at {{count}} dots…' }, { count: row.base })}</option>
                        {discOptions.map((o) => (
                          <option key={o} value={o}>
                            {o}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <strong style={{ flex: '1 1 200px', color: 'var(--sr-bone-100)', fontSize: '14px', padding: '8px 0' }}>{row.name}</strong>
                    )}
                    <SourceDots label={discLabel} row={row} />
                  </div>
                  {row.predator || row.xp ? (
                    <div style={{ color: 'var(--sr-gold-400)', fontSize: '12px', marginTop: '4px' }}>
                      {row.predator ? t('wizard:v5.predatorDotNote', '+1 from {{type}}', { type: predatorType }) : null}
                      {row.predator && row.xp ? ' · ' : null}
                      {row.xp ? t('wizard:v5.xpDotNote', '+{{n}} from XP', { n: row.xp }) : null}
                    </div>
                  ) : null}
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '6px' }}>
                    {row.powers.map((pw, p) => (
                      <input
                        key={p}
                        value={pw}
                        aria-label={t('wizard:v5.powerLabel', '{{disc}} power {{n}}', { disc: discLabel, n: p + 1 })}
                        placeholder={t('wizard:v5.powerPlaceholder', 'Power {{n}} (optional)', { n: p + 1 })}
                        onChange={(e) => setPower(p, e.target.value)}
                        style={{ ...inputStyle, flex: '1 1 180px', width: 'auto', padding: '6px 8px', fontSize: '12px' }}
                      />
                    ))}
                  </div>
                </div>
              );
            })}
            {startingRitualAllowed(sheet) ? (
              <div style={{ marginTop: '6px', maxWidth: '420px' }}>
                <label htmlFor="v5-field-starting-ritual" style={labelStyle}>
                  {t('wizard:v5.startingRitual', 'Starting ritual (Level 1)')}
                </label>
                <input
                  id="v5-field-starting-ritual"
                  value={startingRitual}
                  maxLength={V5_NAME_MAX}
                  onChange={(e) => setStartingRitual(e.target.value)}
                  placeholder={t('wizard:v5.startingRitualPlaceholder', 'optional: one Level 1 Blood Sorcery ritual')}
                  style={inputStyle}
                />
              </div>
            ) : null}
          </ResponsiveSheetBlock>

          <ResponsiveSheetBlock
            sectionId={V5_SECTION_IDS.predator}
            title={<Term id="predator" />}
            subtitle={t('wizard:v5.predatorSub', "How you hunt: a specialty, one Discipline dot, and the type's extras.")}
            accent={ACCENT}
          >
            {inlineErr(V5_SECTION_IDS.predator)}
            <label htmlFor="v5-field-predator" style={labelStyle}><Term id="predator" /></label>
            <select
              id="v5-field-predator"
              value={predatorType}
              onChange={(e) => {
                setPredatorType(e.target.value);
                setPredatorSpecialty(null);
                setPredatorDiscipline('');
                setExtraPowers({});
              }}
              style={{ ...inputStyle, maxWidth: '420px', marginBottom: '12px' }}
            >
              <option value="">{clan === THIN_BLOOD ? t('wizard:v5.predatorNone', 'None (optional for thin-bloods)') : t('wizard:v5.choose', 'Choose…')}</option>
              {V5_PREDATOR_TYPES.map((p) => (
                <option key={p.name} value={p.name} disabled={(p.forbidden_clans || []).includes(clan)}>
                  {p.name}
                  {(p.forbidden_clans || []).includes(clan) ? ` ${t('wizard:v5.notFor', '(not for {{clan}})', { clan })}` : ''}
                </option>
              ))}
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
                        checked={predatorSpecialty === i}
                        onChange={() => setPredatorSpecialty(i)}
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
                      value={predatorDiscipline}
                      onChange={(e) => setPredatorDiscipline(e.target.value)}
                      style={{ ...inputStyle, maxWidth: '300px', padding: '8px' }}
                    >
                      <option value="">{t('wizard:v5.choose', 'Choose…')}</option>
                      {predDiscOptions.map((o) => (
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
                  {(pred.flaws || []).map((f) => `${f.name} ${'●'.repeat(f.dots)}`).join(', ') || t('wizard:v5.noFlaws', 'no flaws')}
                  {pred.humanity ? ` · Humanity ${pred.humanity > 0 ? '+' : ''}${pred.humanity}` : ''}
                  {pred.blood_potency ? ` · Blood Potency +${pred.blood_potency}` : ''}
                </div>
              </div>
            ) : null}
          </ResponsiveSheetBlock>

          <ResponsiveSheetBlock
            sectionId={V5_SECTION_IDS.advantages}
            title="Advantages & Flaws"
            subtitle={t('wizard:v5.advantagesSub', 'Up to {{adv}} dots of Merits and Backgrounds (+ for advantages), at least {{flaws}} dots of Flaws (− for flaws). Predator extras are added on top; its Flaws count.', { adv: derived.advantage_dots, flaws: derived.flaw_min_dots })}
            accent={ACCENT}
          >
            {inlineErr(V5_SECTION_IDS.advantages)}
            <p style={{ color: advDots > derived.advantage_dots || flawDots < derived.flaw_min_dots ? 'var(--sr-blood-300)' : 'var(--sr-ok-400)', fontSize: '12px', margin: '0 0 10px' }}>
              {t('wizard:v5.advantagesCount', 'Advantages {{adv}}/{{advMax}} · Flaws {{flaws}} (min {{flawMin}})', { adv: advDots, advMax: derived.advantage_dots, flaws: flawDots, flawMin: derived.flaw_min_dots })}
            </p>
            <MeritFlawRows
              rows={meritRows}
              setRows={setMeritRows}
              globalNotes={meritNotes}
              setGlobalNotes={setMeritNotes}
            />
            {clan === THIN_BLOOD ? (
              <div style={{ marginTop: '16px', paddingTop: '12px', borderTop: '1px solid var(--sr-night-700)' }}>
                <p style={{ color: 'var(--sr-bone-300)', fontSize: '12px', margin: '0 0 10px', lineHeight: 1.5 }}>
                  {t('wizard:v5.thinHelp', "Thin-bloods also take {{lo}}–{{hi}} thin-blood Merits and the same number of thin-blood Flaws (core p. 182). They have no dot value and don't count toward the totals above. The rules file has no list of them, so write the names from the book.", { lo: V5_THIN_BLOOD_MERITS[0], hi: V5_THIN_BLOOD_MERITS[1] })}
                </p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px' }}>
                  {thinRows('Merits', thinBloodMerits, setThinBloodMerits)}
                  {thinRows('Flaws', thinBloodFlaws, setThinBloodFlaws)}
                </div>
              </div>
            ) : null}
          </ResponsiveSheetBlock>

          {xpTotal > 0 ? (
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
              {inlineErr(V5_SECTION_IDS.experience)}
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
                  onChange={(e) => setXpDraft({ kind: e.target.value, trait: '', skill: '', specialty: '', level: 1 })}
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
                        : xpDisciplineOptions(sheet, V5_DISCIPLINES).map((d) => [d, d, discRows.find((r) => r.name === d)?.level || 0])
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
                    <input
                      aria-label={t('wizard:v5.xpRitualName', 'Ritual name')}
                      value={draft.trait}
                      maxLength={V5_NAME_MAX}
                      onChange={(e) => setXpDraft({ ...draft, trait: e.target.value })}
                      style={{ ...inputStyle, flex: '2 1 200px', width: 'auto', padding: '8px' }}
                    />
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
                  style={{ padding: '8px 14px', fontSize: '12px', background: 'var(--sr-night-800)', color: 'var(--sr-arcane-300)', border: '1px solid var(--sr-arcane-700)', borderRadius: '6px', cursor: 'pointer' }}
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
          ) : null}

          <ResponsiveSheetBlock
            sectionId={V5_SECTION_IDS.humanity}
            title={t('wizard:v5.humanityTitle', 'Humanity & trackers')}
            subtitle={t('wizard:v5.humanitySub', '1–3 Convictions, each with a mortal Touchstone.')}
            accent={ACCENT}
          >
            {inlineErr(V5_SECTION_IDS.humanity)}
            <div style={{ ...gridStyle, gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', marginBottom: '16px', color: 'var(--sr-bone-100)', fontSize: '13px' }}>
              <div><Term id="health" /> <strong>{derived.health}</strong> <span style={{ color: 'var(--sr-bone-300)' }}>(Stamina + 3)</span></div>
              <div><Term id="willpower" /> <strong>{derived.willpower}</strong> <span style={{ color: 'var(--sr-bone-300)' }}>(Composure + Resolve)</span></div>
              <div><Term id="humanity" /> <strong>{derived.humanity}</strong></div>
              <div><Term id="hunger" /> <strong>{derived.hunger}</strong></div>
              <div>
                <Term id="bloodPotency" /> <strong>{derived.blood_potency}</strong>
                {derived.blood_potency_range ? (
                  <span style={{ color: 'var(--sr-bone-300)' }}> ({derived.blood_potency_range[0]}–{derived.blood_potency_range[1]})</span>
                ) : null}
              </div>
            </div>
            {fledglingHumanityAllowed(sheet) ? (
              <label
                htmlFor="v5-field-fledgling-humanity"
                style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--sr-bone-300)', fontSize: '13px', marginBottom: '14px', cursor: 'pointer' }}
              >
                <input
                  id="v5-field-fledgling-humanity"
                  type="checkbox"
                  checked={fledglingHumanity}
                  onChange={(e) => setFledglingHumanity(e.target.checked)}
                />
                {t('wizard:v5.fledgling', 'Just-Embraced fledgling: start at Humanity {{n}} instead of {{base}} (Storyteller option)', { n: V5_FLEDGLING_HUMANITY, base: V5_STARTING_HUMANITY })}
              </label>
            ) : null}
            {convictions.map((c, i) => (
              <div key={i} style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '8px' }}>
                <input
                  aria-label={t('wizard:v5.convictionN', 'Conviction {{n}}', { n: i + 1 })}
                  value={c.conviction}
                  placeholder={t('wizard:v5.convictionPlaceholder', 'Conviction (e.g. Never kill a child)')}
                  onChange={(e) =>
                    setConvictions((prev) => prev.map((x, j) => (j === i ? { ...x, conviction: e.target.value } : x)))
                  }
                  style={{ ...inputStyle, flex: '2 1 220px', width: 'auto', padding: '8px' }}
                />
                <input
                  aria-label={t('wizard:v5.touchstoneN', 'Touchstone {{n}}', { n: i + 1 })}
                  value={c.touchstone}
                  placeholder={t('wizard:v5.touchstonePlaceholder', 'Touchstone (a living mortal)')}
                  onChange={(e) =>
                    setConvictions((prev) => prev.map((x, j) => (j === i ? { ...x, touchstone: e.target.value } : x)))
                  }
                  style={{ ...inputStyle, flex: '2 1 220px', width: 'auto', padding: '8px' }}
                />
                {convictions.length > 1 ? (
                  <button
                    type="button"
                    onClick={() => setConvictions((prev) => prev.filter((_, j) => j !== i))}
                    aria-label={t('wizard:v5.removeConviction', 'Remove conviction {{n}}', { n: i + 1 })}
                    style={{ padding: '6px 10px', background: 'var(--sr-night-800)', color: 'var(--sr-bone-300)', border: '1px solid var(--sr-night-600)', borderRadius: '6px', cursor: 'pointer' }}
                  >
                    ×
                  </button>
                ) : null}
              </div>
            ))}
            {convictions.length < 3 ? (
              <button
                type="button"
                onClick={() => setConvictions((prev) => [...prev, { conviction: '', touchstone: '' }])}
                style={{ padding: '6px 12px', fontSize: '12px', background: 'transparent', color: 'var(--sr-arcane-300)', border: '1px dashed var(--sr-arcane-700)', borderRadius: '6px', cursor: 'pointer' }}
              >
                {t('wizard:v5.addConviction', '+ Add conviction')}
              </button>
            ) : null}
            <label htmlFor="v5-field-tenets" style={{ ...labelStyle, marginTop: '14px' }}>{t('wizard:v5.tenets', 'Chronicle tenets (from your Storyteller)')}</label>
            <textarea id="v5-field-tenets" value={tenets} onChange={(e) => setTenets(e.target.value)} rows={2} style={{ ...inputStyle, resize: 'vertical' }} />
          </ResponsiveSheetBlock>

          <ResponsiveSheetBlock sectionId={V5_SECTION_IDS.story} title={t('wizard:section.story', 'Story')} subtitle={t('wizard:v5.storySub', 'Background narrative.')} accent="var(--sr-arcane-500)">
            <textarea
              aria-label={t('wizard:v5.storySub', 'Background narrative.')}
              value={background}
              onChange={(e) => setBackground(e.target.value)}
              rows={6}
              placeholder={t('wizard:v5.storyPlaceholder', 'History, coterie, goals…')}
              style={{ ...inputStyle, resize: 'vertical', fontFamily: 'var(--sr-font-body)', lineHeight: 1.6 }}
            />
          </ResponsiveSheetBlock>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', marginTop: '24px', justifyContent: 'space-between' }}>
            <button
              type="button"
              onClick={onCancel}
              style={{ padding: '10px 18px', background: 'var(--sr-night-800)', color: 'var(--sr-bone-100)', border: '1px solid var(--sr-night-600)', borderRadius: '8px', cursor: 'pointer' }}
            >
              {t('wizard:cancel', 'Cancel')}
            </button>
            <button
              type="button"
              disabled={submitting}
              onClick={handleSubmit}
              style={{
                padding: '10px 22px',
                background: submitting ? 'var(--sr-night-500)' : 'var(--sr-arcane-500)',
                color: 'white',
                border: 'none',
                borderRadius: '8px',
                cursor: submitting ? 'not-allowed' : 'pointer',
                fontWeight: 'bold',
                fontFamily: 'var(--sr-font-display)',
              }}
            >
              {submitting ? t('wizard:submitting', 'Sealing sheet…') : t('wizard:submit', 'Create character')}
            </button>
          </div>
        </div>
      </GothicBox>
    </div>
  );
}
