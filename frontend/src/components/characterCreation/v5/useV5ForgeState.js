import { useMemo, useState } from 'react';
import { createEmptyMeritRow } from '../../../characterSheet/meritsFlaws';
import {
  THIN_BLOOD,
  V5_AGE_BRACKETS,
  V5_BACKGROUNDS,
  V5_DISCIPLINE_DOTS,
  V5_SKILL_DISTRIBUTIONS,
} from '../../../characterSheet/v5/constants';
import {
  ageAllowed,
  attributeSpreadStatus,
  bloodSorceryLevel,
  clanAllowed,
  clanInfo,
  creationDisciplineOptions,
  deriveV5,
  disciplineRows,
  emptyV5Attributes,
  emptyV5Skills,
  ownFlawDots,
  predatorDisciplineOptions,
  predatorInfo,
  skillSpreadStatus,
  startingXp,
  xpLedger,
} from '../../../characterSheet/v5/validation';
import { CREATION_AGES } from '../../../characterSheet/v5/creationSettings';
import { clanNames, disciplineNames } from '../../../characterSheet/v5/rulesData';

const isBackgroundName = (name) =>
  V5_BACKGROUNDS.some((b) => String(name || '').toLowerCase().startsWith(b.toLowerCase()));

const emptyDisciplines = () => [
  { name: '', level: V5_DISCIPLINE_DOTS[0], powers: [] },
  { name: '', level: V5_DISCIPLINE_DOTS[1], powers: [] },
];

/** Generation to start an age at: 13 where the age allows it, else its last (lowest) one. */
const generationFor = (age) => {
  const gens = V5_AGE_BRACKETS[age].generations;
  return gens.includes(13) ? 13 : gens[gens.length - 1];
};

/**
 * All state of the V5 forge, the sheet built from it (see characterSheet/v5/validation.js for its
 * shape) and the values derived from it. `settings` are the chronicle's creation settings
 * (normalised, see characterSheet/v5/creationSettings.js); `initial` overrides starting values
 * (the guided mode prefills through it).
 */
export default function useV5ForgeState(settings, initial = {}) {
  const firstClan =
    initial.clan || (clanAllowed(settings, 'Brujah') ? 'Brujah' : clanNames().find((c) => clanAllowed(settings, c)) || 'Brujah');
  // Thin-bloods are always childer of the 14th generation or later (the same as changeClan).
  const firstAge =
    firstClan === THIN_BLOOD
      ? 'childer'
      : initial.age || (ageAllowed(settings, 'neonate') ? 'neonate' : CREATION_AGES.find((a) => ageAllowed(settings, a)) || 'neonate');

  const [name, setName] = useState(initial.name || '');
  const [concept, setConcept] = useState(initial.concept || '');
  const [sire, setSire] = useState('');
  const [ambition, setAmbition] = useState('');
  const [desire, setDesire] = useState('');
  const [clan, setClan] = useState(firstClan);
  const [age, setAge] = useState(firstAge);
  const [generation, setGeneration] = useState(() => (firstClan === THIN_BLOOD ? 14 : generationFor(firstAge)));
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
  const dist = V5_SKILL_DISTRIBUTIONS[skillDistribution];

  const changeAge = (next) => {
    setAge(next);
    if (!V5_AGE_BRACKETS[next].xp) setXpPurchases([]);
    if (!V5_AGE_BRACKETS[next].generations.includes(Number(generation))) setGeneration(generationFor(next));
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
    discOptions: creationDisciplineOptions(clan, disciplineNames()),
    discRows: disciplineRows(sheet),
    predDiscOptions: predatorDisciplineOptions(predatorType, clan),
    dist,
    skillMax: Math.max(...Object.keys(dist.counts).map(Number)),
    attrStatus,
    skillStatus: skillSpreadStatus(skills, skillDistribution),
    advDots: advantages.reduce((s, a) => s + a.dots, 0),
    flawDots: ownFlawDots(sheet),
    // values and setters
    name, setName, concept, setConcept, sire, setSire, ambition, setAmbition, desire, setDesire,
    clan, changeClan, age, changeAge, generation, setGeneration,
    attributes, setAttributes, skillDistribution, setSkillDistribution, skills, setSkills,
    specialties, setSpecialties, disciplines, setDisc,
    predatorType, setPredatorType, predatorSpecialty, setPredatorSpecialty,
    predatorDiscipline, setPredatorDiscipline, predatorChoices, setPredatorChoices, extraPowers, setExtraPowers,
    startingRitual, setStartingRitual, startingCeremony, setStartingCeremony, meritRows, setMeritRows, meritNotes, setMeritNotes,
    convictions, setConvictions, tenets, setTenets, background, setBackground,
    fledglingHumanity, setFledglingHumanity, thinBloodMerits, setThinBloodMerits,
    thinBloodFlaws, setThinBloodFlaws, xpPurchases, setXpPurchases, xpDraft, setXpDraft,
    fieldErrors, setFieldErrors,
  };
}
