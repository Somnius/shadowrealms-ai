/**
 * The forge rules with the served catalog applied (rulesData.applyV5Catalog): clans, predator
 * grants with choices, power checks, the starting ceremony. Uses a small invented fixture.
 */
import fixture from '../../rules/__fixtures__/v5-catalog.json';
import { applyV5Catalog, bookRef, clanNames, descIn, getV5Rules, powersOf, predatorNames } from './rulesData';
import {
  clanInfo,
  creationDisciplineOptions,
  finalRituals,
  predatorDisciplineOptions,
  predatorSpecialtyLabels,
  predatorInfo,
  resolvePredatorGrants,
  startingCeremonyOptions,
  validateV5Powers,
} from './validation';

beforeAll(() => applyV5Catalog(fixture));
afterAll(() => applyV5Catalog(null));

const sheet = (over) => ({
  clan: 'Hecata',
  age: 'neonate',
  generation: 13,
  disciplines: [
    { name: 'Oblivion', level: 2, powers: [] },
    { name: 'Auspex', level: 1, powers: [] },
  ],
  ...over,
});

describe('registry', () => {
  it('switches to the catalog and back', () => {
    expect(getV5Rules().source).toBe('catalog');
    expect(clanNames()).toEqual(['Hecata', 'Ventrue', 'Caitiff', 'Thin-blood']);
    expect(predatorNames()).toContain('Grim Reaper');
    applyV5Catalog(null);
    expect(getV5Rules().source).toBe('rules');
    expect(clanNames()).toContain('Brujah');
    applyV5Catalog(fixture);
  });

  it('clans carry Discipline names, bane, compulsion and their description', () => {
    const h = clanInfo('Hecata');
    expect(h.disciplines).toEqual(['Auspex', 'Fortitude', 'Oblivion']);
    expect(h.bane).toBe('Painful Kiss');
    expect(h.compulsion).toBe('Morbidity');
    expect(descIn(h, 'el')).toBe('Κείμενο δοκιμής.');
    expect(descIn(h, 'xx')).toBe('Test clan text.');
    expect(bookRef(h)).toBe('Players Guide, p. 25');
    expect(creationDisciplineOptions('Caitiff')).not.toContain('Thin-Blood Alchemy');
  });

  it('powers keep amalgam and prerequisite by name', () => {
    const d = powersOf('Dominate');
    expect(d.find((p) => p.name === 'Implant Suggestion').amalgam).toEqual({ discipline: 'Presence', level: 1 });
    expect(d.find((p) => p.name === 'Submerged Directive').prerequisite).toEqual([['Mesmerize']]);
  });

  it('reads an all_of prerequisite as groups', () => {
    applyV5Catalog({
      ...fixture,
      disciplines: [
        ...fixture.disciplines,
        { id: 'discipline:animalism', name: 'Animalism', powers: [
          { id: 'power:animalism:animal-messenger', name: 'Animal Messenger', level: 2 },
          { id: 'power:animalism:messengers-command', name: "Messenger's Command", level: 3,
            prerequisite: { all_of: [{ power_id: 'power:animalism:animal-messenger' }, { any_of: ['power:dominate:compel', 'power:dominate:mesmerize'] }] } },
        ] },
      ],
    });
    expect(powersOf('Animalism')[1].prerequisite).toEqual([['Animal Messenger'], ['Compel', 'Mesmerize']]);
    applyV5Catalog(fixture);
  });
});

