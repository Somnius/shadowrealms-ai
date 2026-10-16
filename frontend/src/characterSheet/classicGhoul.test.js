import {
  BLOOD_POOL_MAX,
  CLASSIC_GHOUL_SECTION_IDS as S,
  GHOUL_FREEBIE_RULES,
  buildClassicGhoulPayload,
  clanAllows,
  deriveClassicGhoul,
  disciplineCap,
  domitorBackgroundDots,
  domitorGeneration,
  ghoulAbilityPools,
  ghoulAttributePools,
  ghoulDisciplineOptions,
  potenceFirst,
  rollStartingPool,
  validateClassicGhoulSheet,
  classicGhoulServerErrors,
} from './classicGhoul';
import { abilityPools, attributePools, computeClassicFreebies } from './validation';
import { translateSheetError } from './i18nErrors';
import { setLanguage } from '../i18n';
import { THEO, martaSheet } from './__fixtures__/classicGhoulFixtures';

afterEach(() => setLanguage('en', { remember: false, save: false }));

test('the budgets are Fatal Addiction’s, through the shared pool helpers', () => {
  expect(ghoulAttributePools('physical')).toEqual({ physical: 6, social: 4, mental: 3 });
  expect(ghoulAttributePools('mental')).toEqual({ physical: 3, social: 4, mental: 6 });
  expect(ghoulAbilityPools('skills')).toEqual({ talents: 7, skills: 11, knowledges: 4 });
  // a vampire's stay as they were
  expect(attributePools('physical')).toEqual({ physical: 7, social: 5, mental: 3 });
  expect(abilityPools('talents')).toEqual({ talents: 13, skills: 9, knowledges: 5 });
  expect(GHOUL_FREEBIE_RULES.points).toBe(21);
  expect(GHOUL_FREEBIE_RULES.costs.discipline).toBe(10);
});

test('the domitor’s generation sets the Discipline cap and the Domitor Background', () => {
  expect(domitorGeneration(THEO)).toBe(12);
  expect(domitorGeneration({ wod_meta: { generation: '9th' } })).toBe(9);
  expect(domitorGeneration({ wod_meta: {} })).toBe(13);
  expect([13, 12, 8, 7, 6, 5, 4].map(disciplineCap)).toEqual([1, 1, 1, 2, 3, 4, 5]);
  expect([13, 11, 10, 9, 8, 7, 6].map(domitorBackgroundDots)).toEqual([1, 1, 2, 2, 3, 4, 5]);
});

test('a vassal learns its domitor’s Disciplines or an instinctive one; Protean and Thaumaturgy by clan', () => {
  expect(ghoulDisciplineOptions(THEO, 'vassal')).toEqual(['Celerity', 'Dominate', 'Fortitude', 'Presence']);
  const tremere = { ...THEO, wod_meta: { clan: 'Tremere', disciplines: [{ name: 'Thaumaturgy', dots: 2 }] } };
  expect(ghoulDisciplineOptions(tremere, 'vassal')).toContain('Thaumaturgy');
  const independent = ghoulDisciplineOptions(THEO, 'independent');
  expect(independent).toContain('Obfuscate');
  expect(independent).not.toContain('Potence');
  expect(independent).not.toContain('Thaumaturgy');
  expect(independent).not.toContain('Protean');
  expect(clanAllows('Protean', 'vassal', { wod_meta: { clan: 'Gangrel' } })).toBe(true);
  expect(clanAllows('Protean', 'independent', { wod_meta: { clan: 'Gangrel' } })).toBe(false);
});

test('the starting Blood Pool is a roll: an independent halves it, a vassal may reroll a 1', () => {
  expect(rollStartingPool('vassal', () => 0.65)).toEqual({ roll: 7, pool: 7, rerollable: false });
  expect(rollStartingPool('independent', () => 0.65)).toEqual({ roll: 7, pool: 4, rerollable: false });
  expect(rollStartingPool('vassal', () => 0)).toEqual({ roll: 1, pool: 1, rerollable: true });
  expect(rollStartingPool('independent', () => 0)).toEqual({ roll: 1, pool: 1, rerollable: false });
  expect(rollStartingPool('vassal', () => 0.9999)).toEqual({ roll: 10, pool: 10, rerollable: false });
  for (let i = 0; i < 50; i += 1) {
    const { pool } = rollStartingPool('vassal');
    expect(pool >= 1 && pool <= BLOOD_POOL_MAX).toBe(true);
  }
});

test('a legal sheet passes and derives Humanity, Willpower and no freebies', () => {
  expect(validateClassicGhoulSheet(martaSheet(), THEO)).toEqual({});
  const d = deriveClassicGhoul(martaSheet());
  expect([d.humanity, d.willpower, d.freebies.spent, d.freebies.available]).toEqual([6, 4, 0, 21]);
});

