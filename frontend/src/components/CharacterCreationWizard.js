import React, { useMemo, useState } from 'react';
import { GothicBox } from './GothicDecorations';

const API_URL = '/api';

const PHYSICAL = ['strength', 'dexterity', 'stamina'];
const SOCIAL = ['charisma', 'manipulation', 'appearance'];
const MENTAL = ['perception', 'intelligence', 'wits'];

/** Revised-era ability columns (labels match common sheets; keys are snake_case in JSON). */
const TALENTS = [
  ['alertness', 'Alertness'],
  ['athletics', 'Athletics'],
  ['brawl', 'Brawl'],
  ['dodge', 'Dodge'],
  ['empathy', 'Empathy'],
  ['expression', 'Expression'],
  ['intimidation', 'Intimidation'],
  ['leadership', 'Leadership'],
  ['streetwise', 'Streetwise'],
  ['subterfuge', 'Subterfuge'],
];

const SKILLS = [
  ['animal_ken', 'Animal Ken'],
  ['crafts', 'Crafts'],
  ['drive', 'Drive'],
  ['etiquette', 'Etiquette'],
  ['firearms', 'Firearms'],
  ['melee', 'Melee'],
  ['performance', 'Performance'],
  ['security', 'Security'],
  ['stealth', 'Stealth'],
  ['survival', 'Survival'],
];

const KNOWLEDGES = [
  ['academics', 'Academics'],
  ['computer', 'Computer'],
  ['finance', 'Finance'],
  ['investigation', 'Investigation'],
  ['law', 'Law'],
  ['linguistics', 'Linguistics'],
  ['medicine', 'Medicine'],
  ['occult', 'Occult'],
  ['politics', 'Politics'],
  ['science', 'Science'],
];

const VAMPIRE_CLANS = [
  'Brujah', 'Gangrel', 'Malkavian', 'Nosferatu', 'Toreador', 'Tremere', 'Ventrue',
  'Lasombra', 'Tzimisce', 'Ravnos', 'Assamite', 'Followers of Set', 'Giovanni',
];

const WTA_BREEDS = ['Homid', 'Metis', 'Lupus'];
const WTA_AUSPICES = ['Ahroun', 'Galliard', 'Philodox', 'Ragabash', 'Theurge'];
const WTA_TRIBES = [
  'Black Furies', 'Bone Gnawers', 'Children of Gaia', 'Fianna', 'Get of Fenris',
  'Glass Walkers', 'Red Talons', 'Shadow Lords', 'Silent Striders', 'Silver Fangs',
  'Uktena', 'Wendigo', 'Stargazers',
];

const MTA_TRADITIONS = [
  'Akashic Brotherhood', 'Celestial Chorus', 'Cult of Ecstasy', 'Dream Speakers',
  'Euthanatos', 'Order of Hermes', 'Sons of Ether', 'Verbena', 'Virtual Adepts',
];

/** Classic oWoD-style Nature / Demeanor archetypes (Revised-era sheet lists). */
const WOD_ARCHETYPES = [
  'Architect',
  'Autocrat',
  'Bon Vivant',
  'Bravo',
  'Bureaucrat',
  'Caregiver',
  'Celebrant',
  'Child',
  'Competitor',
  'Conformist',
  'Conniver',
  'Curmudgeon',
  'Deviant',
  'Director',
  'Fanatic',
  'Gallant',
  'Judge',
  'Loner',
  'Martyr',
  'Masochist',
  'Monster',
  'Pedagogue',
  'Penitent',
  'Perfectionist',
  'Rebel',
  'Rogue',
  'Sadist',
  'Scientist',
  'Sociopath',
  'Survivor',
  'Thrill-Seeker',
  'Traditionalist',
  'Trickster',
  'Visionary',
];

const ARCHETYPE_CUSTOM = '__custom__';

const MTA_SPHERES = [
  ['correspondence', 'Correspondence'],
  ['entropy', 'Entropy'],
  ['forces', 'Forces'],
  ['life', 'Life'],
  ['matter', 'Matter'],
  ['mind', 'Mind'],
  ['prime', 'Prime'],
  ['spirit', 'Spirit'],
  ['time', 'Time'],
];

