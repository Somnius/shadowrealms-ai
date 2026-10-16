/**
 * Definitions of the shared V5 creation test vectors (creation-cases.json next to this file, and
 * its copy docs/rules/v5/tests/creation-cases.json): forge sheets (the wizard state, see
 * ../validation.js) whose payload buildV5Payload() makes, and the problem codes both the client
 * and the server (backend/services/v5_chargen.py) report for them. `tamper` changes the payload
 * after it is built, for what the forge itself can't send (the client doesn't see those cases).
 *
 * The catalog is the snapshot stored in creation-cases.json. Regenerate the vectors after changing
 * this file or buildV5Payload: see scripts/v5_creation_cases.py.
 */
import { buildV5Payload, emptyV5Skills } from '../validation';

const ATTRS = {
  strength: 4,
  dexterity: 3,
  stamina: 3,
  charisma: 3,
  manipulation: 2,
  composure: 2,
  intelligence: 2,
  wits: 2,
  resolve: 1,
};

/** Skills from {rating: [keys]}. */
const skills = (byRating) => {
  const s = emptyV5Skills();
  Object.entries(byRating).forEach(([r, keys]) => keys.forEach((k) => (s[k] = Number(r))));
  return s;
};

const conviction = [{ conviction: 'Never harm a child', touchstone: 'Mia, my niece' }];

// ---------- valid sheets the forge makes ----------

/** Brujah Alleycat neonate: Brawl specialty from the type, Celerity dot outside the picks, 13 of 15 XP. */
const brujah = (over = {}) => ({
  name: 'Ada',
  concept: 'Bare-knuckle boxer',
  sire: 'Old Mags',
  ambition: 'Own the docks',
  desire: 'A clean fight tonight',
  chronicle_tenets: '',
  clan: 'Brujah',
  age: 'neonate',
  generation: 13,
  attributes: { ...ATTRS },
  skillDistribution: 'balanced',
  skills: skills({
    3: ['athletics', 'brawl', 'stealth'],
    2: ['drive', 'firearms', 'insight', 'persuasion', 'awareness'],
    1: ['melee', 'larceny', 'etiquette', 'streetwise', 'subterfuge', 'investigation', 'occult'],
  }),
  specialties: [{ skill: 'athletics', name: 'Parkour' }],
  disciplines: [
    { name: 'Potence', level: 2, powers: ['Lethal Body', 'Prowess'] },
    { name: 'Presence', level: 1, powers: ['Awe', 'Daunt'] },
  ],
  predatorType: 'Alleycat',
  predatorSpecialty: 1,
  predatorDiscipline: 'Celerity',
  predatorChoices: {},
  extraPowers: { Celerity: ['Rapid Reflexes'] },
  startingRitual: '',
  startingCeremony: '',
  advantages: [
    { name: 'Resources', dots: 3, kind: 'background' },
    { name: 'Haven', dots: 2, kind: 'background' },
    { name: 'Allies (dock workers)', dots: 2, kind: 'background' },
  ],
  flaws: [{ name: 'Enemy', dots: 2 }],
  convictions: conviction,
  fledglingHumanity: false,
  thinBloodMerits: [{ name: '' }],
  thinBloodFlaws: [{ name: '' }],
  xpPurchases: [
    { kind: 'discipline', trait: 'Presence' },
    { kind: 'skill', trait: 'intimidation' },
  ],
  ...over,
});

/** The same Brujah with no XP spent and one power per creation dot. */
const brujah0 = (over = {}) =>
  brujah({
    disciplines: [
      { name: 'Potence', level: 2, powers: ['Lethal Body', 'Prowess'] },
      { name: 'Presence', level: 1, powers: ['Awe'] },
    ],
    xpPurchases: [],
    ...over,
  });

/** Tremere Bagger (Blood Sorcery dot), starting ritual, XP ritual and an XP Dominate dot. */
const tremere = (over = {}) => ({
  ...brujah0(),
  name: 'Ilse',
  concept: 'Chantry archivist',
  clan: 'Tremere',
  generation: 12,
  skillDistribution: 'jack',
  skills: skills({
    3: ['occult'],
    2: ['academics', 'awareness', 'investigation', 'insight', 'persuasion', 'etiquette', 'stealth', 'larceny'],
    1: ['athletics', 'brawl', 'drive', 'firearms', 'streetwise', 'subterfuge', 'intimidation', 'finance', 'politics', 'science'],
  }),
  specialties: [
    { skill: 'academics', name: 'Hermetic texts' },
    { skill: 'science', name: 'Chemistry' },
    { skill: 'occult', name: 'Thaumaturgy' },
  ],
  disciplines: [
    { name: 'Blood Sorcery', level: 2, powers: ['A Taste for Blood', 'Extinguish Vitae', 'Blood of Potency'] },
    { name: 'Auspex', level: 1, powers: ['Heightened Senses'] },
  ],
  predatorType: 'Bagger',
  predatorSpecialty: 0,
  predatorDiscipline: 'Blood Sorcery',
  extraPowers: { Dominate: ['Cloud Memory'] },
  startingRitual: 'Blood Walk',
  advantages: [
    { name: 'Resources', dots: 2, kind: 'background' },
    { name: 'Mawla', dots: 2, kind: 'background' },
    { name: 'Status', dots: 1, kind: 'background' },
    { name: 'Contacts', dots: 2, kind: 'background' },
  ],
  flaws: [{ name: 'Dark Secret', dots: 2 }],
  xpPurchases: [
    { kind: 'ritual', trait: 'Calix Secretus', level: 2 },
    { kind: 'discipline', trait: 'Dominate' },
  ],
  ...over,
});

/** Hecata Grim Reaper (Oblivion dot), Allies from the type, free Summon Spirit ceremony. */
const hecata = (over = {}) => ({
  ...brujah0(),
  name: 'Livia',
  concept: 'Night-shift pathologist',
  clan: 'Hecata',
  skillDistribution: 'specialist',
  skills: skills({
    4: ['medicine'],
    3: ['occult', 'awareness', 'investigation'],
    2: ['insight', 'persuasion', 'stealth'],
    1: ['larceny', 'academics', 'drive'],
  }),
  specialties: [
    { skill: 'academics', name: 'Necromantic lore' },
    { skill: 'medicine', name: 'Pathology' },
  ],
  disciplines: [
    { name: 'Oblivion', level: 2, powers: ['The Binding Fetter', 'Shadow Cloak', 'Shadow Cast'] },
    { name: 'Fortitude', level: 1, powers: ['Resilience'] },
  ],
  predatorType: 'Grim Reaper',
  predatorSpecialty: 0,
  predatorDiscipline: 'Oblivion',
  predatorChoices: { a0: 0 },
  extraPowers: { Auspex: ['Sense the Unseen'] },
  startingCeremony: 'Summon Spirit',
  advantages: [
    { name: 'Haven', dots: 3, kind: 'background' },
    { name: 'Resources', dots: 2, kind: 'background' },
    { name: 'Herd', dots: 2, kind: 'background' },
  ],
  xpPurchases: [
    { kind: 'discipline', trait: 'Auspex' },
    { kind: 'attribute', trait: 'resolve' },
  ],
  ...over,
});