test('freebies at a ghoul’s prices: a Discipline dot is 10', () => {
  const s = martaSheet({ disciplines: [{ name: 'Potence', dots: 1 }, { name: 'Dominate', dots: 1 }, { name: 'Celerity', dots: 1 }], willpowerBonus: 2 });
  const d = deriveClassicGhoul(s);
  expect(d.freebies.lines).toEqual([
    { key: 'disciplines', label: 'Disciplines', dots: 1, cost: 10 },
    { key: 'willpower', label: 'Willpower', dots: 2, cost: 2 },
  ]);
  expect(d.freebies.remaining).toBe(9);
  // the same call without `rules` prices a vampire's
  const vamp = computeClassicFreebies({ systemType: 'vampire', disciplines: [{ dots: 4 }], backgrounds: [], virtues: {}, meritRows: [] });
  expect(vamp.lines).toEqual([{ key: 'disciplines', label: 'Disciplines', dots: 1, cost: 7 }]);
  expect(vamp.available).toBe(15);
});

test('each rule once', () => {
  const v = (extra, dom = THEO) => validateClassicGhoulSheet(martaSheet(extra), dom);
  expect(v({}, null)[S.identity]).toBe("Choose the ghoul's domitor.");
  expect(v({ name: ' ' })[S.identity]).toBe('Character name is required.');
  expect(v({ kind: 'revenant' })[S.identity]).toMatch(/vassal or independent/);
  expect(v({ attributes: { ...martaSheet().attributes, strength: 2 } })[S.attributes]).toMatch(/^Physical: add exactly 6 dots/);
  expect(v({ abilities: { ...martaSheet().abilities, law: 1 } })[S.abilities]).toMatch(/^Knowledges must use all 4 dots/);
  expect(v({ disciplines: [{ name: 'Dominate', dots: 1 }] })[S.advantages]).toMatch(/^Every ghoul has Potence 1 or more\./);
  expect(v({ disciplines: [{ name: 'Potence', dots: 1 }] })[S.advantages]).toBe('Place the dot in a Discipline besides Potence.');
  expect(v({ disciplines: [{ name: 'Potence', dots: 2 }, { name: 'Dominate', dots: 1 }] })[S.advantages]).toBe(
    'Potence 2: the ghoul of a generation 12 domitor learns Disciplines up to 1.'
  );
  expect(v({ disciplines: [{ name: 'Potence', dots: 1 }, { name: 'Obfuscate', dots: 1 }] })[S.advantages]).toBe('Obfuscate is not a Discipline this ghoul can learn.');
  expect(v({ kind: 'independent', backgrounds: [{ name: 'Resources', dots: 3 }, { name: 'Contacts', dots: 2 }], disciplines: [{ name: 'Potence', dots: 1 }, { name: 'Obfuscate', dots: 1 }] })).toEqual({});
  // Fatal Addiction p. 65: only vassals buy Domitor
  expect(v({ kind: 'independent', disciplines: [{ name: 'Potence', dots: 1 }, { name: 'Obfuscate', dots: 1 }] })[S.advantages]).toBe('Only a vassal takes the Domitor Background.');
  // the server's text caps (backend/services/classic_ghoul.py), on the field's section
  expect(v({ feedingLast: 'x'.repeat(61) })[S.bond]).toBe('Last fed: at most 60 characters.');
  expect(v({ feedingLast: 'x'.repeat(60), overdosing: 'x'.repeat(120), bondNote: 'x'.repeat(500), duties: 'x'.repeat(200) })).toEqual({});
  expect(v({ overdosing: 'x'.repeat(121) })[S.bond]).toBe('Overdosing: at most 120 characters.');
  expect(v({ feedingNote: 'x'.repeat(501) })[S.bond]).toBe('Feeding note: at most 500 characters.');
  expect(v({ concept: 'x'.repeat(201) })[S.identity]).toBe('Concept: at most 200 characters.');
  expect(v({ ghouledSince: 'x'.repeat(201) })[S.identity]).toBe('Ghoul since: at most 200 characters.');
  expect(v({ backgrounds: [{ name: 'Herd', dots: 1 }, { name: 'Resources', dots: 4 }] })[S.advantages]).toBe('Ghouls take no Herd Background.');
  expect(v({ backgrounds: [{ name: 'Resources', dots: 4 }] })[S.advantages]).toBe('Place all 5 Background dots.');
  expect(v({ virtues: { conscience: 3, self_control: 3, courage: 3 } })[S.advantages]).toMatch(/^Virtues: 1 free dot each plus 7 more/);
  expect(v({ bloodPool: null })[S.advantages]).toBe('Roll or set the starting Blood Pool (1–10).');
  expect(v({ bloodPool: 11 })[S.advantages]).toBe('Roll or set the starting Blood Pool (1–10).');
  expect(v({ bondStage: 4 })[S.bond]).toBe('Blood Bond: 0 to 3 drinks.');
  expect(v({ nature: '' })[S.identity]).toBe('Enter your Nature (free text), or pick a preset archetype.');
  expect(v({ willpowerBonus: 22 })[S.freebies]).toBe('Freebie points overspent: 22 of 21.');
  // a 6th-generation domitor's ghoul learns up to 3
  const elder = { ...THEO, wod_meta: { ...THEO.wod_meta, generation: '6' } };
  expect(v({ disciplines: [{ name: 'Potence', dots: 3 }, { name: 'Dominate', dots: 1 }], willpowerBonus: 0 }, elder)[S.advantages]).toBeUndefined();
});

