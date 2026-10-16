import { useState } from 'react';
import { ARCHETYPE_CUSTOM, WOD_ARCHETYPES } from '../../../characterSheet/constants';
import { createEmptyMeritRow } from '../../../characterSheet/meritsFlaws';
import {
  VIRTUE_TOTAL_AT_CREATION,
  emptyAbilityMap,
  emptyAttrMap,
  emptyVirtueFreebies,
  emptyVirtues,
} from '../../../characterSheet/validation';
import {
  BOND_START,
  deriveClassicGhoul,
  domitorBackgroundDots,
  domitorGeneration,
  ghoulAbilityPools,
  ghoulAttributePools,
  ghoulDisciplineOptions,
  rollStartingPool,
} from '../../../characterSheet/classicGhoul';

const int = (v) => parseInt(v, 10) || 0;

/** "Caregiver" / "Caregiver (her son)" / the custom text, as the Classic wizard stores them. */
export function resolveArchetype(pick, custom) {
  const text = (custom || '').trim();
  if (pick === ARCHETYPE_CUSTOM) return text;
  return text ? `${pick} (${text})` : pick;
}

/**
 * All state of the Classic ghoul forge and the sheet built from it (characterSheet/classicGhoul.js
 * reads `sheet`). `domitors`: the user's Classic vampires; `domitorId`: the one picked first (?ghoul_of=).
 * `rng`: the Blood Pool die (tests pass their own).
 */
