import React, { useMemo, useState } from 'react';
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
  V5_STARTING_HUMANITY,
  V5_THIN_BLOOD_MERITS,
  toKey,
} from '../../characterSheet/v5/constants';
import {
  attributeSpreadStatus,
  buildV5Payload,
  clanInfo,
  creationDisciplineOptions,
  deriveV5,
  emptyV5Attributes,
  emptyV5Skills,
  fledglingHumanityAllowed,
  freeSpecialtyCount,
  predatorDisciplineOptions,
  predatorInfo,
  skillSpreadStatus,
  validateV5Sheet,
} from '../../characterSheet/v5/validation';
import { translateSheetErrors } from '../../characterSheet/i18nErrors';
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
    advantages,
    flaws,
    convictions,
    fledglingHumanity,
    thinBloodMerits,
    thinBloodFlaws,
  };
  const derived = deriveV5(sheet);
  const clanRow = clanInfo(clan);
  const pred = predatorInfo(predatorType);
  const discOptions = creationDisciplineOptions(clan, V5_DISCIPLINES);
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
      showSuccess?.(t('wizard:v5.created', 'Character embraced. Enter the chronicle to play.'));
      onDone?.(body, parseInt(campaignId, 10));
    } catch (e) {
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
            {SECTION_ORDER.map(([id, label]) => (
              <button
                key={id}
                type="button"
                onClick={() => scrollToSection(id)}
                style={{
                  fontSize: '11px',
                  padding: '6px 12px',
                  borderRadius: '999px',
                  background: fieldErrors[id] ? 'rgba(248,113,113,0.15)' : 'var(--sr-night-800)',
                  color: fieldErrors[id] ? 'var(--sr-blood-300)' : ACCENT,
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
            {clan !== THIN_BLOOD &&
              disciplines.map((d, i) => (
                <div key={i} style={{ marginBottom: '14px' }}>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center' }}>
                    <select
                      aria-label={t('wizard:v5.discAt', { one: 'Discipline at {{count}} dot', other: 'Discipline at {{count}} dots' }, { count: d.level })}
                      value={d.name}
                      onChange={(e) => setDisc(i, { name: e.target.value })}
                      style={{ ...inputStyle, flex: '1 1 200px', width: 'auto', padding: '8px' }}
                    >
                      <option value="">{t('wizard:v5.discAtPick', { one: 'Discipline at {{count}} dot…', other: 'Discipline at {{count}} dots…' }, { count: d.level })}</option>
                      {discOptions.map((o) => (
                        <option key={o} value={o}>
                          {o}
                        </option>
                      ))}
                    </select>
                    <DotTrack value={d.level} maxRank={5} accent={ACCENT} disabled onChange={() => {}} />
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '6px' }}>
                    {Array.from({ length: d.level }, (_, p) => (
                      <input
                        key={p}
                        value={d.powers[p] || ''}
                        aria-label={t('wizard:v5.powerLabel', '{{disc}} power {{n}}', { disc: d.name || `Discipline ${i + 1}`, n: p + 1 })}
                        placeholder={t('wizard:v5.powerPlaceholder', 'Power {{n}} (optional)', { n: p + 1 })}
                        onChange={(e) => {
                          const powers = [...d.powers];
                          powers[p] = e.target.value;
                          setDisc(i, { powers });
                        }}
                        style={{ ...inputStyle, flex: '1 1 180px', width: 'auto', padding: '6px 8px', fontSize: '12px' }}
                      />
                    ))}
                  </div>
                </div>
              ))}
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
