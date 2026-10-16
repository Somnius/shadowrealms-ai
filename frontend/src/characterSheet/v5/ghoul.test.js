/**
 * The ghoul forge's pure rules (ghoul.js): Mira passes, the failing shapes say why, the catalog
 * options leave out what ghouls can't buy, the payload is the server's shape.
 */
import fixture from './__fixtures__/creation-cases.json';
import { DARIUS, miraSheet, skillsOf } from './__fixtures__/ghoulFixtures';
import { applyV5Catalog } from './rulesData';
import {
  GHOUL_TEMPLATES,
  buildGhoulPayload,
  canBeDomitor,
  isV5Domitor,
  deriveGhoul,
  emptyGhoulAttributes,
  ghoulAdvantageOptions,
  ghoulAttributeStatus,
  ghoulDomitorId,
  ghoulLoresheetOptions,
  ghoulPowerOptions,
  ghoulSpecialtyCount,
  isGhoul,
  templateForRetainerDots,
  validateGhoulSheet,
} from './ghoul';
import { V5_SECTION_IDS as S } from './constants';
import translateSheetError from '../i18nErrors';
import { setLanguage } from '../../i18n';

beforeAll(() => applyV5Catalog(fixture.catalog));
afterAll(() => applyV5Catalog(null));

test('Mira passes with no problem', () => {
  expect(validateGhoulSheet(miraSheet(), DARIUS)).toEqual({});
});

test('the payload is what the server checks', () => {
  const p = buildGhoulPayload(miraSheet(), DARIUS);
  expect(p.system_type).toBe('vampire');
  expect(p.skills.distribution).toBe('gifted');
  expect(p.skills.specialties).toEqual([
    { skill: 'persuasion', name: 'Negotiation', source: 'template' },
    { skill: 'academics', name: 'Media studies' },
    { skill: 'craft', name: 'Video editing' },
  ]);
  const m = p.wod_meta;
  expect(m.sheet_kind).toBe('ghoul');
  expect(m.ghoul).toEqual({
    template: 'gifted',
    retainer_dots: 3,
    domitor: { character_id: 17, name: 'Darius Vale', clan: 'Ventrue' },
    age: 55,
    apparent_age: 53,
    ghouled_since: "About two to three years ago, during Darius's independent year, before Kessler.",
    bonds: [{ character_id: 17, name: 'Darius Vale', strength: null, note: 'Full Bond from the first drink (Bondslave).' }],
    feeding: { last: '', note: "A Rouse Check's worth of Darius's Blood about once a month." },
  });
  expect(m.disciplines).toEqual([{ name: 'Dominate', level: 1, powers: ['Cloud Memory'], ghoul: true }]);
  expect([m.humanity, m.health.max, m.willpower.max]).toEqual([7, 4, 3]);
  expect(m.advantages[1]).toEqual({ id: 'background:contacts', name: 'Contacts (television production coordinator)', dots: 2, kind: 'background', note: 'television production coordinator' });
  expect(m.flaws[2]).toEqual({ id: 'flaw:addiction', name: 'Addiction (cocaine)', dots: 1, kind: 'flaw', note: 'cocaine' });
  ['clan', 'generation', 'hunger', 'blood_potency', 'predator_type', 'saved', 'experience', 'rituals'].forEach((k) => expect(m).not.toHaveProperty(k));
  expect(p.merits_flaws.entries).toContainEqual({ name: 'Bondslave', points: -2, note: 'flaw' });
});

test('a retainer may leave Humanity out; a player ghoul tracks it', () => {
  expect(buildGhoulPayload(miraSheet({ humanityTracked: false }), DARIUS).wod_meta).not.toHaveProperty('humanity');
  expect(deriveGhoul({ template: 'player' }).humanity).toBe(7);
});

