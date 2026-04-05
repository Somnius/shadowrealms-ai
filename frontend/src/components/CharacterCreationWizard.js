import React, { useMemo, useState } from 'react';
import { GothicBox } from './GothicDecorations';
import DotTrack from './characterCreation/DotTrack';
import SheetSection from './characterCreation/SheetSection';
import PoolSummary from './characterCreation/PoolSummary';
import AttributeColumns from './characterCreation/AttributeColumns';
import AbilityColumns from './characterCreation/AbilityColumns';
import MeritFlawRows from './characterCreation/MeritFlawRows';
import ResponsiveSheetBlock from './characterCreation/ResponsiveSheetBlock';
import {
  ARCHETYPE_CUSTOM,
  DISCIPLINE_PRESETS,
  KNOWLEDGES,
  MTA_SPHERES,
  MTA_TRADITIONS,
  SHEET_SECTION_IDS,
  SKILLS,
  TALENTS,
  VAMPIRE_CLANS,
  WOD_ARCHETYPES,
  WTA_AUSPICES,
  WTA_BREEDS,
  WTA_TRIBES,
} from '../characterSheet/constants';
import { buildMeritsFlawsPayload, createEmptyMeritRow } from '../characterSheet/meritsFlaws';
import {
  emptyAbilityMap,
  emptyAttrMap,
  emptySphereMap,
  validateAbilitySpread,
  validateAttributeSpread,
  validateSpheres,
  validateVirtues,
} from '../characterSheet/validation';

const API_URL = '/api';

const SECTION_ORDER = [
  { id: SHEET_SECTION_IDS.identity, label: 'Identity' },
  { id: SHEET_SECTION_IDS.template, label: 'Template' },
  { id: SHEET_SECTION_IDS.nature, label: 'Nature' },
  { id: SHEET_SECTION_IDS.attributes, label: 'Attributes' },
  { id: SHEET_SECTION_IDS.abilities, label: 'Abilities' },
  { id: SHEET_SECTION_IDS.advantages, label: 'Advantages' },
  { id: SHEET_SECTION_IDS.story, label: 'Story' },
];