test('the messages read in Greek', () => {
  setLanguage('el', { remember: false, save: false });
  const msgs = [
    'Every ghoul has Potence 1 or more.',
    'Place the dot in a Discipline besides Potence.',
    'Potence 2: the ghoul of a generation 12 domitor learns Disciplines up to 1.',
    'Obfuscate is not a Discipline this ghoul can learn.',
    'Ghouls take no Herd Background.',
    'Place all 5 Background dots.',
    'Roll or set the starting Blood Pool (1–10).',
    'Blood Bond: 0 to 3 drinks.',
    'Choose whether the ghoul is a vassal or independent.',
    'Only a vassal takes the Domitor Background.',
    'Last fed: at most 60 characters.',
    'Abcdefghijklmnopqrst…: a name is at most 60 characters.',
  ];
  msgs.forEach((m) => expect(translateSheetError(m)).not.toBe(m));
  expect(translateSheetError('Ghouls take no Herd Background.')).toContain('Herd');
  expect(translateSheetError('Last fed: at most 60 characters.')).toBe('Τελευταία φορά που ήπιε: έως 60 χαρακτήρες.');
});

test("the server's problems land on their sections, a too-long text as the client's message", () => {
  const e = classicGhoulServerErrors([
    'wod_meta.ghoul.feeding.last must be text of at most 60 characters',
    'wod_meta.ghoul.bond.stage must be between 0 and 3',
    'wod_meta.backgrounds[0]: ghouls take no Herd (Fatal Addiction)',
    'wod_meta.concept must be text of at most 200 characters',
    'attributes must be an object',
    'skills.talents must be an object',
  ]);
  expect(e[S.bond]).toBe('Last fed: at most 60 characters. wod_meta.ghoul.bond.stage must be between 0 and 3');
  expect(e[S.advantages]).toBe('wod_meta.backgrounds[0]: ghouls take no Herd (Fatal Addiction)');
  expect(e[S.identity]).toBe('Concept: at most 200 characters.');
  expect(e[S.attributes]).toBe('attributes must be an object');
  expect(e[S.abilities]).toBe('skills.talents must be an object');
});

test('the payload: a ghoul’s sheet with a Blood Pool object, Potence first, no clan or generation', () => {
  const p = buildClassicGhoulPayload(martaSheet({ disciplines: [{ name: 'Dominate', dots: 1 }, { name: 'Potence', dots: 1 }] }), THEO);
  expect(p.system_type).toBe('vampire');
  expect(p.skills.talents.alertness).toBe(3);
  expect(p.skills.allocation).toEqual({ primary: 'talents', pools: { talents: 11, skills: 7, knowledges: 4 } });
  const m = p.wod_meta;
  expect(m.sheet_kind).toBe('ghoul');
  expect(m.blood_pool).toEqual({ max: 10, current: 6, per_turn: 1 });
  expect(m.disciplines.map((d) => d.name)).toEqual(['Potence', 'Dominate']);
  expect(m.ghoul).toMatchObject({
    kind: 'vassal',
    domitor: { character_id: 21, name: 'Theodore Doukas', clan: 'Ventrue' },
    age: 51,
    apparent_age: 38,
    bond: { stage: 3, note: 'Third drink in 1998' },
    feeding: { last: '', note: 'A point each month' },
  });
  expect([m.humanity, m.willpower]).toEqual([6, 4]);
  ['clan', 'generation', 'sire', 'hunger', 'edition', 'advantages', 'flaws'].forEach((k) => expect(m).not.toHaveProperty(k));
  expect(buildClassicGhoulPayload(martaSheet({ age: '' }), THEO).wod_meta.ghoul).not.toHaveProperty('age');
});

test('potenceFirst', () => {
  expect(potenceFirst([{ name: 'Celerity' }, { name: 'potence' }, { name: '' }]).map((d) => d.name)).toEqual(['potence', 'Celerity']);
});