/** Caitiff Osiris: Performance at 0 becomes 1 (the type's specialty), split grants, Caitiff XP. */
const caitiff = (over = {}) => ({
  ...brujah0(),
  name: 'Brother Tomas',
  concept: 'Street preacher',
  clan: 'Caitiff',
  skills: skills({
    3: ['persuasion', 'occult', 'insight'],
    2: ['etiquette', 'subterfuge', 'awareness', 'academics', 'streetwise'],
    1: ['athletics', 'brawl', 'drive', 'stealth', 'larceny', 'investigation', 'intimidation'],
  }),
  specialties: [
    { skill: 'academics', name: 'Theology' },
    { skill: 'occult', name: 'Kabbalah' },
  ],
  disciplines: [
    { name: 'Presence', level: 2, powers: ['Awe', 'Lingering Kiss', 'Entrancement'] },
    { name: 'Animalism', level: 1, powers: ['Bond Famulus', 'Feral Whispers'] },
  ],
  predatorType: 'Osiris',
  predatorSpecialty: 1,
  predatorDiscipline: 'Presence',
  // the Mythic share is "any Mythic Flaw": the forge asks which (Folkloric Bane, 1 dot)
  predatorChoices: { a0: { 0: 2, 1: 1 }, f0: { 0: 1, 1: 1 }, 'f0:1:pick': 'flaw:folkloric-bane' },
  extraPowers: {},
  advantages: [
    { name: 'Resources', dots: 2, kind: 'background' },
    { name: 'Haven', dots: 2, kind: 'background' },
    { name: 'Contacts', dots: 3, kind: 'background' },
  ],
  flaws: [
    { name: 'Suspect', dots: 1 },
    { name: 'Addiction', dots: 1 },
  ],
  xpPurchases: [
    { kind: 'discipline', trait: 'Animalism' },
    { kind: 'specialty', skill: 'persuasion', trait: 'Sermons' },
  ],
  ...over,
});

/** Thin-blood fledgling: no predator type, no Disciplines, two thin-blood Merits and Flaws. */
const thinBlood = (over = {}) => ({
  ...brujah0(),
  name: 'Kit',
  concept: 'Night-bus driver',
  clan: 'Thin-blood',
  age: 'childer',
  generation: 14,
  skills: skills({
    3: ['athletics', 'stealth', 'streetwise'],
    2: ['brawl', 'drive', 'larceny', 'insight', 'awareness'],
    1: ['firearms', 'melee', 'persuasion', 'subterfuge', 'investigation', 'technology', 'intimidation'],
  }),
  specialties: [{ skill: 'streetwise', name: 'Squats' }],
  disciplines: [],
  predatorType: '',
  predatorSpecialty: null,
  predatorDiscipline: '',
  extraPowers: {},
  advantages: [
    { name: 'Resources', dots: 1, kind: 'background' },
    { name: 'Contacts', dots: 2, kind: 'background' },
  ],
  // Prey Exclusion is printed at 1 dot (core p. 181), so a second 1-dot Flaw makes the 2.
  flaws: [
    { name: 'Prey Exclusion (animals)', dots: 1 },
    { name: 'Risk-Taker', dots: 1 },
  ],
  // Dead Flesh would rule out Lifelike (core p. 183): Vitae Dependency instead
  thinBloodMerits: [{ name: 'Day Drinker' }, { name: 'Lifelike' }],
  thinBloodFlaws: [{ name: 'Baby Teeth' }, { name: 'Vitae Dependency' }],
  ...over,
});

/** Ventrue ancilla, Tithe Collector (ancillae only): +2 Advantage and Flaw dots, BP 3, 35 XP. */
const ventrue = (over = {}) => ({
  ...brujah0(),
  name: 'Konstantin',
  concept: 'Old-money fixer',
  clan: 'Ventrue',
  age: 'ancilla',
  generation: 11,
  skills: skills({
    3: ['etiquette', 'persuasion', 'leadership'],
    2: ['insight', 'intimidation', 'politics', 'finance', 'awareness'],
    1: ['academics', 'athletics', 'drive', 'firearms', 'investigation', 'subterfuge', 'streetwise'],
  }),
  specialties: [
    { skill: 'academics', name: 'Law' },
    { skill: 'finance', name: 'Banking' },
  ],
  disciplines: [
    { name: 'Dominate', level: 2, powers: ['Cloud Memory', 'Mesmerize', 'Submerged Directive'] },
    { name: 'Presence', level: 1, powers: ['Awe'] },
  ],
  predatorType: 'Tithe Collector',
  predatorSpecialty: 0,
  predatorDiscipline: 'Dominate',
  predatorChoices: { a0: 1 },
  extraPowers: {},
  advantages: [
    { name: 'Resources', dots: 4, kind: 'background' },
    { name: 'Haven', dots: 2, kind: 'background' },
    { name: 'Retainers', dots: 3, kind: 'background' },
  ],
  flaws: [
    { name: 'Enemy', dots: 2 },
    { name: 'Dark Secret', dots: 2 },
  ],
  xpPurchases: [
    { kind: 'attribute', trait: 'charisma' },
    { kind: 'skill', trait: 'etiquette' },
    { kind: 'specialty', skill: 'etiquette', trait: 'Elysium' },
  ],
  ...over,
});

/** Toreador fledgling at Humanity 8, Siren (Presence dot on a pick). */
const toreador = (over = {}) => ({
  ...brujah0(),
  name: 'Eleni',
  concept: 'Opera singer',
  clan: 'Toreador',
  age: 'childer',
  generation: 13,
  skills: skills({
    3: ['performance', 'persuasion', 'etiquette'],
    2: ['insight', 'subterfuge', 'awareness', 'academics', 'craft'],
    1: ['athletics', 'drive', 'stealth', 'streetwise', 'larceny', 'investigation', 'occult'],
  }),
  specialties: [
    { skill: 'performance', name: 'Singing' },
    { skill: 'academics', name: 'Art history' },
    { skill: 'craft', name: 'Painting' },
    { skill: 'persuasion', name: 'Flattery' },
  ],
  disciplines: [
    { name: 'Auspex', level: 2, powers: ['Heightened Senses', 'Premonition'] },
    { name: 'Presence', level: 1, powers: ['Awe', 'Lingering Kiss'] },
  ],
  predatorType: 'Siren',
  predatorSpecialty: 0,
  predatorDiscipline: 'Presence',
  extraPowers: {},
  advantages: [
    { name: 'Fame', dots: 2, kind: 'background' },
    { name: 'Herd', dots: 2, kind: 'background' },
    { name: 'Resources', dots: 3, kind: 'background' },
  ],
  flaws: [{ name: 'Dark Secret', dots: 2 }],
  fledglingHumanity: true,
  ...over,
});

