import fixture from './__fixtures__/creation-cases.json';
import { applyV5Catalog } from './rulesData';
import {
  savedBalance,
  spendChanges,
  spendProblemText,
  spendSummary,
  validateSpend,
} from './savedPoints';

const meta = (over = {}) => ({
  clan: 'Toreador',
  advantages: [
    { name: 'Resources', dots: 3, kind: 'background' },
    { name: 'Herd', dots: 2, kind: 'predator' },
    { name: 'Allies', dots: 4, kind: 'background' },
  ],
  saved: { advantage_dots: 2, specialty: 1 },
  ...over,
});
const skills = {
  social: { persuasion: 3 },
  mental: { occult: 1, science: 0 },
  specialties: [{ skill: 'occult', name: 'Vampires' }],
};
const adv = (...items) => ({ kind: 'saved_advantage', items });
const spec = (skill, name) => ({ kind: 'saved_specialty', skill, name });
const codes = (check) => check.problems.map((p) => p.code);

describe('saved points: the live rule check (same codes as the server)', () => {
  it('reads the balance', () => {
    expect(savedBalance({})).toEqual({ advantage_dots: 0, specialty: 0 });
    expect(savedBalance(meta())).toEqual({ advantage_dots: 2, specialty: 1 });
  });

  it('raises own rows by name, never a predator grant; loresheets take levels', () => {
    const out = spendChanges(meta(), [
      { name: 'resources', dots: 1 },
      { name: 'Herd', dots: 1, kind: 'background' },
      { id: 'loresheet:the-bahari', name: 'The Bahari', kind: 'loresheet', levels: [2] },
    ]);
    expect(out.map(({ row, ...c }) => c)).toEqual([
      { name: 'Resources', kind: 'background', from: 3, to: 4 },
      { name: 'Herd', kind: 'background', from: 0, to: 1 },
      { name: 'The Bahari', kind: 'loresheet', from: 0, to: 2, levels: [2] },
    ]);
    expect(out[2].row).toEqual({ id: 'loresheet:the-bahari', name: 'The Bahari', kind: 'loresheet', dots: 2, levels: [2] });
    const m = meta();
    m.advantages.push({ name: 'The Bahari', kind: 'loresheet', dots: 1, levels: [1] });
    expect(spendChanges(m, [{ name: 'The Bahari', kind: 'loresheet', levels: [3] }])[0].row.levels).toEqual([1, 3]);
  });

  it('passes a spend within the saved dots', () => {
    expect(validateSpend(meta(), adv({ name: 'Contacts', dots: 2, kind: 'background' }), {}, skills)).toEqual({
      ok: true,
      problems: [],
      house_rule: false,
    });
  });

  it('flags more than saved, the cap and a row past 5 as house rules', () => {
    const short = validateSpend(meta(), adv({ name: 'Contacts', dots: 3 }), {}, skills);
    expect(short.house_rule).toBe(true);
    expect(short.problems).toEqual([{ code: 'saved_short', params: { need: 3, have: 2 } }]);
    const cap = validateSpend(meta(), adv({ name: 'Contacts', dots: 2 }), { saved_points: { advantage_dots_cap: 1, allow_specialty: true } }, skills);
    expect(codes(cap)).toEqual(['over_cap']);
    expect(validateSpend(meta(), adv({ name: 'Allies', dots: 2 }), {}, skills).problems).toEqual([
      { code: 'adv_dots_range', params: { name: 'Allies', dots: 6, min: 1, max: 5 } },
    ]);
    // a loresheet level counts its rating; one taken twice is the creation check's loresheet_levels
    const lore = { name: 'The Bahari', kind: 'loresheet', levels: [3] };
    expect(codes(validateSpend(meta(), adv(lore), {}, skills))).toEqual(['saved_short']);
  });

  it('counts earlier spends from saved points against the cap', () => {
    const m = meta({ saved: { advantage_dots: 4 } });
    m.advantages[0] = { name: 'Resources', dots: 4, kind: 'background', saved_dots: 1 };
    const capped = { saved_points: { advantage_dots_cap: 2, allow_specialty: true } };
    expect(validateSpend(m, adv({ name: 'Contacts', dots: 1 }), capped, skills).ok).toBe(true);
    expect(validateSpend(m, adv({ name: 'Contacts', dots: 2 }), capped, skills).problems).toEqual([
      { code: 'over_cap', params: { cap: 2, total: 3 } },
    ]);
  });

  it('checks the specialty', () => {
    expect(validateSpend(meta(), spec('persuasion', 'Bargaining'), {}, skills).ok).toBe(true);
    expect(codes(validateSpend(meta(), spec('science', 'Chemistry'), {}, skills))).toEqual(['skill_no_dot']);
    expect(codes(validateSpend(meta(), spec('occult', ' vampires '), {}, skills))).toEqual(['specialty_duplicate']);
    expect(codes(validateSpend(meta({ saved: { advantage_dots: 2 } }), spec('persuasion', 'Bargaining'), {}, skills))).toEqual(['no_saved_specialty']);
    const off = { saved_points: { advantage_dots_cap: 7, allow_specialty: false } };
    expect(codes(validateSpend(meta(), spec('persuasion', 'Bargaining'), off, skills))).toEqual(['specialty_not_allowed']);
  });

  it('puts every code in words', () => {
    expect(spendProblemText({ code: 'saved_short', params: { need: 3, have: 2 } })).toBe('Needs 3 saved Advantage dots; 2 are saved.');
    expect(spendProblemText({ code: 'skill_no_dot', params: { skill: 'animal_ken' } })).toBe('Animal Ken needs at least one dot for a specialty.');
    // the creation check's codes, in the forge's words
    expect(spendProblemText({ code: 'adv_dots_range', params: { name: 'Allies', dots: 7, min: 1, max: 6 } })).toBe('Allies: 1–6 dots (you have 7).');
    expect(spendProblemText({ code: 'adv_restricted', params: { name: 'Iron Gullet', clan: 'Ventrue' } })).toBe('Iron Gullet is not open to Ventrue.');
    [
      'over_cap', 'adv_unknown', 'adv_repeat', 'adv_requires', 'book_not_allowed', 'catalog_error', 'loresheet_levels',
      'loresheet_restricted', 'custom_row', 'caitiff_status', 'no_saved_specialty', 'specialty_not_allowed', 'specialty_duplicate',
    ].forEach((code) => {
      const text = spendProblemText({ code, params: { name: 'X', skill: 'occult', dots: 6, min: 1, max: 5, cap: 1, total: 2, book: 'b', requires: 'Haven 2', clan: 'Brujah', levels: [1] } });
      expect(text).not.toMatch(/\{\{|\(adv_|\(loresheet_/);
    });
  });

  it('summarises a request', () => {
    expect(spendSummary({ kind: 'saved_advantage', payload: { items: [{ name: 'Resources', dots: 1 }] } })).toBe('Resources +1');
    expect(spendSummary({ kind: 'saved_advantage', payload: {}, changes: [{ name: 'Resources', from: 3, to: 4 }] })).toBe('Resources 3 → 4');
    expect(spendSummary({ kind: 'saved_specialty', payload: { skill: 'occult', name: 'Byzantine rites' } })).toBe('Occult: Byzantine rites');
    expect(spendSummary({ kind: 'saved_advantage', payload: { items: [{ name: 'The Bahari', kind: 'loresheet', levels: [2] }] } })).toBe('The Bahari level 2');
    expect(spendSummary({ kind: 'saved_advantage', payload: {}, changes: [{ name: 'The Bahari', from: 1, to: 4, levels: [1, 2] }] })).toBe('The Bahari levels 1, 2');
  });
});

describe('saved points: the live check with the catalog loaded', () => {
  beforeAll(() => applyV5Catalog(fixture.catalog));
  afterAll(() => applyV5Catalog(null));

  it('rates rows as the catalog prints them (Allies goes to 6)', () => {
    const m = meta({ advantages: [{ id: 'background:allies', name: 'Allies (police)', dots: 5, kind: 'background' }], saved: { advantage_dots: 3 } });
    expect(validateSpend(m, adv({ name: 'Allies (police)', dots: 1, kind: 'background' }), {}, skills).ok).toBe(true);
    expect(validateSpend(m, adv({ name: 'Allies (police)', dots: 2, kind: 'background' }), {}, skills).problems).toEqual([
      { code: 'adv_dots_range', params: { name: 'Allies (police)', dots: 7, min: 1, max: 6 } },
    ]);
    expect(codes(validateSpend(m, adv({ id: 'background:mask', name: 'Mask', dots: 3, kind: 'background' }), {}, skills))).toEqual(['adv_dots_range']);
    expect(codes(validateSpend(m, adv({ name: 'Made Up', dots: 1, kind: 'merit' }), {}, skills))).toEqual(['adv_unknown']);
  });

  it('loresheets: each level once, and only those open to the clan', () => {
    const m = meta({ advantages: [{ id: 'loresheet:the-bahari', name: 'The Bahari', kind: 'loresheet', dots: 1, levels: [1] }] });
    expect(codes(validateSpend(m, adv({ name: 'The Bahari', kind: 'loresheet', levels: [1] }), {}, skills))).toEqual(['loresheet_levels']);
    expect(validateSpend(m, adv({ name: 'The Bahari', kind: 'loresheet', levels: [2] }), {}, skills).ok).toBe(true);
    const helena = { id: 'loresheet:descendant-of-helena', name: 'Descendant of Helena', kind: 'loresheet', levels: [1] };
    expect(validateSpend(meta(), adv(helena), {}, skills).ok).toBe(true); // meta() is a Toreador
    expect(codes(validateSpend(meta({ clan: 'Brujah' }), adv(helena), {}, skills))).toEqual(['loresheet_restricted']);
  });

  it('Student of Kirin Taunk: the Thin-Blood Alchemist Merit brings Thin-Blood Alchemy', () => {
    const kirin = { id: 'loresheet:student-of-kirin-taunk', name: 'Student of Kirin Taunk', kind: 'loresheet', levels: [1] };
    const m = meta({ clan: 'Thin-blood', advantages: [], thin_blood_merits: ['Day Drinker', 'Thin-Blood Alchemist'] });
    expect(validateSpend(m, adv(kirin), {}, skills).ok).toBe(true);
    expect(codes(validateSpend({ ...m, thin_blood_merits: ['Day Drinker'] }, adv(kirin), {}, skills))).toEqual(['loresheet_restricted']);
  });
});