test('the failing shapes say why, in their section', () => {
  const err = (over) => validateGhoulSheet(miraSheet(over), DARIUS);
  expect(err({ attributes: { ...miraSheet().attributes, wits: 4 } })[S.attributes]).toBe("Attributes don't match the Gifted mortal spread.");
  expect(err({ skills: { ...miraSheet().skills, occult: 1 } })[S.skills]).toBe("Skills don't match the Gifted mortal template: 2 at 4, 4 at 3, 4 at 2, 4 at 1.");
  expect(err({ specialties: [...miraSheet().specialties, { skill: 'subterfuge', name: 'Lies' }] })[S.skills]).toBe('The Gifted mortal template gives 3 specialties here (you named 4).');
  expect(err({ power: { discipline: 'Dominate', name: 'Mesmerize' } })[S.disciplines]).toBe("Dominate: a ghoul's power is level 1.");
  expect(err({ power: { discipline: 'Auspex', name: 'Heightened Senses' } })[S.disciplines]).toBe("Auspex is not one of the domitor's Disciplines.");
  expect(err({ power: { discipline: 'Dominate', name: 'Compel' } })[S.disciplines]).toBe("The domitor doesn't have Compel (Dominate): the first power is one the domitor has.");
  expect(err({ power: { discipline: '', name: '' } })[S.disciplines]).toBe('A ghoul starts with exactly one level-1 power (you have 0).');
  expect(err({ advantages: [...miraSheet().advantages, { id: 'background:resources', name: 'Resources', dots: 1, kind: 'background' }] })[S.advantages]).toBe('Advantages: at most 10 dots (you have 11).');
  expect(err({ flaws: [...miraSheet().flaws, { id: 'flaw:dark-secret', name: 'Dark Secret', dots: 1 }] })[S.advantages]).toBe('The Gifted mortal template allows at most 4 dots of Flaws (you have 5).');
  expect(err({ advantages: [{ id: 'background:herd', name: 'Herd', dots: 1, kind: 'background' }] })[S.advantages]).toBe('Herd is not open to ghouls: Herd belongs to Kindred (Players Guide p. 141).');
  expect(err({ bonds: [{ strength: 2 }, { name: 'Leyla', strength: 1 }], flaws: miraSheet().flaws.slice(1) })[S.bond]).toBe('A second Blood Bond needs the Two Masters Flaw.');
  expect(err({ retainerDots: 2 })[S.identity]).toBe('A Gifted mortal ghoul takes Retainers 3; the domitor pays 2.');
  expect(validateGhoulSheet(miraSheet(), null)[S.identity]).toBe("Choose the ghoul's domitor.");
  expect(err({ template: '' })[S.identity]).toBe('Choose a template for the ghoul.');
  expect(err({ template: 'player' })[S.humanity]).toBe('Write 1–3 Convictions, each with a Touchstone.');
});

test('a Retainers 2 ghoul has no Advantages (core p. 194)', () => {
  const average = {
    template: 'average',
    retainerDots: 2,
    attributes: { strength: 2, dexterity: 2, stamina: 3, charisma: 1, manipulation: 1, composure: 3, intelligence: 1, wits: 2, resolve: 1 },
    skills: skillsOf({ 3: ['drive', 'brawl', 'firearms'], 2: ['streetwise', 'larceny', 'stealth', 'athletics'], 1: ['insight', 'awareness', 'intimidation', 'melee', 'survival'] }),
    specialties: [],
  };
  expect(deriveGhoul(average).advantage_dots).toBe(0);
  expect(deriveGhoul({ ...average, retainerDots: null }).advantage_dots).toBe(3);
  expect(validateGhoulSheet(miraSheet({ ...average, advantages: [], flaws: [{ id: 'flaw:bondslave', name: 'Bondslave', dots: 2 }] }), DARIUS)).toEqual({});
});

test('Crone’s Curse takes a Health box', () => {
  expect(deriveGhoul(miraSheet({ flaws: [{ id: 'flaw:ghoul-crones-curse', name: "Crone's Curse", dots: 2 }] })).health).toBe(3);
});

test('templates, spreads and specialties', () => {
  expect(templateForRetainerDots(3)).toBe('gifted');
  expect(templateForRetainerDots(1)).toBe('weak');
  expect(GHOUL_TEMPLATES.deadly.attributes.reduce((a, b) => a + b, 0)).toBe(30);
  expect(emptyGhoulAttributes('deadly').strength).toBe(2);
  expect(emptyGhoulAttributes('gifted').strength).toBe(1);
  expect(ghoulAttributeStatus(miraSheet().attributes, 'gifted').every((r) => r.need === r.have)).toBe(true);
  expect(ghoulSpecialtyCount('gifted', miraSheet().skills)).toBe(3);
  expect(ghoulSpecialtyCount('player', miraSheet().skills)).toBe(3);
});

