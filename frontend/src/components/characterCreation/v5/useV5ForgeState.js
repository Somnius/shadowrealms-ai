import { useEffect, useMemo, useState } from 'react';
import { createEmptyMeritRow } from '../../../characterSheet/meritsFlaws';
import {
  THIN_BLOOD,
  V5_AGE_BRACKETS,
  V5_BACKGROUNDS,
  V5_DISCIPLINE_DOTS,
  V5_SKILL_DISTRIBUTIONS,
  startingGeneration,
} from '../../../characterSheet/v5/constants';
import {
  attributeSpreadStatus,
  bloodSorceryLevel,
  clanAllowed,
  clanInBooks,
  clanInfo,
  creationDisciplineOptions,
  defaultCreationAge,
  deriveV5,
  disciplineRows,
  emptyV5Attributes,
  emptyV5Skills,
  ownFlawDots,
  predatorDisciplineOptions,
  predatorInfo,
  savedAtCreation,
  skillSpreadStatus,
  startingCeremonyOptions,
  startingXp,
  xpLedger,
} from '../../../characterSheet/v5/validation';
import {
  advantageEntries,
  clanNames,
  disciplineNames,
  findAdvantage,
  findLoresheet,
} from '../../../characterSheet/v5/rulesData';

// Free-text rows (no catalog): a Background is told apart by its name.
const isBackgroundName = (name) =>
  V5_BACKGROUNDS.some((b) => String(name || '').toLowerCase().startsWith(b.toLowerCase()));

let rowSeq = 0;
/** A new Advantage/Flaw row of the catalog forge: id '' (nothing chosen yet), a catalog id or 'custom'. */
export const newAdvRow = (kind) => ({ key: `adv${(rowSeq += 1)}`, kind, id: '', name: '', dots: 0, note: '' });
/** A new loresheet row: the sheet's id and the levels taken (each level is bought on its own). */
export const newLoreRow = () => ({ key: `lore${(rowSeq += 1)}`, id: '', levels: [] });

/**
 * Free-text rows typed before the catalog loaded, as catalog-forge rows: a catalog entry when the
 * name matches one, else a custom row (nothing typed is lost).
 */
export function meritRowsToAdvRows(meritRows) {
  return (meritRows || [])
    .filter((r) => String(r.name || '').trim() && Number(r.points))
    .map((r) => {
      const points = Number(r.points);
      const name = String(r.name).trim();
      const flaw = points < 0;
      const found = findAdvantage({ name }, flaw ? 'flaw' : 'merit');
      const e = found && !found.thin_blood ? found : null;
      // "Allies (police)": the bracket becomes the note of the catalog row
      const bracket = name.match(/\(([^)]*)\)\s*$/);
      return {
        ...newAdvRow(e ? e.kind : flaw ? 'flaw' : isBackgroundName(name) ? 'background' : 'merit'),
        id: e ? e.id : 'custom',
        name: e ? e.name : name,
        dots: Math.abs(points),
        note: String(r.note || '').trim() || (e && bracket ? bracket[1].trim() : ''),
      };
    });
}

/**
 * Catalog-forge rows → sheet rows ({id, name, dots, kind, note} or {name, dots, kind, custom}). A
 * row whose id the catalog doesn't know is found by its name, else kept as a custom row.
 */
function catalogRows(advRows, loreRows) {
  const toRow = (r) => {
    const name = String(r.name || '').trim();
    const e = r.id && r.id !== 'custom' ? findAdvantage({ id: r.id, name }, r.kind) : null;
    if (e) return { id: e.id, name: e.name, dots: Number(r.dots) || 0, kind: e.kind, note: r.note };
    if (!name || (!r.id && !r.custom)) return null; // nothing chosen yet
    return { name, dots: Number(r.dots) || 0, kind: r.kind, note: r.note, custom: true };
  };
  const advantages = advRows.filter((r) => r.kind !== 'flaw').map(toRow).filter(Boolean);
  loreRows.forEach((r) => {
    const l = r.id ? findLoresheet({ id: r.id, name: r.name }) : null;
    if (!l) return;
    const levels = [...r.levels].sort((a, b) => a - b);
    advantages.push({ id: l.id, name: l.name, dots: levels.reduce((sum, n) => sum + n, 0), kind: 'loresheet', levels });
  });
  const flaws = advRows.filter((r) => r.kind === 'flaw').map(toRow).filter(Boolean);
  return { advantages, flaws };
}