describe('predator types from the catalog', () => {
  it('clan-only Discipline choices and specialty labels', () => {
    expect(predatorDisciplineOptions('Grim Reaper', 'Hecata')).toEqual(['Auspex', 'Oblivion']);
    expect(predatorDisciplineOptions('Grim Reaper', 'Ventrue')).toEqual(['Auspex']);
    expect(predatorSpecialtyLabels(predatorInfo('Grim Reaper'))).toEqual(['Awareness (Death)', 'Larceny (Forgery)']);
  });

  it('"one of" needs a choice and then gives that option', () => {
    const s = sheet({ predatorType: 'Grim Reaper' });
    const none = resolvePredatorGrants(s);
    expect(none.problems).toEqual(['Grim Reaper: choose one of Allies or Influence.']);
    expect(none.flaws).toEqual([{ name: 'Prey Exclusion (healthy mortals)', dots: 1, kind: 'predator' }]);
    const picked = resolvePredatorGrants({ ...s, predatorChoices: { a0: 1 } });
    expect(picked.problems).toEqual([]);
    expect(picked.advantages).toEqual([{ name: 'Influence (medical community)', dots: 1, kind: 'predator' }]);
  });

  it('a split must add up to its total', () => {
    const s = sheet({ predatorType: 'Osiris' });
    expect(resolvePredatorGrants({ ...s, predatorChoices: { a0: { 0: 1, 1: 1 } } }).problems).toEqual([
      'Osiris: share 3 dots between Fame and Herd (you have 2).',
    ]);
    const ok = resolvePredatorGrants({ ...s, predatorChoices: { a0: { 0: 2, 1: 1 } } });
    expect(ok.problems).toEqual([]);
    expect(ok.advantages.map((a) => `${a.name} ${a.dots}`)).toEqual(['Fame 2', 'Herd 1']);
  });

  it('an unprinted rating is asked of the player', () => {
    const s = sheet({ predatorType: 'Roadside Killer' });
    expect(resolvePredatorGrants(s).problems[0]).toMatch(/choose the dots for Prey Exclusion/);
    const ok = resolvePredatorGrants({ ...s, predatorChoices: { 'f0:0:dots': 2 } });
    expect(ok.problems).toEqual([]);
    expect(ok.flaws).toEqual([{ name: 'Prey Exclusion (locals)', dots: 2, kind: 'predator' }]);
  });
});

describe('powers and ceremonies', () => {
  const ventrue = (powers, extra = {}) => ({
    clan: 'Ventrue',
    disciplines: [
      { name: 'Dominate', level: 2, powers },
      { name: 'Fortitude', level: 1, powers: [] },
    ],
    ...extra,
  });

  it('accepts powers at or below the rating', () => {
    expect(validateV5Powers(ventrue(['Cloud Memory', 'Mesmerize']))).toBeNull();
  });

  it('refuses a power above the rating, twice, unknown, or without its prerequisite or amalgam', () => {
    expect(validateV5Powers(ventrue(['Cloud Memory', 'Submerged Directive']))).toBe(
      'Submerged Directive is a level 3 power; Dominate is at 2.'
    );
    expect(validateV5Powers(ventrue(['Cloud Memory', 'Cloud Memory']))).toBe('Dominate: Cloud Memory is taken twice.');
    expect(validateV5Powers(ventrue(['Mind Bullet']))).toBe('Mind Bullet is not a Dominate power.');
    expect(validateV5Powers(ventrue(['Implant Suggestion']))).toBe('Implant Suggestion also needs Presence 1.');
    const three = { ...ventrue([]), predatorDiscipline: 'Dominate', predatorType: 'Montero', extraPowers: {} };
    three.disciplines[0].powers = ['Cloud Memory', 'Submerged Directive', ''];
    expect(validateV5Powers(three)).toBe('Submerged Directive needs Mesmerize first.');
  });

  it('a ceremony needs its prerequisite Oblivion power, and is stored with kind ceremony', () => {
    const s = sheet();
    expect(startingCeremonyOptions(s)).toEqual([]);
    s.disciplines[0].powers = ['The Binding Fetter', 'Shadow Cloak'];
    expect(startingCeremonyOptions(s).map((c) => c.name)).toEqual(['Summon Spirit']);
    expect(finalRituals({ ...s, startingCeremony: 'Summon Spirit' })).toEqual([
      { name: 'Summon Spirit', level: 1, source: 'creation', kind: 'ceremony' },
    ]);
  });
});
