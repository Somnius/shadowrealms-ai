/** Revised-era oWoD sheet lists — single source for forge UI and validation. */

export const PHYSICAL = ['strength', 'dexterity', 'stamina'];
export const SOCIAL = ['charisma', 'manipulation', 'appearance'];
export const MENTAL = ['perception', 'intelligence', 'wits'];

/** Ability columns: [key, label] */
export const TALENTS = [
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

export const SKILLS = [
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

export const KNOWLEDGES = [
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

export const VAMPIRE_CLANS = [
  'Brujah', 'Gangrel', 'Malkavian', 'Nosferatu', 'Toreador', 'Tremere', 'Ventrue',
  'Lasombra', 'Tzimisce', 'Ravnos', 'Assamite', 'Followers of Set', 'Giovanni',
];

export const WTA_BREEDS = ['Homid', 'Metis', 'Lupus'];
export const WTA_AUSPICES = ['Ahroun', 'Galliard', 'Philodox', 'Ragabash', 'Theurge'];
export const WTA_TRIBES = [
  'Black Furies', 'Bone Gnawers', 'Children of Gaia', 'Fianna', 'Get of Fenris',
  'Glass Walkers', 'Red Talons', 'Shadow Lords', 'Silent Striders', 'Silver Fangs',
  'Uktena', 'Wendigo', 'Stargazers',
];

export const MTA_TRADITIONS = [
  'Akashic Brotherhood', 'Celestial Chorus', 'Cult of Ecstasy', 'Dream Speakers',
  'Euthanatos', 'Order of Hermes', 'Sons of Ether', 'Verbena', 'Virtual Adepts',
];

/** Classic oWoD-style Nature / Demeanor archetypes (Revised-era sheet lists). */
export const WOD_ARCHETYPES = [
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

export const ARCHETYPE_CUSTOM = '__custom__';

export const MTA_SPHERES = [
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

export const DISCIPLINE_PRESETS = [
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

/** Section anchor ids — must match CharacterCreationWizard nav. */
export const SHEET_SECTION_IDS = {
  identity: 'section-identity',
  template: 'section-template',
  nature: 'section-nature',
  attributes: 'section-attributes',
  abilities: 'section-abilities',
  advantages: 'section-advantages',
  story: 'section-story',
};