const DISCIPLINE_PRESETS = [
  'Animalism',
  'Auspex',
  'Celerity',
  'Chimerstry',
  'Daimoinon',
  'Dementation',
  'Dominate',
  'Fortitude',
  'Melpominee',
  'Mortis',
  'Mytherceria',
  'Necromancy',
  'Obfuscate',
  'Obeah',
  'Potence',
  'Presence',
  'Protean',
  'Quietus',
  'Sanguinus',
  'Serpentis',
  'Spiritus',
  'Temporis',
  'Thaumaturgy',
  'Valeren',
  'Vicissitude',
];

function emptyAttrMap() {
  const o = {};
  [...PHYSICAL, ...SOCIAL, ...MENTAL].forEach((k) => {
    o[k] = 1;
  });
  return o;
}

function emptyAbilityMap() {
  const o = {};
  [...TALENTS, ...SKILLS, ...KNOWLEDGES].forEach(([k]) => {
    o[k] = 0;
  });
  return o;
}

function emptySphereMap() {
  const o = {};
  MTA_SPHERES.forEach(([k]) => {
    o[k] = 0;
  });
  return o;
}

function validateAttributeSpread(attrs, pools) {
  const sum = (keys) => keys.reduce((s, k) => s + (parseInt(attrs[k], 10) || 0), 0);
  const p = sum(PHYSICAL);
  const s = sum(SOCIAL);
  const m = sum(MENTAL);
  if (p !== pools.physical) return `Physical attributes must total ${pools.physical} (currently ${p}).`;
  if (s !== pools.social) return `Social attributes must total ${pools.social} (currently ${s}).`;
  if (m !== pools.mental) return `Mental attributes must total ${pools.mental} (currently ${m}).`;
  for (const k of [...PHYSICAL, ...SOCIAL, ...MENTAL]) {
    const v = parseInt(attrs[k], 10);
    if (Number.isNaN(v) || v < 1 || v > 5) {
      return `Each attribute must be between 1 and 5 (${k}).`;
    }
  }
  return null;
}

function sumAbilitiesInCategory(abilities, keys) {
  return keys.reduce((s, [k]) => s + (parseInt(abilities[k], 10) || 0), 0);
}

function validateAbilitySpread(abilities, pools) {
  const t = sumAbilitiesInCategory(abilities, TALENTS);
  const sk = sumAbilitiesInCategory(abilities, SKILLS);
  const kn = sumAbilitiesInCategory(abilities, KNOWLEDGES);
  if (t !== pools.talents) return `Talents must total ${pools.talents} dots (currently ${t}).`;
  if (sk !== pools.skills) return `Skills must total ${pools.skills} dots (currently ${sk}).`;
  if (kn !== pools.knowledges) return `Knowledges must total ${pools.knowledges} dots (currently ${kn}).`;
  for (const [k] of [...TALENTS, ...SKILLS, ...KNOWLEDGES]) {
    const v = parseInt(abilities[k], 10);
    if (Number.isNaN(v) || v < 0 || v > 5) {
      return `Each ability must be between 0 and 5 (${k}).`;
    }
  }
  return null;
}

function validateVirtues(v) {
  const c = parseInt(v.conscience, 10) || 0;
  const sc = parseInt(v.self_control, 10) || 0;
  const co = parseInt(v.courage, 10) || 0;
  if (c < 1 || c > 5 || sc < 1 || sc > 5 || co < 1 || co > 5) {
    return 'Each virtue must be between 1 and 5.';
  }
  if (c + sc + co !== 7) {
    return 'Virtues must total exactly 7 dots (Revised neonate spread), each at least 1.';
  }
  return null;
}

function validateSpheres(spheres) {
  let t = 0;
  for (const [k] of MTA_SPHERES) {
    const v = parseInt(spheres[k], 10) || 0;
    if (v < 0 || v > 5) return `Sphere ${k} must be 0–5.`;
    t += v;
  }
  if (t !== 6) return `Allocate exactly 6 sphere dots at creation (currently ${t}).`;
  return null;
}

/**
 * Clickable WoD-style dot track (filled circles). `maxRank` is usually 5.
 */