/**
 * Tzimisce Pursuer (Auspex dot) with an XP dot of Animalism: Messenger's Command needs Animal
 * Messenger and Compel or Mesmerize, a Dominate power (a prerequisite in another Discipline).
 */
const tzimisce = (over = {}) => ({
  ...brujah0(),
  name: 'Dragomir',
  concept: 'Kennel master',
  clan: 'Tzimisce',
  disciplines: [
    { name: 'Animalism', level: 2, powers: ['Bond Famulus', 'Animal Messenger', "Messenger's Command"] },
    { name: 'Dominate', level: 1, powers: ['Compel'] },
  ],
  predatorType: 'Pursuer',
  predatorSpecialty: 0,
  predatorDiscipline: 'Auspex',
  predatorChoices: {},
  extraPowers: { Auspex: ['Heightened Senses'] },
  xpPurchases: [{ kind: 'discipline', trait: 'Animalism' }],
  ...over,
});

/** Gangrel Roadside Killer: the type's Prey Exclusion has no printed rating, the player picks 2. */
const gangrel = (over = {}) => ({
  ...brujah0(),
  name: 'Rook',
  concept: 'Long-haul trucker',
  clan: 'Gangrel',
  skillDistribution: 'jack',
  skills: skills({
    3: ['survival'],
    2: ['athletics', 'brawl', 'stealth', 'drive', 'awareness', 'animal_ken', 'intimidation', 'investigation'],
    1: ['melee', 'firearms', 'larceny', 'streetwise', 'insight', 'subterfuge', 'medicine', 'occult', 'technology', 'craft'],
  }),
  specialties: [
    { skill: 'craft', name: 'Auto repair' },
    { skill: 'survival', name: 'Tracking' },
  ],
  disciplines: [
    { name: 'Protean', level: 2, powers: ['Eyes of the Beast', 'Feral Weapons', 'Earth Meld'] },
    { name: 'Animalism', level: 1, powers: ['Sense the Beast'] },
  ],
  predatorType: 'Roadside Killer',
  predatorSpecialty: 0,
  predatorDiscipline: 'Protean',
  predatorChoices: { 'f0:0:dots': 2 },
  extraPowers: {},
  ...over,
});

/** Gangrel ancilla Farmer (Blood Potency 2 at most). */
const farmerAncilla = (over = {}) =>
  gangrel({
    age: 'ancilla',
    generation: 11,
    predatorType: 'Farmer',
    predatorSpecialty: 0,
    predatorDiscipline: 'Animalism',
    predatorChoices: {},
    disciplines: [
      { name: 'Protean', level: 2, powers: ['Eyes of the Beast', 'Feral Weapons'] },
      { name: 'Animalism', level: 1, powers: ['Sense the Beast', 'Feral Whispers'] },
    ],
    advantages: [
      { name: 'Haven', dots: 3, kind: 'background' },
      { name: 'Herd', dots: 3, kind: 'background' },
      { name: 'Resources', dots: 3, kind: 'background' },
    ],
    flaws: [
      { name: 'Enemy', dots: 2 },
      { name: 'Dark Secret', dots: 2 },
    ],
    ...over,
  });

/** A Tzimisce on the Brujah's corebook picks; the clan and Risk-Taker are Players Guide entries the Companion reprints. */
const tzimisceCompanion = (over = {}) =>
  brujah0({
    name: 'Mirela',
    concept: 'Night-market butcher',
    clan: 'Tzimisce',
    disciplines: [
      { name: 'Animalism', level: 2, powers: ['Bond Famulus', 'Feral Whispers'] },
      { name: 'Dominate', level: 1, powers: ['Compel'] },
    ],
    flaws: [
      { name: 'Risk-Taker', dots: 1 },
      { name: 'Addiction', dots: 1 },
    ],
    ...over,
  });

const COREBOOK = { allowed_books: ['v5-corebook'] };

/** The Caitiff with Oblivion (a Players Guide Discipline, no power taken) instead of Animalism. */
const caitiffOblivion = () =>
  caitiff({
    disciplines: [
      { name: 'Presence', level: 2, powers: ['Awe', 'Lingering Kiss', 'Entrancement'] },
      { name: 'Oblivion', level: 1, powers: [] },
    ],
    xpPurchases: [{ kind: 'specialty', skill: 'persuasion', trait: 'Sermons' }],
  });

const meta = (payload) => payload.wod_meta;

// ---------- the cases ----------