const emptyDisciplines = () => [
  { name: '', level: V5_DISCIPLINE_DOTS[0], powers: [] },
  { name: '', level: V5_DISCIPLINE_DOTS[1], powers: [] },
];

/**
 * All state of the V5 forge, the sheet built from it (see characterSheet/v5/validation.js for its
 * shape) and the values derived from it. `settings` are the chronicle's creation settings
 * (normalised, see characterSheet/v5/creationSettings.js); `initial` overrides starting values
 * (the guided mode prefills through it).
 */
export default function useV5ForgeState(settings, initialValues) {
  const initial = initialValues || {};
  const offered = (c) => clanAllowed(settings, c) && clanInBooks(settings, c);
  const firstClan = initial.clan || (offered('Brujah') ? 'Brujah' : clanNames().find(offered) || 'Brujah');
  // Thin-bloods are always childer of the 14th generation or later (the same as changeClan).
  const firstAge = firstClan === THIN_BLOOD ? 'childer' : initial.age || defaultCreationAge(settings);

  const [name, setName] = useState(initial.name || '');
  const [concept, setConcept] = useState(initial.concept || '');
  const [sire, setSire] = useState('');
  const [ambition, setAmbition] = useState('');
  const [desire, setDesire] = useState('');
  const [clan, setClan] = useState(firstClan);
  const [age, setAge] = useState(firstAge);
  const [generation, setGeneration] = useState(() => (firstClan === THIN_BLOOD ? 14 : startingGeneration(firstAge)));
  const [attributes, setAttributes] = useState(() => initial.attributes || emptyV5Attributes());
  const [skillDistribution, setSkillDistribution] = useState(initial.skillDistribution || 'balanced');
  const [skills, setSkills] = useState(() => initial.skills || emptyV5Skills());
  const [specialties, setSpecialties] = useState([{ skill: '', name: '' }]);
  const [disciplines, setDisciplines] = useState(emptyDisciplines);
  const [predatorType, setPredatorTypeRaw] = useState(initial.predatorType || '');
  const [predatorSpecialty, setPredatorSpecialty] = useState(null);
  const [predatorDiscipline, setPredatorDiscipline] = useState('');
  // The player's picks among the predator type's grants (see resolvePredatorGrants).
  const [predatorChoices, setPredatorChoices] = useState({});
  // Powers for a predator Discipline that isn't one of the two picks: { [discipline]: [power] }.
  const [extraPowers, setExtraPowers] = useState({});
  // One optional Level 1 ritual with Blood Sorcery 1+ (V5.md §4 step 6).
  const [startingRitual, setStartingRitual] = useState('');
  // One optional Level 1 Oblivion ceremony whose prerequisite power is taken (Players Guide p. 91).
  const [startingCeremony, setStartingCeremony] = useState('');
  // Without the catalog: free-text rows (the same rows as the Classic forge).
  const [meritRows, setMeritRows] = useState(() => [createEmptyMeritRow()]);
  const [meritNotes, setMeritNotes] = useState('');
  // With the catalog: Backgrounds, Merits and Flaws (newAdvRow) and loresheets (newLoreRow).
  const [advRows, setAdvRows] = useState([]);
  const [loreRows, setLoreRows] = useState([]);
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

  // The catalog (once loaded) turns the step into dropdowns; until then, or without it, free text.
  const catalogAdvantages = advantageEntries().length > 0;
  // Rows typed before the catalog arrived move over to the dropdown rows (as custom rows when the
  // catalog doesn't know the name). Once moved, meritRows is empty again, so this runs once.
  useEffect(() => {
    if (!catalogAdvantages) return;
    const moved = meritRowsToAdvRows(meritRows);
    if (!moved.length) return;
    setAdvRows((prev) => [...prev, ...moved]);
    setMeritRows([createEmptyMeritRow()]);
  }, [catalogAdvantages, meritRows]);
  const { advantages, flaws } = catalogAdvantages
    ? catalogRows(advRows, loreRows)
    : {
        advantages: meritRows
          .filter((r) => String(r.name || '').trim() && Number(r.points) > 0)
          .map((r) => ({
            name: r.name,
            dots: Number(r.points),
            kind: isBackgroundName(r.name) ? 'background' : 'merit',
          })),
        flaws: meritRows
          .filter((r) => String(r.name || '').trim() && Number(r.points) < 0)
          .map((r) => ({ name: r.name, dots: -Number(r.points) })),
      };

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
    predatorChoices,
    extraPowers,
    startingRitual,
    startingCeremony,
    advantages,
    flaws,
    convictions,
    // The Humanity 8 start only counts where the Storyteller offers it.
    fledglingHumanity: fledglingHumanity && settings.fledgling_humanity_8,
    thinBloodMerits,
    thinBloodFlaws,
    xpPurchases,
  };

  const attrStatus = useMemo(() => attributeSpreadStatus(attributes), [attributes]);

  // A starting ceremony goes when its prerequisite Oblivion power (or Oblivion) does.
  const ceremonyNames = startingCeremonyOptions(sheet).map((c) => c.name).join('|');
  useEffect(() => {
    if (startingCeremony && !ceremonyNames.split('|').includes(startingCeremony)) setStartingCeremony('');
  }, [startingCeremony, ceremonyNames]);
  const dist = V5_SKILL_DISTRIBUTIONS[skillDistribution];

  const changeAge = (next) => {
    setAge(next);
    if (!V5_AGE_BRACKETS[next].xp) setXpPurchases([]);
    if (!V5_AGE_BRACKETS[next].generations.includes(Number(generation))) setGeneration(startingGeneration(next));
  };

  const changeClan = (next) => {
    setClan(next);
    setDisciplines(emptyDisciplines());
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

  /** A new predator type starts with no specialty, Discipline dot or extra powers chosen. */
  const setPredatorType = (next) => {
    setPredatorTypeRaw(next);
    setPredatorSpecialty(null);
    setPredatorDiscipline('');
    setPredatorChoices({});
    setExtraPowers({});
  };

  const setDisc = (i, patch) =>
    setDisciplines((prev) => prev.map((d, j) => (j === i ? { ...d, ...patch } : d)));

  return {
    settings,
    sheet,
    derived: deriveV5(sheet),
    xp: xpLedger(sheet, disciplineNames()),
    xpTotal: startingXp(sheet),
    bsLevel: bloodSorceryLevel(sheet),
    clanRow: clanInfo(clan),
    pred: predatorInfo(predatorType),
    // the forge's list: a Caitiff's picks from the chronicle's books (the check uses every Discipline)
    discOptions: creationDisciplineOptions(clan, disciplineNames(), settings),
    discRows: disciplineRows(sheet),
    predDiscOptions: predatorDisciplineOptions(predatorType, clan),
    dist,
    skillMax: Math.max(...Object.keys(dist.counts).map(Number)),
    attrStatus,
    skillStatus: skillSpreadStatus(skills, skillDistribution),
    advDots: advantages.reduce((s, a) => s + a.dots, 0),
    flawDots: ownFlawDots(sheet),
    saved: savedAtCreation(sheet, settings),
    // values and setters
    name, setName, concept, setConcept, sire, setSire, ambition, setAmbition, desire, setDesire,
    clan, changeClan, age, changeAge, generation, setGeneration,
    attributes, setAttributes, skillDistribution, setSkillDistribution, skills, setSkills,
    specialties, setSpecialties, disciplines, setDisc,
    predatorType, setPredatorType, predatorSpecialty, setPredatorSpecialty,
    predatorDiscipline, setPredatorDiscipline, predatorChoices, setPredatorChoices, extraPowers, setExtraPowers,
    startingRitual, setStartingRitual, startingCeremony, setStartingCeremony, meritRows, setMeritRows, meritNotes, setMeritNotes,
    catalogAdvantages, advRows, setAdvRows, loreRows, setLoreRows,
    convictions, setConvictions, tenets, setTenets, background, setBackground,
    fledglingHumanity, setFledglingHumanity, thinBloodMerits, setThinBloodMerits,
    thinBloodFlaws, setThinBloodFlaws, xpPurchases, setXpPurchases, xpDraft, setXpDraft,
    fieldErrors, setFieldErrors,
  };
}