function DotTrack({ value, maxRank, onChange, disabled, accent }) {
  const rank = Math.max(0, Math.min(maxRank, parseInt(value, 10) || 0));
  const a = accent || '#c4b5fd';
  return (
    <div
      role="group"
      aria-label={`Rating ${rank} of ${maxRank}`}
      style={{ display: 'flex', alignItems: 'center', gap: '5px', flexWrap: 'nowrap' }}
    >
      {Array.from({ length: maxRank }, (_, i) => {
        const n = i + 1;
        const filled = n <= rank;
        return (
          <button
            key={n}
            type="button"
            disabled={disabled}
            onClick={() => onChange(filled && n === rank ? n - 1 : n)}
            title={`Set to ${n}`}
            style={{
              width: '18px',
              height: '18px',
              minWidth: '18px',
              padding: 0,
              borderRadius: '50%',
              border: `2px solid ${filled ? a : '#4b5568'}`,
              background: filled
                ? `radial-gradient(circle at 30% 30%, ${a}, #5b21b6)`
                : 'transparent',
              cursor: disabled ? 'not-allowed' : 'pointer',
              boxShadow: filled ? `0 0 8px ${a}55` : 'none',
              transition: 'transform 0.12s ease, box-shadow 0.12s ease',
            }}
            onMouseDown={(e) => e.preventDefault()}
          />
        );
      })}
    </div>
  );
}

function SheetSection({ title, subtitle, children, accent }) {
  return (
    <div
      style={{
        marginBottom: '22px',
        padding: '16px 14px',
        background: 'linear-gradient(165deg, rgba(15,23,41,0.95) 0%, rgba(22,33,62,0.85) 100%)',
        border: '1px solid #2a2a4e',
        borderRadius: '10px',
        boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04)',
      }}
    >
      <div
        style={{
          borderBottom: `1px solid ${accent || '#e94560'}44`,
          paddingBottom: '10px',
          marginBottom: '14px',
        }}
      >
        <h3
          style={{
            margin: 0,
            fontFamily: 'Cinzel, serif',
            fontSize: '16px',
            color: accent || '#e94560',
            letterSpacing: '0.06em',
            textTransform: 'uppercase',
          }}
        >
          {title}
        </h3>
        {subtitle ? (
          <p style={{ margin: '6px 0 0', fontSize: '12px', color: '#8b8b9f' }}>{subtitle}</p>
        ) : null}
      </div>
      {children}
    </div>
  );
}

function AttributeColumns({ attrs, setAttrs, pools }) {
  const col = (title, keys, pool, accent) => (
    <div style={{ flex: '1 1 200px', minWidth: 0 }}>
      <div
        style={{
          textAlign: 'center',
          fontFamily: 'Cinzel, serif',
          fontSize: '12px',
          color: accent,
          marginBottom: '12px',
          letterSpacing: '0.08em',
        }}
      >
        {title}
        <span style={{ color: '#6b7280', fontFamily: 'system-ui', marginLeft: '6px' }}>
          ({pool} pts)
        </span>
      </div>
      {keys.map((k) => (
        <div
          key={k}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '10px',
            marginBottom: '10px',
            padding: '6px 8px',
            background: 'rgba(0,0,0,0.2)',
            borderRadius: '6px',
          }}
        >
          <span
            style={{
              color: '#d1d5db',
              fontSize: '13px',
              textTransform: 'capitalize',
              flex: '1 1 auto',
            }}
          >
            {k}
          </span>
          <DotTrack
            value={attrs[k]}
            maxRank={5}
            accent={accent}
            onChange={(n) => {
              const keysAll = [...PHYSICAL, ...SOCIAL, ...MENTAL];
              const catKeys =
                title === 'Physical' ? PHYSICAL : title === 'Social' ? SOCIAL : MENTAL;
              const poolSize =
                title === 'Physical'
                  ? pools.physical
                  : title === 'Social'
                    ? pools.social
                    : pools.mental;
              const old = parseInt(attrs[k], 10) || 1;
              const next = Math.max(1, Math.min(5, n));
              const delta = next - old;
              const sum = catKeys.reduce((s, key) => s + (parseInt(attrs[key], 10) || 1), 0);
              if (sum + delta > poolSize) return;
              setAttrs((prev) => ({ ...prev, [k]: next }));
            }}
          />
        </div>
      ))}
    </div>
  );

  return (
    <div
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: '18px',
        justifyContent: 'space-between',
      }}
    >
      {col('Physical', PHYSICAL, pools.physical, '#f87171')}
      {col('Social', SOCIAL, pools.social, '#a78bfa')}
      {col('Mental', MENTAL, pools.mental, '#38bdf8')}
    </div>
  );
}