export default function useClassicGhoulForgeState(domitors, domitorId, rng = Math.random) {
  const list = domitors || [];
  const first = list.find((d) => String(d.id) === String(domitorId)) || list[0] || null;
  const [domitorKey, setDomitorKey] = useState(first ? String(first.id) : '');
  const domitor = list.find((d) => String(d.id) === domitorKey) || null;
  const generation = domitorGeneration(domitor);

  const [name, setName] = useState('');
  const [concept, setConcept] = useState('');
  const [kind, setKindRaw] = useState('vassal');
  const [naturePick, setNaturePick] = useState(WOD_ARCHETYPES[0]);
  const [natureCustom, setNatureCustom] = useState('');
  const [demeanorPick, setDemeanorPick] = useState(WOD_ARCHETYPES[0]);
  const [demeanorCustom, setDemeanorCustom] = useState('');
  const [duties, setDuties] = useState('');
  const [ghouledSince, setGhouledSince] = useState('');
  const [age, setAge] = useState('');
  const [apparentAge, setApparentAge] = useState('');
  const [attrPriority, setAttrPriority] = useState('physical');
  const [attributes, setAttributes] = useState(() => emptyAttrMap());
  const [abilityPriority, setAbilityPriority] = useState('talents');
  const [abilities, setAbilities] = useState(() => emptyAbilityMap());
  const [customAbilities, setCustomAbilities] = useState({ talents: [], skills: [], knowledges: [] });
  // row 0 is Potence (every ghoul has it, Revised p. 276); row 1 the one other Discipline; row 2 a freebie one
  const [disciplines, setDisciplines] = useState([
    { name: 'Potence', dots: 1 },
    { name: '', dots: 0 },
    { name: '', dots: 0 },
  ]);
  // the Domitor Background starts at what the domitor's generation gives (editable)
  const [backgrounds, setBackgrounds] = useState(() => [
    { name: 'Domitor', dots: first ? domitorBackgroundDots(domitorGeneration(first)) : 1 },
    { name: '', dots: 0 },
    { name: '', dots: 0 },
    { name: '', dots: 0 },
    { name: '', dots: 0 },
  ]);
  const [virtues, setVirtues] = useState(() => emptyVirtues());
  const [virtueFreebies, setVirtueFreebies] = useState(() => emptyVirtueFreebies());
  const [humanityBonus, setHumanityBonus] = useState(0);
  const [willpowerBonus, setWillpowerBonus] = useState(0);
  const [freebieMode, setFreebieMode] = useState(false);
  const [bloodPool, setBloodPool] = useState(null);
  const [lastRoll, setLastRoll] = useState(null);
  const [bondStage, setBondStage] = useState(BOND_START.vassal);
  const [bondNote, setBondNote] = useState('');
  const [feedingLast, setFeedingLast] = useState('');
  const [feedingNote, setFeedingNote] = useState('');
  const [overdosing, setOverdosing] = useState('');
  const [meritRows, setMeritRows] = useState(() => [createEmptyMeritRow()]);
  const [meritNotes, setMeritNotes] = useState('');
  const [background, setBackground] = useState('');
  const [fieldErrors, setFieldErrors] = useState({});

  const disciplineOptions = ghoulDisciplineOptions(domitor, kind);

  /** Vassal / independent: the Blood Bond starts at 3 drinks / none (Fatal Addiction), the roll again. */
  const setKind = (k) => {
    setKindRaw(k);
    setBondStage(BOND_START[k] ?? 0);
    setLastRoll(null);
    setBloodPool(null);
    const allowed = ghoulDisciplineOptions(domitor, k);
    setDisciplines((prev) => prev.map((d, i) => (i > 0 && d.name && !allowed.includes(d.name) ? { name: '', dots: 0 } : d)));
    // Fatal Addiction p. 65: vassals buy the Domitor Background; an independent ghoul has no master
    if (k === 'vassal') {
      setBackgrounds((prev) => (prev.some((b) => b.name === 'Domitor') || prev[0]?.name ? prev : prev.map((b, i) => (i === 0 ? { name: 'Domitor', dots: domitorBackgroundDots(domitorGeneration(domitor)) } : b))));
    } else {
      setBackgrounds((prev) => prev.map((b) => (String(b.name).trim().toLowerCase() === 'domitor' ? { name: '', dots: 0 } : b)));
    }
  };

  /** Another of the user's Classic vampires: its Domitor Background and Disciplines follow. */
  const setDomitorId = (id) => {
    setDomitorKey(String(id));
    const next = list.find((d) => String(d.id) === String(id)) || null;
    setBackgrounds((prev) => prev.map((b, i) => (i === 0 && b.name === 'Domitor' ? { ...b, dots: domitorBackgroundDots(domitorGeneration(next)) } : b)));
    const allowed = ghoulDisciplineOptions(next, kind);
    setDisciplines((prev) => prev.map((d, i) => (i > 0 && d.name && !allowed.includes(d.name) ? { name: '', dots: 0 } : d)));
  };

  const rollPool = () => {
    const r = rollStartingPool(kind, rng);
    setLastRoll(r);
    setBloodPool(r.pool);
  };

  const virtueTotal = ['conscience', 'self_control', 'courage'].reduce((s, k) => s + int(virtues[k]), 0);
  /** As the Classic wizard: raising fills the creation budget (10) first, then (freebie mode) buys dots. */
  const setVirtueFinal = (key, n) => {
    const creation = int(virtues[key]) || 1;
    const bought = int(virtueFreebies[key]);
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

  const sheet = {
    name,
    concept,
    kind,
    nature: resolveArchetype(naturePick, natureCustom),
    demeanor: resolveArchetype(demeanorPick, demeanorCustom),
    duties,
    ghouledSince,
    age,
    apparentAge,
    attrPriority,
    attributes,
    abilityPriority,
    abilities,
    customAbilities,
    disciplines,
    backgrounds,
    virtues,
    virtueFreebies,
    humanityBonus,
    willpowerBonus,
    bloodPool,
    bondStage,
    bondNote,
    feedingLast,
    feedingNote,
    overdosing,
    meritRows,
    meritNotes,
  };
  const derived = deriveClassicGhoul(sheet);

  return {
    domitors: list,
    domitor,
    domitorId: domitorKey,
    setDomitorId,
    generation,
    disciplineOptions,
    name,
    setName,
    concept,
    setConcept,
    kind,
    setKind,
    naturePick,
    setNaturePick,
    natureCustom,
    setNatureCustom,
    demeanorPick,
    setDemeanorPick,
    demeanorCustom,
    setDemeanorCustom,
    duties,
    setDuties,
    ghouledSince,
    setGhouledSince,
    age,
    setAge,
    apparentAge,
    setApparentAge,
    attrPriority,
    setAttrPriority,
    attrPools: ghoulAttributePools(attrPriority),
    attributes,
    setAttributes,
    abilityPriority,
    setAbilityPriority,
    abilityPools: ghoulAbilityPools(abilityPriority),
    abilities,
    setAbilities,
    customAbilities,
    setCustomAbilities,
    disciplines,
    setDisciplines,
    backgrounds,
    setBackgrounds,
    virtues,
    virtueFreebies,
    virtueTotal,
    setVirtueFinal,
    humanityBonus,
    setHumanityBonus,
    willpowerBonus,
    setWillpowerBonus,
    freebieMode,
    setFreebieMode,
    bloodPool,
    setBloodPool,
    lastRoll,
    rollPool,
    bondStage,
    setBondStage,
    bondNote,
    setBondNote,
    feedingLast,
    setFeedingLast,
    feedingNote,
    setFeedingNote,
    overdosing,
    setOverdosing,
    meritRows,
    setMeritRows,
    meritNotes,
    setMeritNotes,
    background,
    setBackground,
    fieldErrors,
    setFieldErrors,
    sheet,
    derived,
  };
}