function scrollToSection(sectionDomId) {
  const el = typeof document !== 'undefined' ? document.getElementById(sectionDomId) : null;
  el?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function buildCustomSkillsPayload(customAbilities) {
  const out = {};
  for (const cat of ['talents', 'skills', 'knowledges']) {
    const rows = (customAbilities[cat] || []).filter((r) => String(r.label || '').trim());
    if (rows.length) {
      out[cat] = rows.map((r) => ({
        key: `custom_${cat}_${r.id}`,
        label: String(r.label).trim(),
        dots: Math.min(5, Math.max(0, parseInt(r.dots, 10) || 0)),
      }));
    }
  }
  return Object.keys(out).length ? out : null;
}

/**
 * Single-page oWoD character forge: scrollable sheet, section nav, pool summaries, structured merits.
 */
export default function CharacterCreationWizard({
  token,
  campaigns,
  onDone,
  onCancel,
  showError,
  showSuccess,
}) {
  const eligible = useMemo(
    () =>
      (campaigns || []).filter((c) =>
        ['vampire', 'werewolf', 'mage'].includes(String(c.game_system || '').toLowerCase())
      ),
    [campaigns]
  );

  const [campaignId, setCampaignId] = useState(
    eligible[0]?.id != null ? String(eligible[0].id) : ''
  );
  const [name, setName] = useState('');
  const [concept, setConcept] = useState('');
  const [priority, setPriority] = useState('physical');
  const [attrs, setAttrs] = useState(() => emptyAttrMap());
  const [abilityPriority, setAbilityPriority] = useState('talents');
  const [abilities, setAbilities] = useState(() => emptyAbilityMap());
  const [customAbilities, setCustomAbilities] = useState({
    talents: [],
    skills: [],
    knowledges: [],
  });
  const [background, setBackground] = useState('');
  const [meritRows, setMeritRows] = useState(() => [createEmptyMeritRow()]);
  const [meritsGlobalNotes, setMeritsGlobalNotes] = useState('');

  const [clan, setClan] = useState(VAMPIRE_CLANS[0]);
  const [naturePick, setNaturePick] = useState(WOD_ARCHETYPES[0]);
  const [natureCustom, setNatureCustom] = useState('');
  const [demeanorPick, setDemeanorPick] = useState(WOD_ARCHETYPES[0]);
  const [demeanorCustom, setDemeanorCustom] = useState('');
  const [generation, setGeneration] = useState('13');
  const [humanity, setHumanity] = useState('7');
  const [willpowerVampire, setWillpowerVampire] = useState('5');
  const [virtues, setVirtues] = useState({ conscience: '3', self_control: '3', courage: '1' });
  const [disciplines, setDisciplines] = useState([
    { name: '', dots: 0 },
    { name: '', dots: 0 },
    { name: '', dots: 0 },
  ]);
  const [backgrounds, setBackgrounds] = useState([
    { name: '', dots: 0 },
    { name: '', dots: 0 },
    { name: '', dots: 0 },
    { name: '', dots: 0 },
    { name: '', dots: 0 },
  ]);

  const [breed, setBreed] = useState(WTA_BREEDS[0]);
  const [auspice, setAuspice] = useState(WTA_AUSPICES[0]);
  const [tribe, setTribe] = useState(WTA_TRIBES[0]);
  const [werewolfRage, setWerewolfRage] = useState('1');
  const [werewolfGnosis, setWerewolfGnosis] = useState('1');
  const [giftsNotes, setGiftsNotes] = useState('');

  const [tradition, setTradition] = useState(MTA_TRADITIONS[0]);
  const [spheres, setSpheres] = useState(() => emptySphereMap());

  const [submitting, setSubmitting] = useState(false);
  const [fieldErrors, setFieldErrors] = useState({});

  const campaign = eligible.find((c) => String(c.id) === String(campaignId));
  const gs = String(campaign?.game_system || '').toLowerCase();
  const systemType = gs;

  const pools = useMemo(() => {
    if (priority === 'physical') {
      return { physical: 7, social: 5, mental: 3 };
    }
    if (priority === 'social') {
      return { physical: 5, social: 7, mental: 3 };
    }
    return { physical: 3, social: 5, mental: 7 };
  }, [priority]);

  const abilityPools = useMemo(() => {
    if (abilityPriority === 'talents') return { talents: 11, skills: 7, knowledges: 4 };
    if (abilityPriority === 'skills') return { talents: 7, skills: 11, knowledges: 4 };
    return { talents: 4, skills: 7, knowledges: 11 };
  }, [abilityPriority]);

  const themeAccent =
    systemType === 'werewolf' ? '#4ade80' : systemType === 'mage' ? '#38bdf8' : '#e94560';

  const resolveNatureDemeanor = (pick, custom) => {
    const t = (custom || '').trim();
    if (pick === ARCHETYPE_CUSTOM) return t;
    return t ? `${pick} (${t})` : pick;
  };

  const wodMeta = () => {
    const base = {
      concept: concept.trim(),
      nature: resolveNatureDemeanor(naturePick, natureCustom),
      demeanor: resolveNatureDemeanor(demeanorPick, demeanorCustom),
    };
    if (systemType === 'vampire') {
      const discClean = disciplines
        .filter((d) => d.name && String(d.name).trim())
        .map((d) => ({
          name: String(d.name).trim(),
          dots: Math.min(5, Math.max(0, parseInt(d.dots, 10) || 0)),
        }));
      const bgClean = backgrounds
        .filter((b) => b.name && String(b.name).trim())
        .map((b) => ({
          name: String(b.name).trim(),
          dots: Math.min(5, Math.max(0, parseInt(b.dots, 10) || 0)),
        }));
      return {
        ...base,
        clan,
        generation,
        humanity: parseInt(humanity, 10) || 7,
        willpower: parseInt(willpowerVampire, 10) || 5,
        virtues: {
          conscience: parseInt(virtues.conscience, 10) || 0,
          self_control: parseInt(virtues.self_control, 10) || 0,
          courage: parseInt(virtues.courage, 10) || 0,
        },
        disciplines: discClean,
        backgrounds: bgClean,
      };
    }
    if (systemType === 'werewolf') {
      return {
        ...base,
        breed,
        auspice,
        tribe,
        rage: Math.max(0, parseInt(werewolfRage, 10) || 0),
        gnosis: Math.max(0, parseInt(werewolfGnosis, 10) || 0),
        gifts_notes: giftsNotes.trim(),
      };
    }
    if (systemType === 'mage') {
      const sp = {};
      MTA_SPHERES.forEach(([k]) => {
        sp[k] = parseInt(spheres[k], 10) || 0;
      });
      return { ...base, tradition, arete: 1, spheres: sp };
    }
    return base;
  };

  const runValidation = () => {
    const err = {};
    if (!campaign) err[SHEET_SECTION_IDS.identity] = 'Choose a chronicle.';
    const cidNum = parseInt(campaignId, 10);
    if (!Number.isFinite(cidNum) || cidNum < 1) {
      err[SHEET_SECTION_IDS.identity] = 'Choose a valid chronicle.';
    }
    if (!name.trim()) err[SHEET_SECTION_IDS.identity] = 'Character name is required.';

    if (['vampire', 'werewolf', 'mage'].includes(systemType)) {
      const natureMsgs = [];
      if (naturePick === ARCHETYPE_CUSTOM && !(natureCustom || '').trim()) {
        natureMsgs.push('Enter your Nature (free text), or pick a preset archetype.');
      }
      if (demeanorPick === ARCHETYPE_CUSTOM && !(demeanorCustom || '').trim()) {
        natureMsgs.push('Enter your Demeanor (free text), or pick a preset archetype.');
      }
      if (natureMsgs.length) err[SHEET_SECTION_IDS.nature] = natureMsgs.join(' ');
    }

    const errA = validateAttributeSpread(attrs, pools);
    if (errA) err[SHEET_SECTION_IDS.attributes] = errA;

    const errAb = validateAbilitySpread(abilities, abilityPools, customAbilities);
    if (errAb) err[SHEET_SECTION_IDS.abilities] = errAb;

    if (systemType === 'vampire') {
      const advMsgs = [];
      const vErr = validateVirtues(virtues);
      if (vErr) advMsgs.push(vErr);
      const dSum = disciplines.reduce((s, d) => s + (parseInt(d.dots, 10) || 0), 0);
      if (dSum > 3) {
        advMsgs.push(
          'Discipline dots at creation are usually 3 total for a neonate — lower some ratings or clear extras.'
        );
      }
      const bgSum = backgrounds.reduce((s, b) => s + (parseInt(b.dots, 10) || 0), 0);
      if (bgSum > 5) {
        advMsgs.push(
          'Background dots total more than 5 (typical starting pool). Adjust before sealing the sheet.'
        );
      }
      if (advMsgs.length) err[SHEET_SECTION_IDS.advantages] = advMsgs.join(' ');
    }

    if (systemType === 'mage') {
      const sErr = validateSpheres(spheres);
      if (sErr) err[SHEET_SECTION_IDS.advantages] = sErr;
    }

    return err;
  };

  const handleSubmit = async () => {
    const err = runValidation();
    setFieldErrors(err);
    const firstKey = SECTION_ORDER.find((s) => err[s.id])?.id;
    if (firstKey) {
      showError?.(err[firstKey]);
      scrollToSection(firstKey);
      return;
    }

    const skillsPayload = {
      talents: Object.fromEntries(TALENTS.map(([k]) => [k, parseInt(abilities[k], 10) || 0])),
      skills: Object.fromEntries(SKILLS.map(([k]) => [k, parseInt(abilities[k], 10) || 0])),
      knowledges: Object.fromEntries(
        KNOWLEDGES.map(([k]) => [k, parseInt(abilities[k], 10) || 0])
      ),
      allocation: {
        primary: abilityPriority,
        pools: abilityPools,
      },
      notes: '',
    };
    const customPart = buildCustomSkillsPayload(customAbilities);
    if (customPart) skillsPayload.custom = customPart;

    const meritsPayload = buildMeritsFlawsPayload(meritRows, meritsGlobalNotes);

    const nm = name.trim();
    const cidNum = parseInt(campaignId, 10);

    setSubmitting(true);
    try {
      const res = await fetch(`${API_URL}/characters/`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: nm,
          campaign_id: cidNum,
          system_type: systemType,
          attributes: attrs,
          skills: skillsPayload,
          background: background.trim(),
          merits_flaws: meritsPayload,
          wod_meta: wodMeta(),
          sheet_locked: true,
          is_active: true,
        }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        showError?.(body.error || 'Could not create character.');
        return;
      }
      showSuccess?.('Character forged. Select them in Player Profile if needed.');
      onDone?.(body);
    } catch (e) {
      showError?.('Network error while creating character.');
    } finally {
      setSubmitting(false);
    }
  };

  const inlineErr = (sectionId) =>
    fieldErrors[sectionId] ? (
      <p style={{ color: '#f87171', fontSize: '13px', marginBottom: '12px' }}>{fieldErrors[sectionId]}</p>
    ) : null;

  if (!eligible.length) {
    return (
      <GothicBox theme="vampire" style={{ padding: '24px', maxWidth: '560px', margin: '0 auto' }}>
        <p style={{ color: '#b5b5c3' }}>
          You need to be a member of at least one Vampire, Werewolf, or Mage chronicle before
          using this forge.
        </p>
        <button
          type="button"
          onClick={onCancel}
          style={{
            marginTop: '16px',
            padding: '10px 20px',
            background: '#2a2a4e',
            color: '#e0e0e0',
            border: '1px solid #9d4edd',
            borderRadius: '8px',
            cursor: 'pointer',
          }}
        >
          Back
        </button>
      </GothicBox>
    );
  }

  return (
    <div style={{ maxWidth: '1040px', margin: '0 auto', padding: '20px 16px 60px' }}>
      <GothicBox
        theme={systemType === 'werewolf' ? 'werewolf' : systemType === 'mage' ? 'mage' : 'vampire'}
      >
        <div style={{ padding: '8px 8px 0' }}>
          <h2
            style={{
              fontFamily: 'Cinzel, serif',
              color: themeAccent,
              marginTop: 0,
              fontSize: '22px',
            }}
          >
            Character sheet forge
          </h2>
          <p style={{ color: '#8b8b9f', fontSize: '14px', lineHeight: 1.5 }}>
            Build a <strong>Classic World of Darkness</strong>–style sheet with dot pools and
            three-column abilities (Revised-era style). Scroll the sheet in order, or jump with the
            nav. Your Storyteller has final say on numbers and templates.
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
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center' }}>
            {SECTION_ORDER.map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => scrollToSection(s.id)}
                style={{
                  fontSize: '11px',
                  padding: '6px 12px',
                  borderRadius: '999px',
                  background: fieldErrors[s.id] ? 'rgba(248,113,113,0.15)' : '#1e293b',
                  color: fieldErrors[s.id] ? '#fca5a5' : themeAccent,
                  border: `1px solid ${fieldErrors[s.id] ? '#b91c1c' : '#334155'}`,
                  cursor: 'pointer',
                  fontFamily: 'Cinzel, serif',
                }}
              >
                {s.label}
              </button>
            ))}
          </div>
          <div
            style={{
              marginTop: '10px',
              display: 'flex',
              flexWrap: 'wrap',
              gap: '12px',
              fontSize: '12px',
              color: '#b5b5c3',
            }}
          >
            <span>
              <strong style={{ color: '#e8e8ef' }}>{name || '—'}</strong>
              {concept ? ` · ${concept}` : ''}
            </span>
            {systemType === 'vampire' && clan ? (
              <span style={{ color: themeAccent }}>Clan {clan}</span>
            ) : null}
            {systemType === 'werewolf' ? (
              <span style={{ color: themeAccent }}>
                {auspice} · {tribe}
              </span>
            ) : null}
            {systemType === 'mage' && tradition ? (
              <span style={{ color: themeAccent }}>{tradition}</span>
            ) : null}
          </div>
        </div>

        <div style={{ padding: '8px 16px 24px' }}>
          <ResponsiveSheetBlock
            sectionId={SHEET_SECTION_IDS.identity}
            title="Identity"
            subtitle="Chronicle and character hook"
            accent={themeAccent}
          >
            {inlineErr(SHEET_SECTION_IDS.identity)}
            <label style={{ color: '#c4b5fd', display: 'block', marginBottom: '8px' }}>
              Chronicle
            </label>
            <select
              value={campaignId}
              onChange={(e) => setCampaignId(e.target.value)}
              style={{
                width: '100%',
                padding: '10px',
                marginBottom: '20px',
                background: '#0f1729',
                color: '#e0e0e0',
                border: '2px solid #2a2a4e',
                borderRadius: '8px',
              }}
            >
              {eligible.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} — {c.game_system}
                </option>
              ))}
            </select>
            <label style={{ color: '#c4b5fd', display: 'block', marginBottom: '8px' }}>
              Character name
            </label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              style={{
                width: '100%',
                padding: '10px',
                marginBottom: '16px',
                background: '#0f1729',
                color: '#e0e0e0',
                border: '2px solid #2a2a4e',
                borderRadius: '8px',
              }}
            />
            <label style={{ color: '#c4b5fd', display: 'block', marginBottom: '8px' }}>
              Concept
            </label>
            <input
              value={concept}
              onChange={(e) => setConcept(e.target.value)}
              placeholder="e.g. weary homicide detective"
              style={{
                width: '100%',
                padding: '10px',
                background: '#0f1729',
                color: '#e0e0e0',
                border: '2px solid #2a2a4e',
                borderRadius: '8px',
              }}
            />
          </ResponsiveSheetBlock>

          <ResponsiveSheetBlock
            sectionId={SHEET_SECTION_IDS.template}
            title="Template"
            subtitle="Clan, breed, or tradition — your chronicle’s baseline"
            accent={themeAccent}
          >
            {systemType === 'vampire' && (
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
                  gap: '14px',
                }}
              >
                <div>
                  <label style={{ color: '#c4b5fd', display: 'block', marginBottom: '6px' }}>
                    Clan
                  </label>
                  <select
                    value={clan}
                    onChange={(e) => setClan(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '10px',
                      background: '#0f1729',
                      color: '#e0e0e0',
                      border: '2px solid #2a2a4e',
                      borderRadius: '8px',
                    }}
                  >
                    {VAMPIRE_CLANS.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label style={{ color: '#c4b5fd', display: 'block', marginBottom: '6px' }}>
                    Generation
                  </label>
                  <input
                    value={generation}
                    onChange={(e) => setGeneration(e.target.value)}
                    placeholder="13"
                    style={{
                      width: '100%',
                      padding: '10px',
                      background: '#0f1729',
                      color: '#e0e0e0',
                      border: '2px solid #2a2a4e',
                      borderRadius: '8px',
                    }}
                  />
                </div>
              </div>
            )}

            {systemType === 'werewolf' && (
              <>
                <label style={{ color: '#c4b5fd', display: 'block', marginBottom: '8px' }}>
                  Breed
                </label>
                <select
                  value={breed}
                  onChange={(e) => setBreed(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px',
                    marginBottom: '12px',
                    background: '#0f1729',
                    color: '#e0e0e0',
                    border: '2px solid #2a2a4e',
                    borderRadius: '8px',
                  }}
                >
                  {WTA_BREEDS.map((b) => (
                    <option key={b} value={b}>
                      {b}
                    </option>
                  ))}
                </select>
                <label style={{ color: '#c4b5fd', display: 'block', marginBottom: '8px' }}>
                  Auspice
                </label>
                <select
                  value={auspice}
                  onChange={(e) => setAuspice(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px',
                    marginBottom: '12px',
                    background: '#0f1729',
                    color: '#e0e0e0',
                    border: '2px solid #2a2a4e',
                    borderRadius: '8px',
                  }}
                >
                  {WTA_AUSPICES.map((a) => (
                    <option key={a} value={a}>
                      {a}
                    </option>
                  ))}
                </select>
                <label style={{ color: '#c4b5fd', display: 'block', marginBottom: '8px' }}>
                  Tribe
                </label>
                <select
                  value={tribe}
                  onChange={(e) => setTribe(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px',
                    background: '#0f1729',
                    color: '#e0e0e0',
                    border: '2px solid #2a2a4e',
                    borderRadius: '8px',
                  }}
                >
                  {WTA_TRIBES.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </>
            )}

            {systemType === 'mage' && (
              <>
                <label style={{ color: '#c4b5fd', display: 'block', marginBottom: '8px' }}>
                  Tradition
                </label>
                <select
                  value={tradition}
                  onChange={(e) => setTradition(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px',
                    background: '#0f1729',
                    color: '#e0e0e0',
                    border: '2px solid #2a2a4e',
                    borderRadius: '8px',
                  }}
                >
                  {MTA_TRADITIONS.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
                <p style={{ color: '#8b8b9f', fontSize: '13px', marginTop: '12px' }}>
                  Arete starts at 1. You will assign six sphere dots in Advantages.
                </p>
              </>
            )}
          </ResponsiveSheetBlock>

          <ResponsiveSheetBlock
            sectionId={SHEET_SECTION_IDS.nature}
            title="Nature & demeanor"
            subtitle="Classic oWoD-style archetypes (Revised-era lists). Pick Custom to type your own."
            accent={themeAccent}
          >
            {inlineErr(SHEET_SECTION_IDS.nature)}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
                gap: '16px',
              }}
            >
              <div>
                <label style={{ color: '#c4b5fd', display: 'block', marginBottom: '6px' }}>
                  Nature
                </label>
                <select
                  value={naturePick}
                  onChange={(e) => setNaturePick(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px',
                    marginBottom: '8px',
                    background: '#0f1729',
                    color: '#e0e0e0',
                    border: '2px solid #2a2a4e',
                    borderRadius: '8px',
                  }}
                >
                  {WOD_ARCHETYPES.map((a) => (
                    <option key={a} value={a}>
                      {a}
                    </option>
                  ))}
                  <option value={ARCHETYPE_CUSTOM}>Custom (enter below)</option>
                </select>
                <input
                  value={natureCustom}
                  onChange={(e) => setNatureCustom(e.target.value)}
                  placeholder={
                    naturePick === ARCHETYPE_CUSTOM
                      ? 'Your Nature (free text)'
                      : 'Optional: extra detail, or wording for another system'
                  }
                  style={{
                    width: '100%',
                    padding: '10px',
                    background: '#0f1729',
                    color: '#e0e0e0',
                    border: '2px solid #2a2a4e',
                    borderRadius: '8px',
                  }}
                />
              </div>
              <div>
                <label style={{ color: '#c4b5fd', display: 'block', marginBottom: '6px' }}>
                  Demeanor
                </label>
                <select
                  value={demeanorPick}
                  onChange={(e) => setDemeanorPick(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px',
                    marginBottom: '8px',
                    background: '#0f1729',
                    color: '#e0e0e0',
                    border: '2px solid #2a2a4e',
                    borderRadius: '8px',
                  }}
                >
                  {WOD_ARCHETYPES.map((a) => (
                    <option key={a} value={a}>
                      {a}
                    </option>
                  ))}
                  <option value={ARCHETYPE_CUSTOM}>Custom (enter below)</option>
                </select>
                <input
                  value={demeanorCustom}
                  onChange={(e) => setDemeanorCustom(e.target.value)}
                  placeholder={
                    demeanorPick === ARCHETYPE_CUSTOM
                      ? 'Your Demeanor (free text)'
                      : 'Optional: extra detail, or wording for another system'
                  }
                  style={{
                    width: '100%',
                    padding: '10px',
                    background: '#0f1729',
                    color: '#e0e0e0',
                    border: '2px solid #2a2a4e',
                    borderRadius: '8px',
                  }}
                />
              </div>
            </div>
          </ResponsiveSheetBlock>

          <ResponsiveSheetBlock
            sectionId={SHEET_SECTION_IDS.attributes}
            title="Attributes"
            subtitle="7 / 5 / 3 across Physical, Social, Mental — minimum 1 in each trait."
            accent={themeAccent}
          >
            {inlineErr(SHEET_SECTION_IDS.attributes)}
            <PoolSummary variant="attributes" attrs={attrs} pools={pools} />
            <label style={{ color: '#c4b5fd', display: 'block', marginBottom: '8px' }}>
              Which category is primary (7 dots)?
            </label>
            <select
              value={priority}
              onChange={(e) => setPriority(e.target.value)}
              style={{
                width: '100%',
                maxWidth: '320px',
                padding: '10px',
                marginBottom: '20px',
                background: '#0f1729',
                color: '#e0e0e0',
                border: '2px solid #2a2a4e',
                borderRadius: '8px',
              }}
            >
              <option value="physical">Physical primary (7) · Social (5) · Mental (3)</option>
              <option value="social">Social primary (7) · Physical (5) · Mental (3)</option>
              <option value="mental">Mental primary (7) · Social (5) · Physical (3)</option>
            </select>
            <AttributeColumns attrs={attrs} setAttrs={setAttrs} pools={pools} />
          </ResponsiveSheetBlock>

          <ResponsiveSheetBlock
            sectionId={SHEET_SECTION_IDS.abilities}
            title="Abilities"
            subtitle="11 / 7 / 4 across Talents, Skills, Knowledges. Custom rows share the same column pools."
            accent={themeAccent}
          >
            {inlineErr(SHEET_SECTION_IDS.abilities)}
            <PoolSummary
              variant="abilities"
              abilities={abilities}
              abilityPools={abilityPools}
              customAbilities={customAbilities}
            />
            <label style={{ color: '#c4b5fd', display: 'block', marginBottom: '8px' }}>
              Which column is primary (11 dots)?
            </label>
            <select
              value={abilityPriority}
              onChange={(e) => setAbilityPriority(e.target.value)}
              style={{
                width: '100%',
                maxWidth: '400px',
                padding: '10px',
                marginBottom: '20px',
                background: '#0f1729',
                color: '#e0e0e0',
                border: '2px solid #2a2a4e',
                borderRadius: '8px',
              }}
            >
              <option value="talents">Talents 11 · Skills 7 · Knowledges 4</option>
              <option value="skills">Skills 11 · Talents 7 · Knowledges 4</option>
              <option value="knowledges">Knowledges 11 · Skills 7 · Talents 4</option>
            </select>
            <AbilityColumns
              abilities={abilities}
              setAbilities={setAbilities}
              pools={abilityPools}
              customAbilities={customAbilities}
              setCustomAbilities={setCustomAbilities}
            />
          </ResponsiveSheetBlock>

          <ResponsiveSheetBlock
            sectionId={SHEET_SECTION_IDS.advantages}
            title="Advantages"
            subtitle="Line-specific pools — virtues, spheres, or Garou energy."
            accent={themeAccent}
          >
            {inlineErr(SHEET_SECTION_IDS.advantages)}

            {systemType === 'vampire' && (
              <SheetSection
                title="Kindred advantages"
                subtitle="Neonate defaults: 3 discipline dots, 5 background dots, virtues total 7."
                accent={themeAccent}
              >
                <div style={{ marginBottom: '20px' }}>
                  <div style={{ color: '#94a3b8', fontSize: '12px', marginBottom: '8px' }}>
                    Disciplines (max 3 dots total at creation)
                  </div>
                  {disciplines.map((d, i) => (
                    <div
                      key={i}
                      style={{
                        display: 'flex',
                        flexWrap: 'wrap',
                        alignItems: 'center',
                        gap: '10px',
                        marginBottom: '10px',
                      }}
                    >
                      <select
                        value={DISCIPLINE_PRESETS.includes(d.name) ? d.name : d.name ? '__custom' : ''}
                        onChange={(e) => {
                          const v = e.target.value;
                          const next = [...disciplines];
                          if (v === '__custom') next[i] = { ...next[i], name: '' };
                          else next[i] = { ...next[i], name: v };
                          setDisciplines(next);
                        }}
                        style={{
                          flex: '1 1 180px',
                          padding: '8px',
                          background: '#0f1729',
                          color: '#e0e0e0',
                          border: '1px solid #2a2a4e',
                          borderRadius: '6px',
                        }}
                      >
                        <option value="">—</option>
                        {DISCIPLINE_PRESETS.map((p) => (
                          <option key={p} value={p}>
                            {p}
                          </option>
                        ))}
                        <option value="__custom">Custom name…</option>
                      </select>
                      {(!d.name || !DISCIPLINE_PRESETS.includes(d.name)) && (
                        <input
                          placeholder="Discipline name"
                          value={DISCIPLINE_PRESETS.includes(d.name) ? '' : d.name}
                          onChange={(e) => {
                            const next = [...disciplines];
                            next[i] = { ...next[i], name: e.target.value };
                            setDisciplines(next);
                          }}
                          style={{
                            flex: '1 1 140px',
                            padding: '8px',
                            background: '#0f1729',
                            color: '#e0e0e0',
                            border: '1px solid #2a2a4e',
                            borderRadius: '6px',
                          }}
                        />
                      )}
                      <DotTrack
                        value={d.dots}
                        maxRank={5}
                        accent={themeAccent}
                        onChange={(n) => {
                          const next = [...disciplines];
                          const others = next.reduce(
                            (s, x, j) => (j === i ? s : s + (parseInt(x.dots, 10) || 0)),
                            0
                          );
                          if (others + n > 3) return;
                          next[i] = { ...next[i], dots: n };
                          setDisciplines(next);
                        }}
                      />
                    </div>
                  ))}
                </div>

                <div style={{ marginBottom: '20px' }}>
                  <div style={{ color: '#94a3b8', fontSize: '12px', marginBottom: '8px' }}>
                    Backgrounds (max 5 dots total)
                  </div>
                  {backgrounds.map((b, i) => (
                    <div
                      key={i}
                      style={{
                        display: 'flex',
                        flexWrap: 'wrap',
                        alignItems: 'center',
                        gap: '10px',
                        marginBottom: '8px',
                      }}
                    >
                      <input
                        placeholder="e.g. Resources"
                        value={b.name}
                        onChange={(e) => {
                          const next = [...backgrounds];
                          next[i] = { ...next[i], name: e.target.value };
                          setBackgrounds(next);
                        }}
                        style={{
                          flex: '1 1 160px',
                          padding: '8px',
                          background: '#0f1729',
                          color: '#e0e0e0',
                          border: '1px solid #2a2a4e',
                          borderRadius: '6px',
                        }}
                      />
                      <DotTrack
                        value={b.dots}
                        maxRank={5}
                        accent="#a78bfa"
                        onChange={(n) => {
                          const next = [...backgrounds];
                          const others = next.reduce(
                            (s, x, j) => (j === i ? s : s + (parseInt(x.dots, 10) || 0)),
                            0
                          );
                          if (others + n > 5) return;
                          next[i] = { ...next[i], dots: n };
                          setBackgrounds(next);
                        }}
                      />
                    </div>
                  ))}
                </div>

                <div style={{ marginBottom: '16px' }}>
                  <div style={{ color: '#94a3b8', fontSize: '12px', marginBottom: '8px' }}>
                    Virtues (7 dots, each 1–5)
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px' }}>
                    {[
                      ['conscience', 'Conscience / Conviction'],
                      ['self_control', 'Self-Control / Instinct'],
                      ['courage', 'Courage'],
                    ].map(([key, label]) => (
                      <div key={key} style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <span style={{ color: '#c4c4d4', fontSize: '12px', width: '140px' }}>
                          {label}
                        </span>
                        <DotTrack
                          value={virtues[key]}
                          maxRank={5}
                          accent="#f472b6"
                          onChange={(n) => {
                            setVirtues((prev) => ({ ...prev, [key]: String(n) }));
                          }}
                        />
                      </div>
                    ))}
                  </div>
                </div>

                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
                    gap: '12px',
                  }}
                >
                  <div>
                    <label style={{ color: '#c4b5fd', fontSize: '12px' }}>Humanity</label>
                    <input
                      type="number"
                      min={0}
                      max={10}
                      value={humanity}
                      onChange={(e) => setHumanity(e.target.value)}
                      style={{
                        width: '100%',
                        marginTop: '4px',
                        padding: '8px',
                        background: '#0f1729',
                        color: '#e0e0e0',
                        border: '1px solid #2a2a4e',
                        borderRadius: '6px',
                      }}
                    />
                  </div>
                  <div>
                    <label style={{ color: '#c4b5fd', fontSize: '12px' }}>Willpower</label>
                    <input
                      type="number"
                      min={1}
                      max={10}
                      value={willpowerVampire}
                      onChange={(e) => setWillpowerVampire(e.target.value)}
                      style={{
                        width: '100%',
                        marginTop: '4px',
                        padding: '8px',
                        background: '#0f1729',
                        color: '#e0e0e0',
                        border: '1px solid #2a2a4e',
                        borderRadius: '6px',
                      }}
                    />
                  </div>
                </div>
              </SheetSection>
            )}

            {systemType === 'mage' && (
              <SheetSection
                title="Spheres"
                subtitle="Allocate exactly 6 dots among the nine spheres (Arete remains 1)."
                accent={themeAccent}
              >
                {MTA_SPHERES.map(([k, label]) => (
                  <div
                    key={k}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      marginBottom: '8px',
                      padding: '6px 8px',
                      background: 'rgba(0,0,0,0.2)',
                      borderRadius: '6px',
                    }}
                  >
                    <span style={{ color: '#c4c4d4', fontSize: '13px' }}>{label}</span>
                    <DotTrack
                      value={spheres[k]}
                      maxRank={5}
                      accent={themeAccent}
                      onChange={(n) => {
                        setSpheres((prev) => {
                          const old = parseInt(prev[k], 10) || 0;
                          const delta = n - old;
                          const sum = MTA_SPHERES.reduce(
                            (s, [kk]) => s + (parseInt(prev[kk], 10) || 0),
                            0
                          );
                          if (sum + delta > 6) return prev;
                          return { ...prev, [k]: n };
                        });
                      }}
                    />
                  </div>
                ))}
              </SheetSection>
            )}

            {systemType === 'werewolf' && (
              <SheetSection
                title="Garou advantages"
                subtitle="Starting Rage, Gnosis, and gifts — set with your Storyteller."
                accent={themeAccent}
              >
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))',
                    gap: '12px',
                    marginBottom: '14px',
                  }}
                >
                  <div>
                    <label style={{ color: '#c4b5fd', fontSize: '12px' }}>Rage</label>
                    <input
                      type="number"
                      min={0}
                      max={10}
                      value={werewolfRage}
                      onChange={(e) => setWerewolfRage(e.target.value)}
                      style={{
                        width: '100%',
                        marginTop: '4px',
                        padding: '8px',
                        background: '#0f1729',
                        color: '#e0e0e0',
                        border: '1px solid #2a2a4e',
                        borderRadius: '6px',
                      }}
                    />
                  </div>
                  <div>
                    <label style={{ color: '#c4b5fd', fontSize: '12px' }}>Gnosis</label>
                    <input
                      type="number"
                      min={0}
                      max={10}
                      value={werewolfGnosis}
                      onChange={(e) => setWerewolfGnosis(e.target.value)}
                      style={{
                        width: '100%',
                        marginTop: '4px',
                        padding: '8px',
                        background: '#0f1729',
                        color: '#e0e0e0',
                        border: '1px solid #2a2a4e',
                        borderRadius: '6px',
                      }}
                    />
                  </div>
                </div>
                <label style={{ color: '#c4b5fd', display: 'block', marginBottom: '8px' }}>
                  Gifts & rank notes
                </label>
                <textarea
                  value={giftsNotes}
                  onChange={(e) => setGiftsNotes(e.target.value)}
                  rows={4}
                  placeholder="Gift names, rank, or table agreements…"
                  style={{
                    width: '100%',
                    padding: '12px',
                    background: '#0f1729',
                    color: '#e0e0e0',
                    border: '2px solid #2a2a4e',
                    borderRadius: '8px',
                    resize: 'vertical',
                    fontFamily: 'Crimson Text, Georgia, serif',
                    lineHeight: 1.5,
                  }}
                />
              </SheetSection>
            )}
          </ResponsiveSheetBlock>

          <ResponsiveSheetBlock
            sectionId={SHEET_SECTION_IDS.story}
            title="Story & merits"
            subtitle="Background narrative and structured merits / flaws."
            accent="#9d4edd"
          >
            <label style={{ color: '#c4b5fd', display: 'block', marginBottom: '8px' }}>
              Background & hooks
            </label>
            <textarea
              value={background}
              onChange={(e) => setBackground(e.target.value)}
              rows={6}
              placeholder="History, coterie, pack, cabal, goals…"
              style={{
                width: '100%',
                padding: '12px',
                marginBottom: '20px',
                background: '#0f1729',
                color: '#e0e0e0',
                border: '2px solid #2a2a4e',
                borderRadius: '8px',
                resize: 'vertical',
                fontFamily: 'Crimson Text, Georgia, serif',
                lineHeight: 1.6,
              }}
            />
            <MeritFlawRows
              rows={meritRows}
              setRows={setMeritRows}
              globalNotes={meritsGlobalNotes}
              setGlobalNotes={setMeritsGlobalNotes}
            />
          </ResponsiveSheetBlock>

          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: '10px',
              marginTop: '24px',
              justifyContent: 'space-between',
            }}
          >
            <button
              type="button"
              onClick={onCancel}
              style={{
                padding: '10px 18px',
                background: '#1e293b',
                color: '#e2e8f0',
                border: '1px solid #475569',
                borderRadius: '8px',
                cursor: 'pointer',
              }}
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