function AbilityColumns({ abilities, setAbilities, pools }) {
  const setDot = (key, catKeys, poolSize, n) => {
    const old = parseInt(abilities[key], 10) || 0;
    const next = Math.max(0, Math.min(5, n));
    const delta = next - old;
    const sum = catKeys.reduce((s, [kk]) => s + (parseInt(abilities[kk], 10) || 0), 0);
    if (sum + delta > poolSize) return;
    setAbilities((prev) => ({ ...prev, [key]: next }));
  };

  const col = (title, list, pool, colAccent) => (
    <div style={{ flex: '1 1 220px', minWidth: 0 }}>
      <div
        style={{
          textAlign: 'center',
          fontFamily: 'Cinzel, serif',
          fontSize: '12px',
          color: colAccent,
          marginBottom: '12px',
          letterSpacing: '0.08em',
        }}
      >
        {title}
        <span style={{ color: '#6b7280', fontFamily: 'system-ui', marginLeft: '6px' }}>
          ({pool} dots)
        </span>
      </div>
      {list.map(([k, label]) => (
        <div
          key={k}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '8px',
            marginBottom: '8px',
            padding: '5px 6px',
            background: 'rgba(0,0,0,0.18)',
            borderRadius: '6px',
          }}
        >
          <span style={{ color: '#c4c4d4', fontSize: '12px', flex: '1 1 auto' }}>{label}</span>
          <DotTrack
            value={abilities[k]}
            maxRank={5}
            accent={colAccent}
            onChange={(n) => setDot(k, list, pool, n)}
          />
        </div>
      ))}
    </div>
  );

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '18px', justifyContent: 'space-between' }}>
      {col('Talents', TALENTS, pools.talents, '#fbbf24')}
      {col('Skills', SKILLS, pools.skills, '#34d399')}
      {col('Knowledges', KNOWLEDGES, pools.knowledges, '#818cf8')}
    </div>
  );
}