export const CASE_DEFS = [
  // valid sheets
  { name: 'valid: Brujah Alleycat neonate with 13 XP spent', sheet: () => brujah(), expect: [] },
  { name: 'valid: Brujah with no XP spent', sheet: () => brujah0(), expect: [] },
  {
    name: 'valid: XP first dot in Academics brings its free specialty, plus an XP specialty',
    sheet: () =>
      brujah0({
        xpPurchases: [
          { kind: 'skill', trait: 'academics', specialty: 'Latin' },
          { kind: 'specialty', skill: 'brawl', trait: 'Knives' },
          { kind: 'skill', trait: 'drive' },
        ],
      }),
    expect: [],
  },
  { name: 'valid: Tremere Bagger, starting ritual, XP ritual and XP Dominate', sheet: () => tremere(), expect: [] },
  {
    name: 'valid: Tremere Bagger takes the Obfuscate dot (outside the clan picks)',
    sheet: () =>
      tremere({
        disciplines: [
          { name: 'Blood Sorcery', level: 2, powers: ['A Taste for Blood', 'Extinguish Vitae'] },
          { name: 'Auspex', level: 1, powers: ['Heightened Senses'] },
        ],
        predatorDiscipline: 'Obfuscate',
        extraPowers: { Obfuscate: ['Cloak of Shadows'], Dominate: ['Cloud Memory'] },
      }),
    expect: [],
  },
  {
    name: 'valid: Banu Haqim Bagger takes the Blood Sorcery dot (Players Guide clan)',
    sheet: () =>
      tremere({
        clan: 'Banu Haqim',
        disciplines: [
          { name: 'Blood Sorcery', level: 2, powers: ['A Taste for Blood', 'Extinguish Vitae', 'Scour Secrets'] },
          { name: 'Celerity', level: 1, powers: ['Rapid Reflexes'] },
        ],
        xpPurchases: [{ kind: 'ritual', trait: 'Calix Secretus', level: 2 }],
      }),
    expect: [],
  },
  { name: 'valid: Hecata Grim Reaper with Allies and the Summon Spirit ceremony', sheet: () => hecata(), expect: [] },
  { name: 'valid: Caitiff Osiris, Performance 0 becomes 1, split grants, Caitiff XP', sheet: () => caitiff(), expect: [] },
  { name: 'valid: thin-blood fledgling with no predator type', sheet: () => thinBlood(), expect: [] },
  { name: 'valid: Ventrue ancilla Tithe Collector spends all 35 XP', sheet: () => ventrue(), expect: [] },
  { name: 'valid: Toreador fledgling at Humanity 8', sheet: () => toreador(), expect: [] },
  { name: 'valid: Gangrel Roadside Killer picks the unprinted Prey Exclusion rating', sheet: () => gangrel(), expect: [] },
  {
    name: "valid: Tzimisce Messenger's Command with Compel from Dominate (prerequisite in another Discipline)",
    sheet: () => tzimisce(),
    expect: [],
  },
  {
    name: 'valid: Allies at 6 dots, as the catalog prints it (a row named, without its id)',
    sheet: () =>
      brujah0({
        advantages: [
          { name: 'Allies (dock workers)', dots: 6, kind: 'background' },
          { name: 'Haven', dots: 1, kind: 'background' },
        ],
      }),
    expect: [],
  },
  {
    name: 'valid: inside the chronicle settings',
    settings: { allowed_clans: ['Brujah', 'Toreador'], allowed_predators: ['Alleycat'], allowed_ages: ['neonate'], flaws_max_dots: 4 },
    sheet: () => brujah(),
    expect: [],
  },
  { name: 'valid: allowed books: only the corebook, every pick from it', settings: COREBOOK, sheet: () => brujah(), expect: [] },
  {
    name: 'valid: allowed books: a Players Guide clan and Flaw the Companion reprints (also_in)',
    settings: { allowed_books: ['v5-corebook', 'v5-companion'] },
    sheet: () => tzimisceCompanion(),
    expect: [],
  },
  {
    name: 'valid: allowed books: a Caitiff picks Oblivion with the Players Guide allowed',
    settings: { allowed_books: ['v5-corebook', 'v5-players-guide'] },
    sheet: () => caitiffOblivion(),
    expect: [],
  },

  // attributes and skills
  { name: 'attributes: two at 4', sheet: () => brujah0({ attributes: { ...ATTRS, dexterity: 4 } }), expect: ['attr_spread'] },
  { name: 'attributes: a 5 at creation', sheet: () => brujah0({ attributes: { ...ATTRS, strength: 5 } }), expect: ['attr_range'] },
  {
    name: 'skills: one dot too many for Balanced',
    sheet: () => brujah0({ skills: { ...brujah0().skills, finance: 1 } }),
    expect: ['skill_dist'],
  },
  { name: 'skills: no distribution chosen', sheet: () => brujah0({ skillDistribution: '' }), expect: ['skill_dist'] },
  {
    name: 'specialties: two free ones where one is allowed',
    sheet: () => brujah0({ specialties: [{ skill: 'athletics', name: 'Parkour' }, { skill: 'stealth', name: 'Rooftops' }] }),
    expect: ['specialty_count'],
  },
  {
    name: 'specialties: rated Academics without its free specialty',
    sheet: () => brujah0({ skills: { ...brujah0().skills, occult: 0, academics: 1 } }),
    expect: ['specialty_missing'],
  },
  {
    name: 'specialties: the same one twice',
    sheet: () =>
      tremere({
        specialties: [
          { skill: 'academics', name: 'Hermetic texts' },
          { skill: 'science', name: 'Chemistry' },
          { skill: 'academics', name: 'Hermetic Texts' },
        ],
      }),
    expect: ['specialty_duplicate'],
  },

  // Disciplines and powers
  {
    name: 'disciplines: two at 2 dots',
    sheet: () =>
      brujah0({
        disciplines: [
          { name: 'Potence', level: 2, powers: ['Lethal Body', 'Prowess'] },
          { name: 'Presence', level: 2, powers: ['Awe', 'Daunt'] },
        ],
      }),
    expect: ['disc_pick'],
  },
  {
    name: 'disciplines: Dominate is not a Brujah Discipline',
    sheet: () =>
      brujah0({
        disciplines: [
          { name: 'Dominate', level: 2, powers: ['Cloud Memory', 'Compel'] },
          { name: 'Potence', level: 1, powers: ['Lethal Body'] },
        ],
      }),
    expect: ['disc_clan'],
  },
  {
    name: 'powers: a level 3 power at Potence 2',
    sheet: () => brujah0({ disciplines: [{ name: 'Potence', level: 2, powers: ['Lethal Body', 'Brutal Feed'] }, brujah0().disciplines[1]] }),
    expect: ['power_level'],
  },
  {
    name: 'powers: Eyes of the Serpent needs Protean 1',
    sheet: () => brujah0({ disciplines: [brujah0().disciplines[0], { name: 'Presence', level: 1, powers: ['Eyes of the Serpent'] }] }),
    expect: ['power_amalgam'],
  },
  {
    name: 'powers: Weaving needs Rapid Reflexes',
    sheet: () =>
      brujah0({
        disciplines: [
          { name: 'Celerity', level: 2, powers: ["Cat's Grace", 'Fleetness', 'Weaving'] },
          { name: 'Potence', level: 1, powers: ['Lethal Body'] },
        ],
      }),
    expect: ['power_prereq'],
  },
  {
    name: "powers: Messenger's Command without Compel or Mesmerize",
    sheet: () => tzimisce({ disciplines: [tzimisce().disciplines[0], { name: 'Dominate', level: 1, powers: ['Cloud Memory'] }] }),
    expect: ['power_prereq'],
  },
  {
    name: 'powers: the same power twice',
    sheet: () => brujah0({ disciplines: [{ name: 'Potence', level: 2, powers: ['Lethal Body', 'Lethal Body'] }, brujah0().disciplines[1]] }),
    expect: ['power_duplicate'],
  },
  {
    name: 'powers: not a Potence power',
    sheet: () => brujah0({ disciplines: [{ name: 'Potence', level: 2, powers: ['Lethal Body', 'Mind Bullet'] }, brujah0().disciplines[1]] }),
    expect: ['power_unknown'],
  },

  // predator type
  {
    name: 'predator: none chosen',
    sheet: () => brujah0({ predatorType: '', predatorSpecialty: null, predatorDiscipline: '', extraPowers: {} }),
    expect: ['predator_missing'],
  },
  {
    name: 'predator: Ventrue cannot be a Bagger',
    sheet: () =>
      ventrue({
        age: 'neonate',
        generation: 13,
        predatorType: 'Bagger',
        predatorSpecialty: 1,
        predatorDiscipline: 'Obfuscate',
        predatorChoices: {},
        disciplines: [
          { name: 'Dominate', level: 2, powers: ['Cloud Memory', 'Mesmerize'] },
          { name: 'Presence', level: 1, powers: ['Awe'] },
        ],
        extraPowers: { Obfuscate: ['Cloak of Shadows'] },
        advantages: [{ name: 'Resources', dots: 4, kind: 'background' }, { name: 'Haven', dots: 3, kind: 'background' }],
        // not Enemy: Bagger gives Enemies already, and it can be taken only once
        flaws: [{ name: 'Dark Secret', dots: 2 }],
        xpPurchases: [],
      }),
    expect: ['predator_forbidden'],
  },
  { name: 'predator: no specialty picked', sheet: () => brujah0({ predatorSpecialty: null }), expect: ['predator_specialty'] },
  {
    name: 'predator: no Discipline dot picked',
    sheet: () => brujah0({ predatorDiscipline: '', extraPowers: {} }),
    expect: ['predator_discipline'],
  },
  { name: 'predator: Grim Reaper without its Allies or Influence choice', sheet: () => hecata({ predatorChoices: {} }), expect: ['predator_grant'] },
  {
    name: 'predator: Osiris shares 2 of its 3 Fame/Herd dots',
    sheet: () => caitiff({ predatorChoices: { a0: { 0: 1, 1: 1 }, f0: { 0: 1, 1: 1 }, 'f0:1:pick': 'flaw:folkloric-bane' } }),
    expect: ['predator_grant'],
  },
  { name: 'predator: Farmer ancilla is over Blood Potency 2', sheet: () => farmerAncilla(), expect: ['predator_bp'] },
  {
    name: 'predator: Tithe Collector for a neonate',
    sheet: () =>
      ventrue({
        age: 'neonate',
        generation: 13,
        advantages: [{ name: 'Resources', dots: 4, kind: 'background' }, { name: 'Haven', dots: 3, kind: 'background' }],
        flaws: [{ name: 'Enemy', dots: 2 }],
        xpPurchases: [],
      }),
    expect: ['predator_ancilla'],
  },

  // Advantages and Flaws
  {
    name: 'advantages: 8 dots of your own',
    sheet: () => brujah0({ advantages: [...brujah0().advantages.slice(0, 2), { name: 'Allies (dock workers)', dots: 3, kind: 'background' }] }),
    expect: ['adv_over'],
  },
  { name: 'flaws: a Siren with only the type’s Enemy', sheet: () => toreador({ flaws: [] }), expect: ['flaw_under'] },
  { name: 'advantages: a 6-dot row', sheet: () => brujah0({ advantages: [{ name: 'Resources', dots: 6, kind: 'background' }] }), expect: ['adv_dots_range'] },
  // Saved points (forge v2 D): the unspent dots and the unused free specialty go to wod_meta.saved,
  // which counts toward the 7 dots, so a payload can't claim more than it left unspent.
  {
    name: 'valid: 2 Advantage dots and the free specialty saved for later',
    sheet: () =>
      brujah0({
        advantages: [
          { name: 'Resources', dots: 3, kind: 'background' },
          { name: 'Haven', dots: 2, kind: 'background' },
        ],
        specialties: [],
      }),
    expect: [],
  },
  {
    name: 'saved: more Advantage dots saved than were left unspent',
    sheet: () => brujah0(),
    tamper: (p) => {
      meta(p).saved.advantage_dots = 3;
    },
    expect: ['adv_over'],
  },
  {
    name: 'thin-blood: two Merits, one Flaw',
    sheet: () => thinBlood({ thinBloodFlaws: [{ name: 'Baby Teeth' }] }),
    expect: ['thin_blood_merits'],
  },

  // Convictions, age and generation
  { name: 'convictions: none', sheet: () => brujah0({ convictions: [] }), expect: ['conviction_count'] },
  {
    name: 'convictions: four',
    sheet: () =>
      brujah0({
        convictions: ['a', 'b', 'c', 'd'].map((x) => ({ conviction: `Conviction ${x}`, touchstone: `Touchstone ${x}` })),
      }),
    expect: ['conviction_count'],
  },
  {
    name: 'convictions: one without its Touchstone',
    sheet: () => brujah0({ convictions: [{ conviction: 'Never harm a child', touchstone: '' }] }),
    expect: ['conviction_pairs'],
  },
  { name: 'age: a neonate of the 11th generation', sheet: () => brujah0({ generation: 11 }), expect: ['age_generation'] },
  { name: 'generation: a thin-blood of the 13th', sheet: () => thinBlood({ generation: 13 }), expect: ['thin_blood_generation'] },
  { name: 'generation: a 14th-generation Toreador', sheet: () => toreador({ generation: 14 }), expect: ['generation_thin_blood'] },

  // starting experience and rituals
  {
    name: 'xp: 23 of 15 spent',
    sheet: () => brujah({ xpPurchases: [...brujah().xpPurchases, { kind: 'attribute', trait: 'resolve' }] }),
    expect: ['xp_over'],
  },
  {
    name: 'xp: Medicine bought to 6',
    sheet: () =>
      ventrue({
        skillDistribution: 'specialist',
        skills: skills({
          4: ['medicine'],
          3: ['etiquette', 'persuasion', 'leadership'],
          2: ['insight', 'intimidation', 'finance'],
          1: ['academics', 'awareness', 'politics'],
        }),
        xpPurchases: [
          { kind: 'skill', trait: 'medicine' },
          { kind: 'skill', trait: 'medicine' },
        ],
      }),
    expect: ['xp_max_dots'],
  },
  {
    name: 'rituals: a level 4 ritual at Blood Sorcery 3',
    sheet: () => tremere({ xpPurchases: [{ kind: 'ritual', trait: 'Defense of the Sacred Haven', level: 4 }], extraPowers: {} }),
    expect: ['ritual_blood_sorcery'],
  },
  {
    name: 'rituals: a level 1 ritual bought as level 2',
    sheet: () => tremere({ xpPurchases: [{ kind: 'ritual', trait: 'Ward against Ghouls', level: 2 }], extraPowers: {} }),
    expect: ['ritual_level'],
  },

  // supplement data (Forge v2 part F): restrictions printed on a sheet or a level, Koldunic Sorcery,
  // Flaws the book gives no rating, Merit prerequisites, two entries of one name
  {
    name: 'loresheets: Child of the Angel Michael is open to a Brujah',
    sheet: () => brujah0({ advantages: [...brujah0().advantages.slice(0, 2), { id: 'loresheet:child-of-the-angel-michael', name: 'Child of the Angel Michael', dots: 2, kind: 'loresheet', levels: [2] }] }),
    expect: [],
  },
  {
    name: 'loresheets: Child of the Angel Michael is unavailable to Nosferatu',
    sheet: () =>
      brujah0({
        clan: 'Nosferatu',
        disciplines: [
          { name: 'Potence', level: 2, powers: ['Lethal Body', 'Prowess'] },
          { name: 'Obfuscate', level: 1, powers: ['Cloak of Shadows'] },
        ],
        advantages: [...brujah0().advantages.slice(0, 2), { id: 'loresheet:child-of-the-angel-michael', name: 'Child of the Angel Michael', dots: 2, kind: 'loresheet', levels: [2] }],
      }),
    expect: ['loresheet_restricted'],
  },
  {
    name: 'loresheets: Tegyrius the Vizier levels 1–3 are open to anyone',
    sheet: () => brujah0({ advantages: [{ name: 'Resources', dots: 1, kind: 'background' }, { id: 'loresheet:tegyrius-the-vizier', name: 'Tegyrius the Vizier', dots: 6, kind: 'loresheet', levels: [1, 2, 3] }] }),
    expect: [],
  },
  {
    name: 'loresheets: Tegyrius the Vizier level 4 is Banu Haqim only',
    sheet: () => brujah0({ advantages: [{ name: 'Resources', dots: 3, kind: 'background' }, { id: 'loresheet:tegyrius-the-vizier', name: 'Tegyrius the Vizier', dots: 4, kind: 'loresheet', levels: [4] }] }),
    expect: ['loresheet_restricted'],
  },
  {
    name: 'loresheets: an Anarch sheet whose level names our sources lack can be taken',
    sheet: () => brujah0({ advantages: [...brujah0().advantages.slice(0, 2), { id: 'loresheet:salvador-garcia', name: 'Salvador Garcia', dots: 2, kind: 'loresheet', levels: [2] }] }),
    expect: [],
  },
  {
    name: 'powers: Koldunic Sorcery is for the Tzimisce only',
    sheet: () =>
      tremere({ disciplines: [{ name: 'Blood Sorcery', level: 2, powers: ['Koldunic Sorcery', 'Extinguish Vitae', 'Blood of Potency'] }, tremere().disciplines[1]] }),
    expect: ['power_clan'],
  },
  {
    name: 'powers: a Tzimisce buys Blood Sorcery with XP and takes Koldunic Sorcery with it',
    sheet: () =>
      tzimisce({
        disciplines: [
          { name: 'Animalism', level: 2, powers: ['Bond Famulus', 'Feral Whispers'] },
          { name: 'Dominate', level: 1, powers: ['Compel'] },
        ],
        extraPowers: { Auspex: ['Heightened Senses'], 'Blood Sorcery': ['Koldunic Sorcery'] },
        xpPurchases: [{ kind: 'discipline', trait: 'Blood Sorcery' }],
      }),
    expect: [],
  },
  {
    // its "with the first Blood Sorcery dot" is about order; creation dots come all at once
    name: 'powers: an ancilla Tzimisce takes Koldunic Sorcery in the second Blood Sorcery slot',
    sheet: () =>
      tzimisce({
        age: 'ancilla',
        generation: 11,
        disciplines: [
          { name: 'Animalism', level: 2, powers: ['Bond Famulus', 'Feral Whispers'] },
          { name: 'Dominate', level: 1, powers: ['Compel'] },
        ],
        flaws: [
          { name: 'Enemy', dots: 2 },
          { name: 'Dark Secret', dots: 2 },
        ],
        extraPowers: { Auspex: ['Heightened Senses'], 'Blood Sorcery': ['A Taste for Blood', 'Koldunic Sorcery'] },
        xpPurchases: [
          { kind: 'discipline', trait: 'Blood Sorcery' },
          { kind: 'discipline', trait: 'Blood Sorcery' },
        ],
      }),
    expect: [],
  },
  {
    name: 'rituals: a Koldunic ritual needs the Koldunic Sorcery power',
    sheet: () => tremere({ xpPurchases: [{ kind: 'ritual', trait: 'Elemental Grasp', level: 2 }, { kind: 'discipline', trait: 'Dominate' }] }),
    expect: ['ritual_prereq'],
  },
  {
    name: 'advantages: a Flaw the book gives no rating takes the dots the player picks',
    sheet: () =>
      brujah0({
        predatorDiscipline: 'Potence',
        disciplines: [
          { name: 'Potence', level: 2, powers: ['Lethal Body', 'Prowess', 'Brutal Feed'] },
          { name: 'Presence', level: 1, powers: ['Awe'] },
        ],
        extraPowers: {},
        flaws: [{ id: 'flaw:ingrained-killer-instinct', name: 'Killer Instinct', dots: 2 }],
      }),
    expect: [],
  },
  {
    name: 'advantages: an Ingrained Discipline Flaw needs that Discipline at 3',
    sheet: () => brujah0({ flaws: [{ id: 'flaw:ingrained-killer-instinct', name: 'Killer Instinct', dots: 2 }] }),
    expect: ['adv_requires'],
  },
  {
    name: 'advantages: two Ingrained Discipline Flaws (one only), the second without its Discipline',
    sheet: () =>
      brujah0({
        predatorDiscipline: 'Potence',
        disciplines: [
          { name: 'Potence', level: 2, powers: ['Lethal Body', 'Prowess', 'Brutal Feed'] },
          { name: 'Presence', level: 1, powers: ['Awe'] },
        ],
        extraPowers: {},
        flaws: [
          { id: 'flaw:ingrained-killer-instinct', name: 'Killer Instinct', dots: 1 },
          { id: 'flaw:ingrained-egomaniac', name: 'Egomaniac', dots: 1 },
        ],
      }),
    expect: ['adv_excluded', 'adv_requires'],
  },
  {
    name: "advantages: Groveling Worm and Penitence can't be taken together",
    sheet: () =>
      brujah0({
        advantages: [
          { name: 'Resources', dots: 3, kind: 'background' },
          { name: 'Haven', dots: 2, kind: 'background' },
          { id: 'merit:penitence', name: 'Penitence', dots: 2, kind: 'merit' },
        ],
        flaws: [{ id: 'flaw:groveling-worm', name: 'Groveling Worm', dots: 2 }],
      }),
    expect: ['adv_excluded'],
  },
  {
    name: "advantages: a thin-blood can't take Dead Flesh with Lifelike",
    sheet: () => thinBlood({ thinBloodFlaws: [{ name: 'Baby Teeth' }, { name: 'Dead Flesh' }] }),
    expect: ['adv_excluded'],
  },
  {
    name: 'loresheets: Student of Kirin Taunk is open to a thin-blood with the Thin-Blood Alchemist Merit',
    sheet: () =>
      thinBlood({
        advantages: [...thinBlood().advantages, { id: 'loresheet:student-of-kirin-taunk', name: 'Student of Kirin Taunk', dots: 1, kind: 'loresheet', levels: [1] }],
        thinBloodMerits: [{ name: 'Day Drinker' }, { name: 'Thin-Blood Alchemist' }],
      }),
    expect: [],
  },
  {
    name: 'loresheets: Student of Kirin Taunk needs the Thin-Blood Alchemist Merit',
    sheet: () =>
      thinBlood({
        advantages: [...thinBlood().advantages, { id: 'loresheet:student-of-kirin-taunk', name: 'Student of Kirin Taunk', dots: 1, kind: 'loresheet', levels: [1] }],
      }),
    expect: ['loresheet_restricted'],
  },
  {
    name: 'advantages: Influencer (Succubus Club) needs Fame 2',
    sheet: () =>
      brujah0({
        advantages: [
          { name: 'Resources', dots: 3, kind: 'background' },
          { name: 'Haven', dots: 2, kind: 'background' },
          { id: 'merit:influencer', name: 'Influencer', dots: 1, kind: 'merit' },
        ],
      }),
    expect: ['adv_requires'],
  },
  {
    name: 'advantages: Influencer with Fame 2',
    sheet: () =>
      brujah0({
        advantages: [
          { name: 'Resources', dots: 3, kind: 'background' },
          { name: 'Fame', dots: 2, kind: 'background' },
          { id: 'merit:influencer', name: 'Influencer', dots: 1, kind: 'merit' },
        ],
      }),
    expect: [],
  },
  {
    name: "advantages: the Ashfinders' Influencer is another Merit (by id): no Fame needed",
    sheet: () =>
      brujah0({
        advantages: [
          { name: 'Resources', dots: 3, kind: 'background' },
          { name: 'Haven', dots: 2, kind: 'background' },
          { id: 'merit:influencer-ashfinders', name: 'Influencer', dots: 2, kind: 'merit' },
        ],
      }),
    expect: [],
  },

  // the chronicle's creation settings
  { name: 'settings: clan left out', settings: { allowed_clans: ['Tremere'] }, sheet: () => brujah0(), expect: ['clan_not_allowed'] },
  { name: 'settings: predator type left out', settings: { allowed_predators: ['Siren'] }, sheet: () => brujah0(), expect: ['predator_not_allowed'] },
  { name: 'settings: age left out', settings: { allowed_ages: ['childer'] }, sheet: () => brujah0(), expect: ['age_not_allowed'] },
  {
    name: 'settings: over the Flaw cap',
    settings: { flaws_max_dots: 2 },
    sheet: () => brujah0({ flaws: [{ name: 'Enemy', dots: 2 }, { name: 'Dark Secret', dots: 1 }] }),
    expect: ['flaw_over'],
  },
  {
    name: 'settings: no Humanity 8 start',
    settings: { fledgling_humanity_8: false },
    sheet: () => toreador(),
    expect: ['fledgling_not_allowed'],
  },
  {
    name: 'books: a Players Guide clan and Flaw with only the corebook (no Companion)',
    settings: COREBOOK,
    sheet: () => tzimisceCompanion(),
    expect: ['book_not_allowed'],
  },
  {
    name: 'books: a Players Guide clan, predator type, powers and ceremony with only the corebook',
    settings: COREBOOK,
    sheet: () => hecata(),
    expect: ['book_not_allowed'],
  },
  {
    name: 'books: a Caitiff picks Oblivion (Players Guide) with only the corebook',
    settings: COREBOOK,
    sheet: () => caitiffOblivion(),
    expect: ['book_not_allowed'],
  },
  {
    name: 'books: a Players Guide power with only the corebook',
    settings: COREBOOK,
    sheet: () =>
      brujah0({
        disciplines: [
          { name: 'Potence', level: 2, powers: ['Lethal Body', 'Relentless Grasp'] },
          { name: 'Presence', level: 1, powers: ['Awe'] },
        ],
      }),
    expect: ['book_not_allowed'],
  },
  {
    name: 'books: a Players Guide ritual bought with XP with only the corebook',
    settings: COREBOOK,
    sheet: () => tremere(),
    expect: ['book_not_allowed'],
  },
  {
    name: 'books: a Players Guide Merit with only the corebook',
    settings: COREBOOK,
    sheet: () =>
      brujah0({
        advantages: [
          { name: 'Resources', dots: 3, kind: 'background' },
          { name: 'Haven', dots: 2, kind: 'background' },
          { name: 'Allies (dock workers)', dots: 1, kind: 'background' },
          { name: 'Check the Trunk', dots: 1, kind: 'merit' },
        ],
      }),
    expect: ['book_not_allowed'],
  },
  {
    name: 'books: a Players Guide thin-blood Merit with only the corebook',
    settings: COREBOOK,
    sheet: () =>
      thinBlood({
        flaws: [
          { name: 'Prey Exclusion (animals)', dots: 1 },
          { name: 'Addiction', dots: 1 },
        ],
        thinBloodMerits: [{ name: 'Day Drinker' }, { name: 'Low Appetite' }],
      }),
    expect: ['book_not_allowed'],
  },
  {
    name: 'several problems at once',
    sheet: () =>
      brujah0({
        attributes: { ...ATTRS, dexterity: 4 },
        advantages: [{ name: 'Resources', dots: 5, kind: 'background' }, { name: 'Haven', dots: 4, kind: 'background' }],
        convictions: [],
      }),
    expect: ['adv_over', 'attr_spread', 'conviction_count'],
  },

  // payloads the forge can't make (changed after buildV5Payload)
  {
    name: 'server: an XP dot priced too low',
    sheet: () => brujah(),
    tamper: (p) => {
      meta(p).experience.log[0].cost = 5;
    },
    expect: ['xp_price'],
  },
  {
    name: 'server: 35 starting XP for a neonate',
    sheet: () => brujah(),
    tamper: (p) => {
      Object.assign(meta(p).experience, { total: 35, unspent: 22 });
    },
    expect: ['xp_total'],
  },
  {
    name: 'server: an XP log that skips a dot',
    sheet: () => brujah(),
    tamper: (p) => {
      Object.assign(meta(p).experience.log[0], { from: 2, to: 3 });
    },
    expect: ['xp_log'],
  },
  {
    name: 'server: XP on a childe',
    sheet: () => toreador(),
    tamper: (p) => {
      p.skills.physical.athletics += 1;
      meta(p).experience = {
        total: 15,
        spent: 6,
        unspent: 9,
        log: [{ kind: 'skill', trait: 'athletics', what: 'Athletics', from: 1, to: 2, cost: 6 }],
      };
    },
    expect: ['xp_none'],
  },
  {
    name: 'server: Humanity raised by hand',
    sheet: () => brujah(),
    tamper: (p) => {
      meta(p).humanity = 9;
    },
    expect: ['derived_value'],
  },
  {
    name: 'server: Blood Potency raised by hand',
    sheet: () => brujah(),
    tamper: (p) => {
      meta(p).blood_potency = 3;
    },
    expect: ['derived_value'],
  },
  {
    name: 'server: Health raised by hand',
    sheet: () => brujah(),
    tamper: (p) => {
      meta(p).health.max = 8;
    },
    expect: ['derived_value'],
  },
  {
    name: 'server: the predator type’s Contacts relabelled as Resources',
    sheet: () => brujah(),
    tamper: (p) => {
      meta(p).advantages.find((a) => a.kind === 'predator').name = 'Resources';
    },
    expect: ['predator_grant'],
  },
  {
    name: 'server: a predator specialty the type does not give',
    sheet: () => brujah(),
    tamper: (p) => {
      p.skills.specialties.find((s) => s.source === 'predator').name = 'Everything';
    },
    expect: ['predator_specialty'],
  },
  {
    name: 'server: Summon Spirit without The Binding Fetter',
    sheet: () => hecata(),
    tamper: (p) => {
      meta(p).disciplines.find((d) => d.name === 'Oblivion').powers[0] = "Oblivion's Sight";
    },
    expect: ['ceremony_start'],
  },
  {
    name: 'server: two free starting rituals',
    sheet: () => tremere(),
    tamper: (p) => {
      meta(p).rituals.push({ name: 'Ward against Ghouls', level: 1, source: 'creation' });
    },
    expect: ['ritual_start'],
  },
  {
    name: 'server: an XP ritual missing from the rituals list',
    sheet: () => tremere(),
    tamper: (p) => {
      meta(p).rituals = meta(p).rituals.filter((r) => r.source !== 'xp');
    },
    expect: ['xp_log'],
  },
  {
    name: 'server: a thin-blood with a Discipline',
    sheet: () => thinBlood(),
    tamper: (p) => {
      meta(p).disciplines = [{ name: 'Thin-Blood Alchemy', level: 1, powers: [] }];
    },
    expect: ['disc_thin_blood'],
  },
  {
    name: 'server: thin-blood Merits on a Brujah',
    sheet: () => brujah(),
    tamper: (p) => {
      meta(p).thin_blood_merits = ['Day Drinker'];
    },
    expect: ['thin_blood_only'],
  },
  {
    name: 'server: three powers at Potence 2',
    sheet: () => brujah(),
    tamper: (p) => {
      meta(p).disciplines.find((d) => d.name === 'Potence').powers.push('Soaring Leap');
    },
    expect: ['power_count'],
  },
  {
    name: 'server: a custom row needs the Storyteller',
    sheet: () => brujah0(),
    tamper: (p) => {
      meta(p).advantages[1] = { name: 'Night Doctor', dots: 2, kind: 'merit', custom: true };
    },
    expect: ['custom_row'],
  },
  {
    name: 'server: a loresheet row whose dots are not the sum of its levels',
    sheet: () => brujah0(),
    tamper: (p) => {
      meta(p).advantages[1] = { name: 'Theo Bell', dots: 2, kind: 'loresheet', levels: [1, 2] };
    },
    expect: ['loresheet_levels'],
  },
  {
    name: 'server: a Caitiff who lists Status',
    sheet: () => caitiff(),
    tamper: (p) => {
      meta(p).advantages[0] = { name: 'Status', dots: 2, kind: 'background' };
    },
    expect: ['caitiff_status'],
  },
  {
    name: 'server: v5.json fallback names for the Siren grants are accepted',
    sheet: () => toreador(),
    tamper: (p) => {
      meta(p).advantages.find((a) => a.kind === 'predator').name = 'Looks: Beautiful';
      meta(p).flaws.find((a) => a.kind === 'predator').name = 'Enemy (spurned lover or jealous partner)';
    },
    expect: [],
  },
  {
    name: 'server: v5.json fallback name for the Bagger specialty is accepted',
    sheet: () => tremere(),
    tamper: (p) => {
      p.skills.specialties.find((s) => s.source === 'predator').name = 'Lock Picking';
    },
    expect: [],
  },
];