test('ghouls are offered ghoul Merits, not Herd, Feeding, thin-blood or coterie entries', () => {
  const merits = ghoulAdvantageOptions('merit').map((a) => a.id);
  const backgrounds = ghoulAdvantageOptions('background').map((a) => a.id);
  const flaws = ghoulAdvantageOptions('flaw').map((a) => a.id);
  expect(merits).toContain('merit:ghoul-blood-empathy');
  expect(flaws).toEqual(expect.arrayContaining(['flaw:ghoul-crones-curse', 'flaw:two-masters', 'flaw:bondslave', 'flaw:addiction']));
  expect(backgrounds).not.toContain('background:herd');
  expect(backgrounds).not.toContain('background:domain');
  expect(merits).not.toContain('merit:iron-gullet');
  const ids = [...merits, ...backgrounds, ...flaws];
  const catalog = Object.fromEntries(fixture.catalog.advantages.map((a) => [a.id, a]));
  expect(ids.some((id) => catalog[id].thin_blood || catalog[id].caitiff || catalog[id].coterie)).toBe(false);
  expect(ghoulLoresheetOptions().some((l) => l.thin_blood_only)).toBe(false);
});

test('the power step lists the domitor’s level-1 powers first', () => {
  const opts = ghoulPowerOptions(DARIUS, 'Dominate');
  expect(opts[0]).toEqual(expect.objectContaining({ name: 'Cloud Memory', domitorHas: true }));
  expect(opts.map((o) => o.name)).toEqual(expect.arrayContaining(['Compel', 'Slavish Devotion']));
  expect(opts.find((o) => o.name === 'Compel').domitorHas).toBe(false);
  expect(opts.some((o) => o.name === 'Mesmerize')).toBe(false);
});

test('which rows are ghouls and who may be a domitor', () => {
  const mira = { id: 30, sheet_kind: 'ghoul', wod_meta: { sheet_kind: 'ghoul', ghoul: { domitor: { character_id: 17 } } } };
  expect(isGhoul(mira)).toBe(true);
  expect(isGhoul(DARIUS)).toBe(false);
  expect(ghoulDomitorId(mira)).toBe(17);
  expect(ghoulDomitorId(DARIUS)).toBe(null);
  expect(canBeDomitor(DARIUS)).toBe(true);
  expect(canBeDomitor({ ...mira, rules_edition: 'v5' })).toBe(false);
  // a Classic vampire is a domitor too (its ghoul is a Classic sheet), not of the V5 forge
  expect(canBeDomitor({ ...DARIUS, rules_edition: 'classic' })).toBe(true);
  expect(isV5Domitor({ ...DARIUS, rules_edition: 'classic' })).toBe(false);
  expect(isV5Domitor(DARIUS)).toBe(true);
  expect(canBeDomitor({ ...DARIUS, system_type: 'mage' })).toBe(false);
});

test('the client messages read in Greek', () => {
  setLanguage('el');
  try {
    expect(translateSheetError("Attributes don't match the Gifted mortal spread.")).toBe('Τα Attributes δεν ταιριάζουν με την κατανομή του προτύπου Gifted θνητός.');
    expect(translateSheetError('Herd is not open to ghouls: Herd belongs to Kindred (Players Guide p. 141).')).toBe(
      'Το Herd δεν επιτρέπεται σε ghouls: το Herd ανήκει στους Kindred (Players Guide σελ. 141).'
    );
    expect(translateSheetError("Skills don't match the Gifted mortal template: 2 at 4, 4 at 3, 4 at 2, 4 at 1.")).toBe(
      'Τα Skills δεν ταιριάζουν με το πρότυπο Gifted θνητός: 2 στο 4, 4 στο 3, 4 στο 2, 4 στο 1.'
    );
  } finally {
    setLanguage('en');
  }
});
