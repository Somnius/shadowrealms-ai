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

const API_URL = '/api';
const ACCENT = '#e94560';

const SECTION_ORDER = [
  [V5_SECTION_IDS.identity, 'Identity'],
  [V5_SECTION_IDS.clan, 'Clan'],
  [V5_SECTION_IDS.attributes, 'Attributes'],
  [V5_SECTION_IDS.skills, 'Skills'],
  [V5_SECTION_IDS.disciplines, 'Disciplines'],
  [V5_SECTION_IDS.predator, 'Predator'],
  [V5_SECTION_IDS.advantages, 'Advantages'],
  [V5_SECTION_IDS.humanity, 'Humanity'],
  [V5_SECTION_IDS.story, 'Story'],
];

const inputStyle = {
  width: '100%',
  padding: '10px',
  background: '#0f1729',
  color: '#e0e0e0',
  border: '2px solid #2a2a4e',
  borderRadius: '8px',
};
const labelStyle = { color: '#c4b5fd', display: 'block', marginBottom: '6px', fontSize: '13px' };
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
              color: ok ? '#86efac' : '#fca5a5',
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
    const err = validateV5Sheet(sheet, V5_DISCIPLINES);
    if (!campaignId) err[V5_SECTION_IDS.identity] = 'Choose a chronicle.';
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
      const res = await fetch(`${API_URL}/characters/`, {
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
        showError?.(body.error || 'Could not create character.');
        return;
      }
      showSuccess?.('Character embraced. Select them in Player Profile if needed.');
      onDone?.(body);
    } catch (e) {
      showError?.('Network error while creating character.');
    } finally {
      setSubmitting(false);
    }
  };

  const inlineErr = (id) =>
    fieldErrors[id] ? (
      <p style={{ color: '#f87171', fontSize: '13px', marginBottom: '12px' }}>{fieldErrors[id]}</p>
    ) : null;

  const textField = (label, value, setter, placeholder) => {
    const id = `v5-field-${toKey(label)}`;
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
              placeholder={kind === 'Merits' ? 'e.g. Day Drinker' : 'e.g. Baby Teeth'}
              onChange={(e) =>
                setRows((prev) => prev.map((x, j) => (j === i ? { name: e.target.value } : x)))
              }
              style={{ ...inputStyle, flex: '1 1 auto', width: 'auto', padding: '8px' }}
            />
            {rows.length > 1 ? (
              <button
                type="button"
                aria-label={`Remove thin-blood ${kind.replace(/s$/, '')} ${i + 1}`}
                onClick={() => setRows((prev) => prev.filter((_, j) => j !== i))}
                style={{ padding: '6px 10px', background: '#1e293b', color: '#94a3b8', border: '1px solid #475569', borderRadius: '6px', cursor: 'pointer' }}
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
            style={{ padding: '6px 12px', fontSize: '12px', background: 'transparent', color: '#c4b5fd', border: '1px dashed #6d28d9', borderRadius: '6px', cursor: 'pointer' }}
          >
            + Add {kind === 'Merits' ? 'Merit' : 'Flaw'}
          </button>
        ) : null}
      </div>
    );
  };

  return (
    <div style={{ maxWidth: '1040px', margin: '0 auto', padding: '20px 16px 60px' }}>
      <GothicBox theme="vampire">
        <div style={{ padding: '8px 8px 0' }}>
          <h2 style={{ fontFamily: 'Cinzel, serif', color: ACCENT, marginTop: 0, fontSize: '22px' }}>
            Character sheet forge · V5
          </h2>
          <p style={{ color: '#8b8b9f', fontSize: '14px', lineHeight: 1.5 }}>
            <strong>Vampire: The Masquerade 5th Edition</strong> creation: fixed attribute spread,
            a skill distribution, 2 + 1 Discipline dots, a predator type, 7 Advantage dots and at
            least 2 Flaw dots. No freebie points in V5.
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
            borderBottom: '1px solid #2a2a4e',
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
                  background: fieldErrors[id] ? 'rgba(248,113,113,0.15)' : '#1e293b',
                  color: fieldErrors[id] ? '#fca5a5' : ACCENT,
                  border: `1px solid ${fieldErrors[id] ? '#b91c1c' : '#334155'}`,
                  cursor: 'pointer',
                  fontFamily: 'Cinzel, serif',
                }}
              >
                {label}
              </button>
            ))}
          </div>
          <div style={{ marginTop: '10px', display: 'flex', flexWrap: 'wrap', gap: '12px', fontSize: '12px', color: '#b5b5c3' }}>
            <span>
              <strong style={{ color: '#e8e8ef' }}>{name || '—'}</strong>
              {concept ? ` · ${concept}` : ''}
            </span>
            <span style={{ color: ACCENT }}>{clan}</span>
            <span>
              Health {derived.health} · Willpower {derived.willpower} · Humanity {derived.humanity} · BP{' '}
              {derived.blood_potency} · Hunger {derived.hunger}
            </span>
          </div>
        </div>

        <div style={{ padding: '8px 16px 24px' }}>
          <ResponsiveSheetBlock sectionId={V5_SECTION_IDS.identity} title="Identity" subtitle="Chronicle and concept" accent={ACCENT}>
            {inlineErr(V5_SECTION_IDS.identity)}
            <label htmlFor="v5-field-chronicle" style={labelStyle}>Chronicle</label>
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
              {textField('Character name', name, setName)}
              {textField('Concept', concept, setConcept, 'e.g. burned-out paramedic')}
              {textField('Sire', sire, setSire, 'optional')}
              {textField('Ambition', ambition, setAmbition, 'long-term goal')}
              {textField('Desire', desire, setDesire, 'this session')}
            </div>
          </ResponsiveSheetBlock>

          <ResponsiveSheetBlock
            sectionId={V5_SECTION_IDS.clan}
            title="Clan & generation"
            subtitle="Age sets the generation range and starting Blood Potency."
            accent={ACCENT}
          >
            {inlineErr(V5_SECTION_IDS.clan)}
            <div style={gridStyle}>
              <div>
                <label htmlFor="v5-field-clan" style={labelStyle}>Clan</label>
                <select id="v5-field-clan" value={clan} onChange={(e) => changeClan(e.target.value)} style={inputStyle}>
                  {V5_CLAN_NAMES.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor="v5-field-age" style={labelStyle}>Age</label>
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
                <label htmlFor="v5-field-generation" style={labelStyle}>Generation</label>
                <select
                  id="v5-field-generation"
                  value={generation}
                  onChange={(e) => setGeneration(parseInt(e.target.value, 10))}
                  style={inputStyle}
                >
                  {V5_AGE_BRACKETS[age].generations.map((g) => (
                    <option key={g} value={g}>
                      {g}th{g >= 14 ? ' (thin-blood)' : ''}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            {clanRow ? (
              <p style={{ color: '#94a3b8', fontSize: '13px', marginTop: '12px', lineHeight: 1.5 }}>
                {clanRow.disciplines.length ? (
                  <>
                    <strong style={{ color: '#c4b5fd' }}>Disciplines:</strong> {clanRow.disciplines.join(', ')}.{' '}
                  </>
                ) : null}
                {clanRow.bane_summary ? (
                  <>
                    <strong style={{ color: '#c4b5fd' }}>Bane:</strong> {clanRow.bane_summary}.{' '}
                  </>
                ) : null}
                {clanRow.compulsion ? (
                  <>
                    <strong style={{ color: '#c4b5fd' }}>Compulsion:</strong> {clanRow.compulsion}.
                  </>
                ) : null}
              </p>
            ) : null}
          </ResponsiveSheetBlock>

          <ResponsiveSheetBlock
            sectionId={V5_SECTION_IDS.attributes}
            title="Attributes"
            subtitle="One at 4, three at 3, four at 2, one at 1."
            accent={ACCENT}
          >
            {inlineErr(V5_SECTION_IDS.attributes)}
            <SpreadChips status={attrStatus} />
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '18px' }}>
              {['physical', 'social', 'mental'].map((cat) => (
                <div key={cat} style={{ flex: '1 1 200px', minWidth: 0 }}>
                  <div style={{ textAlign: 'center', fontFamily: 'Cinzel, serif', fontSize: '12px', color: ACCENT, marginBottom: '10px', textTransform: 'capitalize' }}>
                    {cat}
                  </div>
                  {V5_ATTRIBUTES[cat].map(([k, label]) => (
                    <div key={k} style={rowStyle}>
                      <span style={{ color: '#d1d5db', fontSize: '13px' }}>{label}</span>
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
            title="Skills"
            subtitle="Pick a distribution, then free specialties."
            accent={ACCENT}
          >
            {inlineErr(V5_SECTION_IDS.skills)}
            <label htmlFor="v5-field-distribution" style={labelStyle}>Distribution</label>
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
                  <div style={{ textAlign: 'center', fontFamily: 'Cinzel, serif', fontSize: '12px', color: ACCENT, marginBottom: '10px', textTransform: 'capitalize' }}>
                    {cat}
                  </div>
                  {V5_SKILLS[cat].map(([k, label]) => (
                    <div key={k} style={rowStyle}>
                      <span style={{ color: '#c4c4d4', fontSize: '12px' }}>{label}</span>
                      <DotTrack
                        label={label}
                        value={skills[k]}
                        maxRank={skillMax}
                        accent="#fbbf24"
                        onChange={(n) => setSkills((prev) => ({ ...prev, [k]: n }))}
                      />
                    </div>
                  ))}
                </div>
              ))}
            </div>
            <div style={{ marginTop: '16px' }}>
              <div style={{ color: '#94a3b8', fontSize: '12px', marginBottom: '8px' }}>
                Specialties: {freeSpecialtyCount(skills)} free (one each for rated Academics, Craft,
                Performance, Science, plus one of your choice). The predator type adds one more below.
              </div>
              {specialties.map((sp, i) => (
                <div key={i} style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '8px' }}>
                  <select
                    aria-label={`Specialty ${i + 1} skill`}
                    value={sp.skill}
                    onChange={(e) =>
                      setSpecialties((prev) => prev.map((x, j) => (j === i ? { ...x, skill: e.target.value } : x)))
                    }
                    style={{ ...inputStyle, flex: '1 1 160px', width: 'auto', padding: '8px' }}
                  >
                    <option value="">Skill…</option>
                    {V5_SKILL_KEYS.filter((k) => skills[k] > 0).map((k) => (
                      <option key={k} value={k}>
                        {V5_SKILL_LABELS[k]}
                      </option>
                    ))}
                  </select>
                  <input
                    aria-label={`Specialty ${i + 1} name`}
                    value={sp.name}
                    placeholder="Specialty (e.g. Grappling)"
                    onChange={(e) =>
                      setSpecialties((prev) => prev.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))
                    }
                    style={{ ...inputStyle, flex: '2 1 200px', width: 'auto', padding: '8px' }}
                  />
                  <button
                    type="button"
                    onClick={() => setSpecialties((prev) => prev.filter((_, j) => j !== i))}
                    style={{ padding: '6px 10px', background: '#1e293b', color: '#94a3b8', border: '1px solid #475569', borderRadius: '6px', cursor: 'pointer' }}
                  >
                    ×
                  </button>
                </div>
              ))}
              {specialties.length < freeSpecialtyCount(skills) ? (
                <button
                  type="button"
                  onClick={() => setSpecialties((prev) => [...prev, { skill: '', name: '' }])}
                  style={{ padding: '6px 12px', fontSize: '12px', background: 'transparent', color: '#c4b5fd', border: '1px dashed #6d28d9', borderRadius: '6px', cursor: 'pointer' }}
                >
                  + Add specialty
                </button>
              ) : null}
            </div>
          </ResponsiveSheetBlock>

          <ResponsiveSheetBlock
            sectionId={V5_SECTION_IDS.disciplines}
            title="Disciplines"
            subtitle={
              clan === THIN_BLOOD
                ? 'Thin-bloods start with no Disciplines.'
                : clan === CAITIFF
                  ? 'Any two Disciplines: one at 2 dots, one at 1. One power per dot.'
                  : 'Two clan Disciplines: one at 2 dots, one at 1. One power per dot.'
            }
            accent={ACCENT}
          >
            {inlineErr(V5_SECTION_IDS.disciplines)}
            {clan !== THIN_BLOOD &&
              disciplines.map((d, i) => (
                <div key={i} style={{ marginBottom: '14px' }}>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center' }}>
                    <select
                      aria-label={`Discipline at ${d.level} ${d.level === 1 ? 'dot' : 'dots'}`}
                      value={d.name}
                      onChange={(e) => setDisc(i, { name: e.target.value })}
                      style={{ ...inputStyle, flex: '1 1 200px', width: 'auto', padding: '8px' }}
                    >
                      <option value="">Discipline at {d.level} {d.level === 1 ? 'dot' : 'dots'}…</option>
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
                        aria-label={`${d.name || `Discipline ${i + 1}`} power ${p + 1}`}
                        placeholder={`Power ${p + 1} (optional)`}
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
            title="Predator type"
            subtitle="How you hunt: a specialty, one Discipline dot, and the type's extras."
            accent={ACCENT}
          >
            {inlineErr(V5_SECTION_IDS.predator)}
            <label htmlFor="v5-field-predator" style={labelStyle}>Predator type</label>
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
              <option value="">{clan === THIN_BLOOD ? 'None (optional for thin-bloods)' : 'Choose…'}</option>
              {V5_PREDATOR_TYPES.map((p) => (
                <option key={p.name} value={p.name} disabled={(p.forbidden_clans || []).includes(clan)}>
                  {p.name}
                  {(p.forbidden_clans || []).includes(clan) ? ` (not for ${clan})` : ''}
                </option>
              ))}
            </select>
            {pred ? (
              <div style={{ color: '#cbd5e1', fontSize: '13px', display: 'grid', gap: '10px' }}>
                <div style={{ color: '#94a3b8' }}>Hunting pool: {pred.pool}</div>
                <div role="radiogroup" aria-labelledby="v5-predator-specialty-label">
                  <span id="v5-predator-specialty-label" style={labelStyle}>Specialty</span>
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
                    <label htmlFor="v5-field-predator-discipline" style={labelStyle}>Discipline dot</label>
                    <select
                      id="v5-field-predator-discipline"
                      value={predatorDiscipline}
                      onChange={(e) => setPredatorDiscipline(e.target.value)}
                      style={{ ...inputStyle, maxWidth: '300px', padding: '8px' }}
                    >
                      <option value="">Choose…</option>
                      {predDiscOptions.map((o) => (
                        <option key={o} value={o}>
                          {o}
                        </option>
                      ))}
                    </select>
                  </div>
                ) : null}
                <div style={{ color: '#94a3b8' }}>
                  {(pred.advantages || []).map((a) => `${a.name} ${'●'.repeat(a.dots)}`).join(', ') || 'No advantages'}
                  {' · '}
                  {(pred.flaws || []).map((f) => `${f.name} ${'●'.repeat(f.dots)}`).join(', ') || 'no flaws'}
                  {pred.humanity ? ` · Humanity ${pred.humanity > 0 ? '+' : ''}${pred.humanity}` : ''}
                  {pred.blood_potency ? ` · Blood Potency +${pred.blood_potency}` : ''}
                </div>
              </div>
            ) : null}
          </ResponsiveSheetBlock>

          <ResponsiveSheetBlock
            sectionId={V5_SECTION_IDS.advantages}
            title="Advantages & flaws"
            subtitle={`Up to ${derived.advantage_dots} dots of Merits and Backgrounds (+ for advantages), at least ${derived.flaw_min_dots} dots of Flaws (− for flaws). Predator extras are added on top; its Flaws count.`}
            accent={ACCENT}
          >
            {inlineErr(V5_SECTION_IDS.advantages)}
            <p style={{ color: advDots > derived.advantage_dots || flawDots < derived.flaw_min_dots ? '#fca5a5' : '#86efac', fontSize: '12px', margin: '0 0 10px' }}>
              Advantages {advDots}/{derived.advantage_dots} · Flaws {flawDots} (min {derived.flaw_min_dots})
            </p>
            <MeritFlawRows
              rows={meritRows}
              setRows={setMeritRows}
              globalNotes={meritNotes}
              setGlobalNotes={setMeritNotes}
            />
            {clan === THIN_BLOOD ? (
              <div style={{ marginTop: '16px', paddingTop: '12px', borderTop: '1px solid #2a2a4e' }}>
                <p style={{ color: '#94a3b8', fontSize: '12px', margin: '0 0 10px', lineHeight: 1.5 }}>
                  Thin-bloods also take {V5_THIN_BLOOD_MERITS[0]}–{V5_THIN_BLOOD_MERITS[1]} thin-blood
                  Merits and the same number of thin-blood Flaws (core p. 182). They have no dot value
                  and don't count toward the totals above. The rules file has no list of them, so
                  write the names from the book.
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
            title="Humanity & trackers"
            subtitle="1–3 Convictions, each with a mortal Touchstone."
            accent={ACCENT}
          >
            {inlineErr(V5_SECTION_IDS.humanity)}
            <div style={{ ...gridStyle, gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', marginBottom: '16px', color: '#e2e8f0', fontSize: '13px' }}>
              <div>Health <strong>{derived.health}</strong> <span style={{ color: '#94a3b8' }}>(Stamina + 3)</span></div>
              <div>Willpower <strong>{derived.willpower}</strong> <span style={{ color: '#94a3b8' }}>(Composure + Resolve)</span></div>
              <div>Humanity <strong>{derived.humanity}</strong></div>
              <div>Hunger <strong>{derived.hunger}</strong></div>
              <div>
                Blood Potency <strong>{derived.blood_potency}</strong>
                {derived.blood_potency_range ? (
                  <span style={{ color: '#94a3b8' }}> ({derived.blood_potency_range[0]}–{derived.blood_potency_range[1]})</span>
                ) : null}
              </div>
            </div>
            {fledglingHumanityAllowed(sheet) ? (
              <label
                htmlFor="v5-field-fledgling-humanity"
                style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#cbd5e1', fontSize: '13px', marginBottom: '14px', cursor: 'pointer' }}
              >
                <input
                  id="v5-field-fledgling-humanity"
                  type="checkbox"
                  checked={fledglingHumanity}
                  onChange={(e) => setFledglingHumanity(e.target.checked)}
                />
                Just-Embraced fledgling: start at Humanity {V5_FLEDGLING_HUMANITY} instead of{' '}
                {V5_STARTING_HUMANITY} (Storyteller option)
              </label>
            ) : null}
            {convictions.map((c, i) => (
              <div key={i} style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '8px' }}>
                <input
                  aria-label={`Conviction ${i + 1}`}
                  value={c.conviction}
                  placeholder="Conviction (e.g. Never kill a child)"
                  onChange={(e) =>
                    setConvictions((prev) => prev.map((x, j) => (j === i ? { ...x, conviction: e.target.value } : x)))
                  }
                  style={{ ...inputStyle, flex: '2 1 220px', width: 'auto', padding: '8px' }}
                />
                <input
                  aria-label={`Touchstone ${i + 1}`}
                  value={c.touchstone}
                  placeholder="Touchstone (a living mortal)"
                  onChange={(e) =>
                    setConvictions((prev) => prev.map((x, j) => (j === i ? { ...x, touchstone: e.target.value } : x)))
                  }
                  style={{ ...inputStyle, flex: '2 1 220px', width: 'auto', padding: '8px' }}
                />
                {convictions.length > 1 ? (
                  <button
                    type="button"
                    onClick={() => setConvictions((prev) => prev.filter((_, j) => j !== i))}
                    style={{ padding: '6px 10px', background: '#1e293b', color: '#94a3b8', border: '1px solid #475569', borderRadius: '6px', cursor: 'pointer' }}
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
                style={{ padding: '6px 12px', fontSize: '12px', background: 'transparent', color: '#c4b5fd', border: '1px dashed #6d28d9', borderRadius: '6px', cursor: 'pointer' }}
              >
                + Add conviction
              </button>
            ) : null}
            <label htmlFor="v5-field-tenets" style={{ ...labelStyle, marginTop: '14px' }}>Chronicle tenets (from your Storyteller)</label>
            <textarea id="v5-field-tenets" value={tenets} onChange={(e) => setTenets(e.target.value)} rows={2} style={{ ...inputStyle, resize: 'vertical' }} />
          </ResponsiveSheetBlock>

          <ResponsiveSheetBlock sectionId={V5_SECTION_IDS.story} title="Story" subtitle="Background narrative." accent="#9d4edd">
            <textarea
              aria-label="Background narrative"
              value={background}
              onChange={(e) => setBackground(e.target.value)}
              rows={6}
              placeholder="History, coterie, goals…"
              style={{ ...inputStyle, resize: 'vertical', fontFamily: 'Crimson Text, Georgia, serif', lineHeight: 1.6 }}
            />
          </ResponsiveSheetBlock>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', marginTop: '24px', justifyContent: 'space-between' }}>
            <button
              type="button"
              onClick={onCancel}
              style={{ padding: '10px 18px', background: '#1e293b', color: '#e2e8f0', border: '1px solid #475569', borderRadius: '8px', cursor: 'pointer' }}
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={submitting}
              onClick={handleSubmit}
              style={{
                padding: '10px 22px',
                background: submitting ? '#4a4a5e' : '#9d4edd',
                color: 'white',
                border: 'none',
                borderRadius: '8px',
                cursor: submitting ? 'not-allowed' : 'pointer',
                fontWeight: 'bold',
                fontFamily: 'Cinzel, serif',
              }}
            >
              {submitting ? 'Sealing sheet…' : 'Create character'}
            </button>
          </div>
        </div>
      </GothicBox>
    </div>
  );
}