/** The cases with their forge sheets: {name, settings, client, sheet, payload, expect}. */
export function buildCases(defs = CASE_DEFS) {
  return defs.map((d) => {
    const sheet = d.sheet();
    const payload = buildV5Payload(sheet);
    if (d.tamper) d.tamper(payload);
    return JSON.parse(
      JSON.stringify({
        name: d.name,
        settings: d.settings || null,
        client: !d.tamper,
        expect: [...new Set(d.expect)].sort(),
        sheet,
        payload,
      })
    );
  });
}

/** A case as the shared file stores it (no forge sheet: the server reads the payload). */
export const storedCase = ({ sheet, ...c }) => c;

/**
 * The shared file's text: one JSON line per catalog entry and per case (scripts/v5_creation_cases.py
 * writes the same layout).
 */
export function formatCasesFile(doc) {
  const line = (x) => JSON.stringify(x);
  const list = (arr, pad) => (arr.length ? `[\n${arr.map((x) => `${pad} ${line(x)}`).join(',\n')}\n${pad}]` : '[]');
  const catalog = Object.entries(doc.catalog || {})
    .map(([k, v]) => `  ${line(k)}: ${list(v, '  ')}`)
    .join(',\n');
  return `{\n "version": ${line(doc.version)},\n "about": ${line(doc.about)},\n "catalog": {\n${catalog}\n },\n "cases": ${list(doc.cases, ' ')}\n}\n`;
}
