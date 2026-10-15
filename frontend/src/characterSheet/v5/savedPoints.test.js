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

  it('raises own rows, never a predator grant', () => {
    expect(spendChanges(meta(), [{ name: 'resources', dots: 1 }, { name: 'Herd', dots: 1, kind: 'background' }])).toEqual([
      { name: 'Resources', kind: 'background', from: 3, to: 4 },
      { name: 'Herd', kind: 'background', from: 0, to: 1 },
    ]);
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
      { code: 'dots_range', params: { name: 'Allies', to: 6 } },
    ]);
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
    expect(spendProblemText({ code: 'clan_only', params: { name: 'Tunnel Rat', clans: ['Nosferatu', 'Malkavian'] } })).toBe(
      'Tunnel Rat is only for Nosferatu and Malkavian.'
    );
    expect(spendProblemText({ code: 'adv_dots_allowed', params: { name: 'Mask', to: 3, allowed: [1, 2] } })).toBe('Mask takes 1 or 2 dots, not 3.');
    expect(spendProblemText({ code: 'cannot_buy', params: { name: 'Iron Gullet', clan: 'Ventrue' } })).toBe('Ventrue characters cannot take Iron Gullet.');
    [
      'over_cap', 'dots_range', 'unknown_advantage', 'not_an_advantage', 'adv_dots_range', 'book_not_allowed',
      'no_saved_specialty', 'specialty_not_allowed', 'specialty_duplicate', 'thin_blood_only', 'caitiff_only',
      'ghoul_only', 'coterie_advantage', 'requires', 'not_repeatable',
    ].forEach((code) => {
      const text = spendProblemText({ code, params: { name: 'X', skill: 'occult', to: 6, min: 1, max: 5, cap: 1, total: 2, book: 'b', requires: 'Haven 2' } });
      expect(text).not.toBe(code);
      expect(text).not.toMatch(/\{\{/);
    });
  });

  it('summarises a request', () => {
    expect(spendSummary({ kind: 'saved_advantage', payload: { items: [{ name: 'Resources', dots: 1 }] } })).toBe('Resources +1');
    expect(spendSummary({ kind: 'saved_advantage', payload: {}, changes: [{ name: 'Resources', from: 3, to: 4 }] })).toBe('Resources 3 → 4');
    expect(spendSummary({ kind: 'saved_specialty', payload: { skill: 'occult', name: 'Byzantine rites' } })).toBe('Occult: Byzantine rites');
  });
});