/**
 * Multi-step oWoD-oriented character creator (Vampire / Werewolf / Mage campaigns).
 * Dot-pool UX and three-column abilities inspired by classic Revised-era sheets.
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

  const maxStep = 4;

  const [step, setStep] = useState(0);
  const [campaignId, setCampaignId] = useState(
    eligible[0]?.id != null ? String(eligible[0].id) : ''
  );
  const [name, setName] = useState('');
  const [concept, setConcept] = useState('');
  const [priority, setPriority] = useState('physical');
  const [attrs, setAttrs] = useState(() => emptyAttrMap());
  const [abilityPriority, setAbilityPriority] = useState('talents');
  const [abilities, setAbilities] = useState(() => emptyAbilityMap());
  const [background, setBackground] = useState('');
  const [meritsFlawsNotes, setMeritsFlawsNotes] = useState('');

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

  const [tradition, setTradition] = useState(MTA_TRADITIONS[0]);
  const [spheres, setSpheres] = useState(() => emptySphereMap());

  const [submitting, setSubmitting] = useState(false);

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
        .map((d) => ({ name: String(d.name).trim(), dots: Math.min(5, Math.max(0, parseInt(d.dots, 10) || 0)) }));
      const bgClean = backgrounds
        .filter((b) => b.name && String(b.name).trim())
        .map((b) => ({ name: String(b.name).trim(), dots: Math.min(5, Math.max(0, parseInt(b.dots, 10) || 0)) }));
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
      return { ...base, breed, auspice, tribe };
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

  const handleSubmit = async () => {
    if (!campaign) {
      showError?.('Choose a chronicle.');
      return;
    }
    const cidNum = parseInt(campaignId, 10);
    if (!Number.isFinite(cidNum) || cidNum < 1) {
      showError?.('Choose a valid chronicle.');
      return;
    }
    const nm = name.trim();
    if (!nm) {
      showError?.('Character name is required.');
      return;
    }
    if (['vampire', 'werewolf', 'mage'].includes(systemType)) {
      if (naturePick === ARCHETYPE_CUSTOM && !(natureCustom || '').trim()) {
        showError?.('Enter your Nature (free text), or pick a preset archetype.');
        return;
      }
      if (demeanorPick === ARCHETYPE_CUSTOM && !(demeanorCustom || '').trim()) {
        showError?.('Enter your Demeanor (free text), or pick a preset archetype.');
        return;
      }
    }
    const errA = validateAttributeSpread(attrs, pools);
    if (errA) {
      showError?.(errA);
      return;
    }
    const errAb = validateAbilitySpread(abilities, abilityPools);
    if (errAb) {
      showError?.(errAb);
      return;
    }

    if (systemType === 'vampire') {
      const vErr = validateVirtues(virtues);
      if (vErr) {
        showError?.(vErr);
        return;
      }
      const dSum = disciplines.reduce((s, d) => s + (parseInt(d.dots, 10) || 0), 0);
      if (dSum > 3) {
        showError?.('Discipline dots at creation are usually 3 total for a neonate — lower some ratings or clear extras.');
        return;
      }
      const bgSum = backgrounds.reduce((s, b) => s + (parseInt(b.dots, 10) || 0), 0);
      if (bgSum > 5) {
        showError?.('Background dots total more than 5 (typical starting pool). Adjust before sealing the sheet.');
        return;
      }
    }

    if (systemType === 'mage') {
      const sErr = validateSpheres(spheres);
      if (sErr) {
        showError?.(sErr);
        return;
      }
    }

    const skillsPayload = {
      talents: Object.fromEntries(TALENTS.map(([k]) => [k, parseInt(abilities[k], 10) || 0])),
      skills: Object.fromEntries(SKILLS.map(([k]) => [k, parseInt(abilities[k], 10) || 0])),
      knowledges: Object.fromEntries(KNOWLEDGES.map(([k]) => [k, parseInt(abilities[k], 10) || 0])),
      allocation: {
        primary: abilityPriority,
        pools: abilityPools,
      },
      notes: '',
    };

    const meritsPayload = meritsFlawsNotes.trim()
      ? { notes: meritsFlawsNotes.trim() }
      : {};

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

  const miniHeader = step >= 2 && (
    <div
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: '12px 24px',
        padding: '12px 14px',
        marginBottom: '16px',
        background: 'rgba(233,69,96,0.08)',
        border: '1px solid #2a2a4e',
        borderRadius: '8px',
        fontSize: '13px',
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
  );

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
    <div style={{ maxWidth: '960px', margin: '0 auto', padding: '20px 16px 60px' }}>
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
            three-column abilities (Revised-era style). This is not a full replacement for your
            corebook—your Storyteller has final say on numbers and templates.
          </p>
          <div style={{ marginTop: '10px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            {['Identity', 'Template', 'Attributes', 'Abilities', 'Advantages & seal'].map(
              (label, i) => (
                <span
                  key={label}
                  style={{
                    fontSize: '11px',
                    padding: '4px 10px',
                    borderRadius: '999px',
                    background: step === i ? `${themeAccent}33` : '#1e293b',
                    color: step === i ? themeAccent : '#64748b',
                    border: `1px solid ${step === i ? themeAccent : '#334155'}`,
                  }}
                >
                  {i + 1}. {label}
                </span>
              )
            )}
          </div>
        </div>

        <div style={{ padding: '16px' }}>
          {miniHeader}

          {step === 0 && (
            <SheetSection title="Identity" subtitle="Chronicle and character hook" accent={themeAccent}>
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
            </SheetSection>
          )}

          {step === 1 && systemType === 'vampire' && (
            <SheetSection title="Kindred template" accent={themeAccent}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '14px' }}>
                <div>
                  <label style={{ color: '#c4b5fd', display: 'block', marginBottom: '6px' }}>Clan</label>
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
                  <label style={{ color: '#c4b5fd', display: 'block', marginBottom: '6px' }}>Generation</label>
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
            </SheetSection>
          )}

          {step === 1 && systemType === 'werewolf' && (
            <SheetSection title="Garou template" accent={themeAccent}>
              <label style={{ color: '#c4b5fd', display: 'block', marginBottom: '8px' }}>Breed</label>
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
              <label style={{ color: '#c4b5fd', display: 'block', marginBottom: '8px' }}>Auspice</label>
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
              <label style={{ color: '#c4b5fd', display: 'block', marginBottom: '8px' }}>Tribe</label>
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
            </SheetSection>
          )}

          {step === 1 && systemType === 'mage' && (
            <SheetSection title="Mage template" accent={themeAccent}>
              <label style={{ color: '#c4b5fd', display: 'block', marginBottom: '8px' }}>Tradition</label>
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
                Arete starts at 1. You will assign six sphere dots on the last step.
              </p>
            </SheetSection>
          )}

          {step === 1 && ['vampire', 'werewolf', 'mage'].includes(systemType) && (
            <SheetSection
              title="Nature & demeanor"
              subtitle="Classic oWoD-style archetypes (Revised-era lists). Pick Custom to type your own — for another game line or a Storyteller-specific list."
              accent={themeAccent}
            >
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
                  gap: '16px',
                }}
              >
                <div>
                  <label style={{ color: '#c4b5fd', display: 'block', marginBottom: '6px' }}>Nature</label>
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
                  <label style={{ color: '#c4b5fd', display: 'block', marginBottom: '6px' }}>Demeanor</label>
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
            </SheetSection>
          )}

          {step === 2 && (
            <SheetSection
              title="Attributes"
              subtitle="7 / 5 / 3 across Physical, Social, Mental — click dots to set each trait (minimum 1)."
              accent={themeAccent}
            >
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
            </SheetSection>
          )}

          {step === 3 && (
            <SheetSection
              title="Abilities"
              subtitle="11 / 7 / 4 across Talents, Skills, Knowledges (Revised-style). Click dots; pool caps prevent overspending."
              accent={themeAccent}
            >
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
              />
            </SheetSection>
          )}

          {step === 4 && (
            <>
              {systemType === 'vampire' && (
                <SheetSection
                  title="Advantages — Vampire"
                  subtitle="Neonate defaults: 3 discipline dots, 5 background dots, virtues total 7 (each 1–5). Willpower and Humanity are editable for your table."
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
                            const others = next.reduce((s, x, j) => (j === i ? s : s + (parseInt(x.dots, 10) || 0)), 0);
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
                            const others = next.reduce((s, x, j) => (j === i ? s : s + (parseInt(x.dots, 10) || 0)), 0);
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
                          <span style={{ color: '#c4c4d4', fontSize: '12px', width: '140px' }}>{label}</span>
                          <DotTrack
                            value={virtues[key]}
                            maxRank={5}
                            accent="#f472b6"
                            onChange={(n) => {
                              const next = { ...virtues, [key]: String(n) };
                              setVirtues(next);
                            }}
                          />
                        </div>
                      ))}
                    </div>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: '12px' }}>
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
                  subtitle="Allocate exactly 6 dots among the nine spheres (Arete remains 1 at this stage)."
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
                  title="Garou notes"
                  subtitle="Gifts, Rage, and Gnosis follow your Storyteller and corebook—record anything you have already agreed on."
                  accent={themeAccent}
                >
                  <p style={{ color: '#8b8b9f', fontSize: '14px' }}>
                    Use the narrative box below for rank, starting Rage/Gnosis, or gift names once your table assigns them.
                  </p>
                </SheetSection>
              )}

              <SheetSection title="Story & optional merits" accent="#9d4edd">
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
                    marginBottom: '16px',
                    background: '#0f1729',
                    color: '#e0e0e0',
                    border: '2px solid #2a2a4e',
                    borderRadius: '8px',
                    resize: 'vertical',
                    fontFamily: 'Crimson Text, Georgia, serif',
                    lineHeight: 1.6,
                  }}
                />
                <label style={{ color: '#c4b5fd', display: 'block', marginBottom: '8px' }}>
                  Merits & flaws (free text)
                </label>
                <textarea
                  value={meritsFlawsNotes}
                  onChange={(e) => setMeritsFlawsNotes(e.target.value)}
                  rows={3}
                  placeholder="e.g. Eidetic Memory +2, Phobia (fire) -1 — ST-approved only"
                  style={{
                    width: '100%',
                    padding: '12px',
                    background: '#0f1729',
                    color: '#e0e0e0',
                    border: '2px solid #2a2a4e',
                    borderRadius: '8px',
                    resize: 'vertical',
                  }}
                />
              </SheetSection>
            </>
          )}

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
              onClick={step === 0 ? onCancel : () => setStep((s) => Math.max(0, s - 1))}
              style={{
                padding: '10px 18px',
                background: '#1e293b',
                color: '#e2e8f0',
                border: '1px solid #475569',
                borderRadius: '8px',
                cursor: 'pointer',
              }}
            >
              {step === 0 ? 'Cancel' : 'Back'}
            </button>
            {step < maxStep ? (
              <button
                type="button"
                onClick={() => setStep((s) => s + 1)}
                style={{
                  padding: '10px 22px',
                  background: `linear-gradient(135deg, ${themeAccent} 0%, #5b21b6 100%)`,
                  color: 'white',
                  border: 'none',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  fontWeight: 'bold',
                  fontFamily: 'Cinzel, serif',
                }}
              >
                Next
              </button>
            ) : (
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
            )}
          </div>
        </div>
      </GothicBox>
    </div>
  );
}
