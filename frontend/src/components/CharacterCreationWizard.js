import React, { useMemo, useState } from 'react';
import { GothicBox } from './GothicDecorations';
import DotTrack from './characterCreation/DotTrack';
import SheetSection from './characterCreation/SheetSection';
import PoolSummary from './characterCreation/PoolSummary';
import AttributeColumns from './characterCreation/AttributeColumns';
import AbilityColumns from './characterCreation/AbilityColumns';
import MeritFlawRows from './characterCreation/MeritFlawRows';
import ResponsiveSheetBlock from './characterCreation/ResponsiveSheetBlock';
import FreebieSummary from './characterCreation/FreebieSummary';
import V5CharacterCreationWizard from './characterCreation/V5CharacterCreationWizard';
import { editionLabel, editionOf, V5 } from '../rules/rulesEdition';
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
  abilityPools as abilityPoolsFor,
  attributePools,
  computeClassicFreebies,
  deriveClassicMorality,
  emptyAbilityMap,
  emptyVirtueFreebies,
  finalVirtues,
  isNosferatu,
  emptyAttrMap,
  emptySphereMap,
  emptyVirtues,
  VIRTUE_TOTAL_AT_CREATION,
  validateAbilitySpread,
  validateAttributeSpread,
  validateFreebies,
  validateSpheres,
  validateVirtues,
} from '../characterSheet/validation';
import { BACKGROUND_DOTS, DISCIPLINE_DOTS } from '../rules/classicRules';
import { t } from '../i18n';
import { Term } from '../i18n/glossary';
import { translateSheetError } from '../characterSheet/i18nErrors';

const API_URL = '/api';

// Labels are functions: t() must run at render time, in the active language.
const SECTION_ORDER = [
  { id: SHEET_SECTION_IDS.identity, label: () => t('wizard:section.identity', 'Identity') },
  { id: SHEET_SECTION_IDS.template, label: () => t('wizard:section.template', 'Template') },
  { id: SHEET_SECTION_IDS.nature, label: () => 'Nature' },
  { id: SHEET_SECTION_IDS.attributes, label: () => 'Attributes' },
  { id: SHEET_SECTION_IDS.abilities, label: () => 'Abilities' },
  { id: SHEET_SECTION_IDS.advantages, label: () => 'Advantages' },
  { id: SHEET_SECTION_IDS.story, label: () => t('wizard:section.story', 'Story') },
  { id: SHEET_SECTION_IDS.freebies, label: () => 'Freebies' },
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
 * Classic (Revised) rules; a V5 chronicle renders the V5 forge instead.
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

  const [campaignIdState, setCampaignId] = useState(
    eligible[0]?.id != null ? String(eligible[0].id) : ''
  );
  // Campaigns can arrive after mount: fall back to the first eligible one so the state
  // always matches what the <select> shows.
  const campaignId = eligible.some((c) => String(c.id) === String(campaignIdState))
    ? String(campaignIdState)
    : eligible[0]?.id != null
      ? String(eligible[0].id)
      : '';
  const [name, setName] = useState('');
  const [concept, setConcept] = useState('');
  const [priority, setPriority] = useState('physical');
  const [attrsRaw, setAttrs] = useState(() => emptyAttrMap());
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
  // Humanity / Willpower are derived from Virtues; these are extra dots bought with freebies.
  const [humanityBonus, setHumanityBonus] = useState(0);
  const [willpowerBonus, setWillpowerBonus] = useState(0);
  // Creation Virtues (1 free each + 7) and freebie Virtue dots, kept apart: only the
  // creation dots set Humanity / Willpower.
  const [virtues, setVirtues] = useState(() => emptyVirtues());
  const [virtueFreebies, setVirtueFreebies] = useState(() => emptyVirtueFreebies());
  const [freebieMode, setFreebieMode] = useState(false);
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
  // Nosferatu Appearance is always 0; other clans keep at least the free dot. The raw
  // state is left alone so switching clan back restores the previous Appearance.
  const nosferatu = isNosferatu(systemType, clan);
  const attrs = useMemo(
    () => ({
      ...attrsRaw,
      appearance: nosferatu ? 0 : Math.max(1, parseInt(attrsRaw.appearance, 10) || 1),
    }),
    [attrsRaw, nosferatu]
  );

  // Dots ADDED on top of the free dot per attribute (Revised 7/5/3), abilities 13/9/5.
  const pools = useMemo(() => attributePools(priority), [priority]);
  const abilityPools = useMemo(() => abilityPoolsFor(abilityPriority), [abilityPriority]);

  const morality = deriveClassicMorality(virtues, virtueFreebies);
  const humanityFinal = Math.min(10, morality.humanityBase + humanityBonus);
  const willpowerFinal = Math.min(10, morality.willpowerBase + willpowerBonus);
  const virtuesFinal = finalVirtues(virtues, virtueFreebies);
  const virtueTotal = ['conscience', 'self_control', 'courage'].reduce(
    (sum, k) => sum + (parseInt(virtues[k], 10) || 0),
    0
  );

  /**
   * Set a Virtue's final rating. Raising fills the creation budget (10) first, then
   * (freebie mode only) buys freebie dots; lowering removes freebie dots first.
   */
  const setVirtueFinal = (key, n) => {
    const creation = parseInt(virtues[key], 10) || 1;
    const bought = parseInt(virtueFreebies[key], 10) || 0;
    const target = Math.max(1, Math.min(5, n));
    const current = creation + bought;
    if (target === current) return;
    if (target < current) {
      const drop = current - target;
      const fromBought = Math.min(bought, drop);
      setVirtueFreebies((prev) => ({ ...prev, [key]: bought - fromBought }));
      setVirtues((prev) => ({ ...prev, [key]: Math.max(1, creation - (drop - fromBought)) }));
      return;
    }
    const up = target - current;
    const toCreation = Math.min(up, Math.max(0, VIRTUE_TOTAL_AT_CREATION - virtueTotal));
    const toBought = up - toCreation;
    if (toBought > 0 && !freebieMode) return;
    setVirtues((prev) => ({ ...prev, [key]: creation + toCreation }));
    if (toBought > 0) setVirtueFreebies((prev) => ({ ...prev, [key]: bought + toBought }));
  };

  const freebies = computeClassicFreebies({
    systemType,
    attrs,
    attrPools: pools,
    abilities,
    abilityPoolsSel: abilityPools,
    customAbilities,
    disciplines,
    backgrounds,
    virtues,
    virtueFreebies,
    humanityBonus,
    willpowerBonus,
    meritRows,
    nosferatu,
  });

  const themeAccent =
    systemType === 'werewolf' ? '#4ade80' : systemType === 'mage' ? '#38bdf8' : '#e94560';

  const resolveNatureDemeanor = (pick, custom) => {
    const text = (custom || '').trim();
    if (pick === ARCHETYPE_CUSTOM) return text;
    return text ? `${pick} (${text})` : pick;
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
        humanity: humanityFinal,
        willpower: willpowerFinal,
        virtues: virtuesFinal,
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
    if (!campaign) err[SHEET_SECTION_IDS.identity] = t('wizard:error.chronicle', 'Choose a chronicle.');
    const cidNum = parseInt(campaignId, 10);
    if (!Number.isFinite(cidNum) || cidNum < 1) {
      err[SHEET_SECTION_IDS.identity] = t('wizard:error.chronicleInvalid', 'Choose a valid chronicle.');
    }
    if (!name.trim()) err[SHEET_SECTION_IDS.identity] = t('wizard:error.name', 'Character name is required.');

    if (['vampire', 'werewolf', 'mage'].includes(systemType)) {
      const natureMsgs = [];
      if (naturePick === ARCHETYPE_CUSTOM && !(natureCustom || '').trim()) {
        natureMsgs.push(t('wizard:classic.error.nature', 'Enter your Nature (free text), or pick a preset archetype.'));
      }
      if (demeanorPick === ARCHETYPE_CUSTOM && !(demeanorCustom || '').trim()) {
        natureMsgs.push(t('wizard:classic.error.demeanor', 'Enter your Demeanor (free text), or pick a preset archetype.'));
      }
      if (natureMsgs.length) err[SHEET_SECTION_IDS.nature] = natureMsgs.join(' ');
    }

    // Final sheets may hold freebie dots; the freebie ledger prices and caps them.
    const errA = validateAttributeSpread(attrs, pools, { allowFreebies: true, nosferatu });
    if (errA) err[SHEET_SECTION_IDS.attributes] = translateSheetError(errA);

    const errAb = validateAbilitySpread(abilities, abilityPools, customAbilities, {
      allowFreebies: true,
    });
    if (errAb) err[SHEET_SECTION_IDS.abilities] = translateSheetError(errAb);

    if (systemType === 'vampire') {
      const advMsgs = [];
      // Creation Virtues must be exactly 10; extra dots live in virtueFreebies.
      const vErr = validateVirtues(virtues);
      if (vErr) advMsgs.push(translateSheetError(vErr));
      const dSum = disciplines.reduce((s, d) => s + (parseInt(d.dots, 10) || 0), 0);
      if (dSum < DISCIPLINE_DOTS) {
        advMsgs.push(t('wizard:classic.error.disciplines', 'Place all {{n}} Discipline dots (clan Disciplines; Caitiff any).', { n: DISCIPLINE_DOTS }));
      }
      const bgSum = backgrounds.reduce((s, b) => s + (parseInt(b.dots, 10) || 0), 0);
      if (bgSum < BACKGROUND_DOTS) {
        advMsgs.push(t('wizard:classic.error.backgrounds', 'Place all {{n}} Background dots.', { n: BACKGROUND_DOTS }));
      }
      if (advMsgs.length) err[SHEET_SECTION_IDS.advantages] = advMsgs.join(' ');
    }

    const fErr = validateFreebies(freebies);
    if (fErr) err[SHEET_SECTION_IDS.freebies] = translateSheetError(fErr);

    if (systemType === 'mage') {
      const sErr = validateSpheres(spheres);
      if (sErr) err[SHEET_SECTION_IDS.advantages] = translateSheetError(sErr);
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
        showError?.(body.error || t('wizard:error.createFailed', 'Could not create character.'));
        return;
      }
      showSuccess?.(t('wizard:created', 'Character forged. Select them in Player Profile if needed.'));
      onDone?.(body);
    } catch (e) {
      showError?.(t('wizard:error.network', 'Network error while creating character.'));
    } finally {
      setSubmitting(false);
    }
  };

  const inlineErr = (sectionId) =>
    fieldErrors[sectionId] ? (
      <p style={{ color: '#f87171', fontSize: '13px', marginBottom: '12px' }}>{fieldErrors[sectionId]}</p>
    ) : null;

  if (campaign && editionOf(campaign) === V5) {
    return (
      <V5CharacterCreationWizard
        token={token}
        campaigns={eligible}
        campaignId={campaignId}
        onCampaignChange={setCampaignId}
        onDone={onDone}
        onCancel={onCancel}
        showError={showError}
        showSuccess={showSuccess}
      />
    );
  }

  if (!eligible.length) {
    return (
      <GothicBox theme="vampire" style={{ padding: '24px', maxWidth: '560px', margin: '0 auto' }}>
        <p style={{ color: '#b5b5c3' }}>
          {t('wizard:noChronicle', 'You need to be a member of at least one Vampire, Werewolf, or Mage chronicle before using this forge.')}
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
          {t('wizard:back', 'Back')}
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
            {t('wizard:classic.title', 'Character sheet forge')}
          </h2>
          <p style={{ color: '#8b8b9f', fontSize: '14px', lineHeight: 1.5 }}>
            {t('wizard:classic.intro', 'Build a Classic World of Darkness (Revised) sheet: place your creation dots, then spend 15 freebie points. Scroll the sheet in order, or jump with the nav. Your Storyteller has final say on numbers and templates.')}
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
                {s.label()}
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
            <label
              style={{
                color: freebies.remaining < 0 ? '#fca5a5' : '#94a3b8',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                cursor: 'pointer',
              }}
            >
              <input
                type="checkbox"
                checked={freebieMode}
                onChange={(e) => setFreebieMode(e.target.checked)}
              />
              {t('wizard:classic.freebieMode', 'Freebie mode · {{spent}}/{{available}} spent', { spent: freebies.spent, available: freebies.available })}
            </label>
          </div>
        </div>

        <div style={{ padding: '8px 16px 24px' }}>
          <ResponsiveSheetBlock
            sectionId={SHEET_SECTION_IDS.identity}
            title={t('wizard:section.identity', 'Identity')}
            subtitle={t('wizard:classic.identitySub', 'Chronicle and character hook')}
            accent={themeAccent}
          >
            {inlineErr(SHEET_SECTION_IDS.identity)}
            <label style={{ color: '#c4b5fd', display: 'block', marginBottom: '8px' }}>
              {t('wizard:field.chronicle', 'Chronicle')}
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
                  {String(c.game_system || '').toLowerCase() === 'vampire' ? ` (${editionLabel(c)})` : ''}
                </option>
              ))}
            </select>
            <label style={{ color: '#c4b5fd', display: 'block', marginBottom: '8px' }}>
              {t('wizard:field.name', 'Character name')}
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
              {t('wizard:field.concept', 'Concept')}
            </label>
            <input
              value={concept}
              onChange={(e) => setConcept(e.target.value)}
              placeholder={t('wizard:field.conceptPlaceholder', 'e.g. weary homicide detective')}
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
            title={t('wizard:section.template', 'Template')}
            subtitle={t('wizard:classic.templateSub', 'Clan, breed, or tradition — your chronicle’s baseline')}
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
                    <Term id="clan" />
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
                    <Term id="generation" />
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
                  {t('wizard:classic.areteHint', 'Arete starts at 1. You will assign six sphere dots in Advantages.')}
                </p>
              </>
            )}
          </ResponsiveSheetBlock>

          <ResponsiveSheetBlock
            sectionId={SHEET_SECTION_IDS.nature}
            title="Nature & Demeanor"
            subtitle={t('wizard:classic.natureSub', 'Classic oWoD-style archetypes (Revised-era lists). Pick Custom to type your own.')}
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
                  <option value={ARCHETYPE_CUSTOM}>{t('wizard:classic.customArchetype', 'Custom (enter below)')}</option>
                </select>
                <input
                  value={natureCustom}
                  onChange={(e) => setNatureCustom(e.target.value)}
                  placeholder={
                    naturePick === ARCHETYPE_CUSTOM
                      ? t('wizard:classic.naturePlaceholder', 'Your Nature (free text)')
                      : t('wizard:classic.archetypeExtra', 'Optional: extra detail, or wording for another system')
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
                  <option value={ARCHETYPE_CUSTOM}>{t('wizard:classic.customArchetype', 'Custom (enter below)')}</option>
                </select>
                <input
                  value={demeanorCustom}
                  onChange={(e) => setDemeanorCustom(e.target.value)}
                  placeholder={
                    demeanorPick === ARCHETYPE_CUSTOM
                      ? t('wizard:classic.demeanorPlaceholder', 'Your Demeanor (free text)')
                      : t('wizard:classic.archetypeExtra', 'Optional: extra detail, or wording for another system')
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
            title={<Term id="attributes" />}
            subtitle={t('wizard:classic.attributesSub', 'Every attribute starts at 1. Add 7 / 5 / 3 dots across Physical, Social, Mental.')}
            accent={themeAccent}
          >
            {inlineErr(SHEET_SECTION_IDS.attributes)}
            <PoolSummary variant="attributes" attrs={attrs} pools={pools} nosferatu={nosferatu} />
            <label style={{ color: '#c4b5fd', display: 'block', marginBottom: '8px' }}>
              {t('wizard:classic.attrPrimary', 'Which category is primary (+7 dots)?')}
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
              <option value="physical">{t('wizard:classic.attrOrder.physical', 'Physical primary (+7) · Social (+5) · Mental (+3)')}</option>
              <option value="social">{t('wizard:classic.attrOrder.social', 'Social primary (+7) · Physical (+5) · Mental (+3)')}</option>
              <option value="mental">{t('wizard:classic.attrOrder.mental', 'Mental primary (+7) · Social (+5) · Physical (+3)')}</option>
            </select>
            <AttributeColumns
              attrs={attrs}
              setAttrs={setAttrs}
              pools={pools}
              freebieMode={freebieMode}
              nosferatu={nosferatu}
            />
          </ResponsiveSheetBlock>

          <ResponsiveSheetBlock
            sectionId={SHEET_SECTION_IDS.abilities}
            title={<Term id="abilities" />}
            subtitle={t('wizard:classic.abilitiesSub', '13 / 9 / 5 across Talents, Skills, Knowledges; no ability above 3 before freebies. Custom rows share the column pools.')}
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
              {t('wizard:classic.abilityPrimary', 'Which column is primary (13 dots)?')}
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
              <option value="talents">Talents 13 · Skills 9 · Knowledges 5</option>
              <option value="skills">Skills 13 · Talents 9 · Knowledges 5</option>
              <option value="knowledges">Knowledges 13 · Skills 9 · Talents 5</option>
            </select>
            <AbilityColumns
              abilities={abilities}
              setAbilities={setAbilities}
              pools={abilityPools}
              customAbilities={customAbilities}
              setCustomAbilities={setCustomAbilities}
              freebieMode={freebieMode}
            />
          </ResponsiveSheetBlock>

          <ResponsiveSheetBlock
            sectionId={SHEET_SECTION_IDS.advantages}
            title="Advantages"
            subtitle={t('wizard:classic.advantagesSub', 'Line-specific pools — virtues, spheres, or Garou energy.')}
            accent={themeAccent}
          >
            {inlineErr(SHEET_SECTION_IDS.advantages)}

            {systemType === 'vampire' && (
              <SheetSection
                title={t('wizard:classic.kindredTitle', 'Kindred advantages')}
                subtitle={t('wizard:classic.kindredSub', '3 Discipline dots, 5 Background dots, Virtues 1 free each + 7. Humanity and Willpower follow from your Virtues.')}
                accent={themeAccent}
              >
                <div style={{ marginBottom: '20px' }}>
                  <div style={{ color: '#94a3b8', fontSize: '12px', marginBottom: '8px' }}>
                    <Term id="discipline">Disciplines</Term>{' '}
                    {t('wizard:classic.dotsAtCreation', '({{n}} dots at creation; more with freebies)', { n: DISCIPLINE_DOTS })}
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
                        <option value="__custom">{t('wizard:classic.customName', 'Custom name…')}</option>
                      </select>
                      {(!d.name || !DISCIPLINE_PRESETS.includes(d.name)) && (
                        <input
                          placeholder={t('wizard:classic.disciplineName', 'Discipline name')}
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
                          if (!freebieMode && n > (parseInt(d.dots, 10) || 0) && others + n > DISCIPLINE_DOTS) return;
                          next[i] = { ...next[i], dots: n };
                          setDisciplines(next);
                        }}
                      />
                    </div>
                  ))}
                </div>

                <div style={{ marginBottom: '20px' }}>
                  <div style={{ color: '#94a3b8', fontSize: '12px', marginBottom: '8px' }}>
                    <Term id="backgrounds" />{' '}
                    {t('wizard:classic.dotsAtCreation', '({{n}} dots at creation; more with freebies)', { n: BACKGROUND_DOTS })}
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
                        placeholder={t('wizard:classic.backgroundPlaceholder', 'e.g. Resources')}
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
                          if (!freebieMode && n > (parseInt(b.dots, 10) || 0) && others + n > BACKGROUND_DOTS) return;
                          next[i] = { ...next[i], dots: n };
                          setBackgrounds(next);
                        }}
                      />
                    </div>
                  ))}
                </div>

                <div style={{ marginBottom: '16px' }}>
                  <div style={{ color: '#94a3b8', fontSize: '12px', marginBottom: '8px' }}>
                    <Term id="virtues" />{' '}
                    {morality.virtueFreebieDots > 0
                      ? t('wizard:classic.virtuesPlacedBought', '(1 free each + 7 = {{total}}; placed {{placed}} + {{bought}} bought with freebies; those don\'t change Humanity or Willpower)', { total: VIRTUE_TOTAL_AT_CREATION, placed: virtueTotal, bought: morality.virtueFreebieDots })
                      : t('wizard:classic.virtuesPlaced', '(1 free each + 7 = {{total}}; placed {{placed}})', { total: VIRTUE_TOTAL_AT_CREATION, placed: virtueTotal })}
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px' }}>
                    {[
                      ['conscience', 'Conscience / Conviction'],
                      ['self_control', 'Self-Control / Instinct'],
                      ['courage', 'Courage'],
                    ].map(([key, label]) => (
                      <div key={key} style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <span style={{ color: '#c4c4d4', fontSize: '12px', minWidth: '140px' }}>
                          {label}
                        </span>
                        <DotTrack
                          value={virtuesFinal[key]}
                          maxRank={5}
                          accent="#f472b6"
                          onChange={(n) => setVirtueFinal(key, n)}
                        />
                        {virtueFreebies[key] > 0 ? (
                          <span style={{ color: '#94a3b8', fontSize: '11px' }}>
                            {t('wizard:classic.plusFreebie', '{{base}} + {{n}} freebie', { base: virtues[key], n: virtueFreebies[key] })}
                          </span>
                        ) : null}
                      </div>
                    ))}
                  </div>
                </div>

                <div style={{ display: 'grid', gap: '10px' }}>
                  {[
                    ['humanity', 'Humanity', humanityFinal, morality.humanityBase, 'Conscience + Self-Control', humanityBonus, setHumanityBonus],
                    ['willpower', 'Willpower', willpowerFinal, morality.willpowerBase, 'Courage', willpowerBonus, setWillpowerBonus],
                  ].map(([termId, label, value, baseValue, from, bonus, setBonus]) => (
                    <div key={label} style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '10px' }}>
                      <span style={{ color: '#c4b5fd', fontSize: '12px', minWidth: '80px' }}><Term id={termId} /></span>
                      <DotTrack value={value} maxRank={10} accent="#f472b6" disabled onChange={() => {}} />
                      <span style={{ color: '#94a3b8', fontSize: '12px' }}>
                        {value} = {from} ({baseValue}){bonus > 0 ? ` + ${t('wizard:classic.nFreebie', '{{n}} freebie', { n: bonus })}` : ''}
                      </span>
                      {freebieMode ? (
                        <span style={{ display: 'inline-flex', gap: '4px' }}>
                          <button
                            type="button"
                            aria-label={t('wizard:classic.lowerFreebie', 'Lower {{label}} freebie dots', { label })}
                            disabled={bonus <= 0}
                            onClick={() => setBonus(Math.max(0, bonus - 1))}
                            style={{ padding: '2px 8px', background: '#1e293b', color: '#e2e8f0', border: '1px solid #475569', borderRadius: '6px', cursor: 'pointer' }}
                          >
                            −
                          </button>
                          <button
                            type="button"
                            aria-label={t('wizard:classic.raiseFreebie', 'Raise {{label}} with freebies', { label })}
                            disabled={value >= 10}
                            onClick={() => setBonus(bonus + 1)}
                            style={{ padding: '2px 8px', background: '#1e293b', color: '#e2e8f0', border: '1px solid #475569', borderRadius: '6px', cursor: 'pointer' }}
                          >
                            +
                          </button>
                        </span>
                      ) : null}
                    </div>
                  ))}
                </div>
              </SheetSection>
            )}

            {systemType === 'mage' && (
              <SheetSection
                title="Spheres"
                subtitle={t('wizard:classic.spheresSub', 'Allocate exactly 6 dots among the nine spheres (Arete remains 1).')}
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
                title={t('wizard:classic.garouTitle', 'Garou advantages')}
                subtitle={t('wizard:classic.garouSub', 'Starting Rage, Gnosis, and gifts — set with your Storyteller.')}
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
                  {t('wizard:classic.giftsNotes', 'Gifts & rank notes')}
                </label>
                <textarea
                  value={giftsNotes}
                  onChange={(e) => setGiftsNotes(e.target.value)}
                  rows={4}
                  placeholder={t('wizard:classic.giftsPlaceholder', 'Gift names, rank, or table agreements…')}
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
            title={t('wizard:classic.storyTitle', 'Story & merits')}
            subtitle={t('wizard:classic.storySub', 'Background narrative and structured merits / flaws.')}
            accent="#9d4edd"
          >
            <label style={{ color: '#c4b5fd', display: 'block', marginBottom: '8px' }}>
              {t('wizard:classic.backgroundStory', 'Background & hooks')}
            </label>
            <textarea
              value={background}
              onChange={(e) => setBackground(e.target.value)}
              rows={6}
              placeholder={t('wizard:classic.backgroundStoryPlaceholder', 'History, coterie, pack, cabal, goals…')}
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

          <ResponsiveSheetBlock
            sectionId={SHEET_SECTION_IDS.freebies}
            title={<Term id="freebie" />}
            subtitle={t('wizard:classic.freebiesSub', '15 points (+ up to 7 from Flaws) to raise anything above the creation budgets.')}
            accent={themeAccent}
          >
            {inlineErr(SHEET_SECTION_IDS.freebies)}
            <FreebieSummary
              freebies={freebies}
              freebieMode={freebieMode}
              setFreebieMode={setFreebieMode}
              isVampire={systemType === 'vampire'}
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
              {t('wizard:cancel', 'Cancel')}
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
              {submitting ? t('wizard:submitting', 'Sealing sheet…') : t('wizard:submit', 'Create character')}
            </button>
          </div>
        </div>
      </GothicBox>
    </div>
  );
}
