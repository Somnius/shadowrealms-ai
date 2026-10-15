/**
 * Forge v2 part C: Merits, Backgrounds, Flaws and loresheets from the catalog (fixture: real names
 * and ratings, invented descriptions).
 */
import fixture from '../../rules/__fixtures__/v5-catalog.json';
import { act } from '@testing-library/react';
import { setLanguage } from '../../i18n';
import { translateSheetError } from '../i18nErrors';
import { advantageEntries, applyV5Catalog, findAdvantage, findLoresheet, predatorNames } from './rulesData';
import {
  advantageDotChoices,
  advantageOptions,
  buildV5Payload,
  clanFlaws,
  dotChoicesText,
  dotRequirement,
  loresheetOptions,
  ownFlawDots,
  predatorGroupOptions,
  predatorInfo,
  resolvePredatorGrants,
  thinBloodOptions,
  validateThinBloodMeritsFlaws,
  validateV5AdvantageRows,
  validateV5Sheet,
} from './validation';
import { V5_SECTION_IDS } from './constants';
import { meritRowsToAdvRows } from '../../components/characterCreation/v5/useV5ForgeState';

beforeAll(() => applyV5Catalog(fixture));
afterAll(() => applyV5Catalog(null));

const entry = (id) => advantageEntries().find((a) => a.id === id);
const ids = (list) => list.map((a) => a.id);
const row = (id, dots, extra = {}) => {
  const e = entry(id);
  return { id, name: e.name, dots, kind: e.kind, ...extra };
};
const lore = (id, levels) => ({
  id,
  name: findLoresheet({ id }).name,
  dots: levels.reduce((s, n) => s + n, 0),
  kind: 'loresheet',
  levels,
});

describe('the registry', () => {
  it('reads advantages and loresheets, with clan names and level descriptions', () => {
    expect(entry('background:allies')).toMatchObject({ name: 'Allies', kind: 'background', group: 'Allies', repeatable: true });
    expect(entry('merit:iron-gullet').cannot_buy_for).toEqual(['Ventrue']);
    const ashur = findLoresheet({ name: 'Harbingers of Ashur' });
    expect(ashur.clans_only).toEqual(['Hecata']);
    expect(ashur.levels[0]).toMatchObject({ dots: 1, name: 'The Ashen Mask', desc: { en: 'Test level 1 of Harbingers of Ashur.' } });
  });

  it('finds rows by id, by name with a note, and prefers the clan one for shared names', () => {
    expect(findAdvantage({ name: 'Allies (police)' }, 'background').id).toBe('background:allies');
    expect(findAdvantage({ name: 'Suspect' }, 'merit')).toBeNull(); // a Flaw, not a Merit
    expect(findAdvantage({ name: 'Clan Curse' }, 'flaw', 'thin_blood').id).toBe('flaw:thin-blood-clan-curse');
    expect(findAdvantage({ name: 'Clan Curse' }, 'flaw', 'caitiff').id).toBe('flaw:caitiff-clan-curse');
    expect(findAdvantage({ name: 'Suspect' }, 'flaw', 'caitiff').id).toBe('flaw:suspect');
  });

  it('an id the catalog doesn\'t know falls back to the name', () => {
    expect(findAdvantage({ id: 'merit:renamed-since', name: 'Beautiful' }, 'merit').id).toBe('merit:beautiful');
    expect(findAdvantage({ id: 'merit:renamed-since' }, 'merit')).toBeNull();
    expect(findLoresheet({ id: 'loresheet:old-id', name: 'The Bahari' }).id).toBe('loresheet:the-bahari');
  });

  it('predator grants carry the catalog names', () => {
    applyV5Catalog({
      ...fixture,
      advantages: [
        ...fixture.advantages,
        { ...fixture.advantages.find((a) => a.id === 'flaw:prey-exclusion'), id: 'flaw:methuselahs-thirst', name: "Methuselah's Thirst" },
      ],
      predator_types: [
        { ...fixture.predator_types[0], flaws: [{ pick: 'all', options: [{ id: 'flaw:methuselahs-thirst', dots: 1 }] }] },
      ],
    });
    expect(predatorNames()).toEqual(['Grim Reaper']);
    expect(predatorInfo('Grim Reaper').flaws[0].options[0]).toMatchObject({ id: 'flaw:methuselahs-thirst', name: "Methuselah's Thirst" });
    applyV5Catalog(fixture);
  });
});

describe('ratings', () => {
  it('a range, an open rating up to 5, a list, a fixed rating, none', () => {
    expect(advantageDotChoices(entry('background:allies'))).toEqual([1, 2, 3, 4, 5, 6]);
    expect(advantageDotChoices(entry('background:haven'))).toEqual([1, 2, 3, 4, 5]); // "•+"
    expect(advantageDotChoices(entry('background:mask'))).toEqual([1, 2]);
    expect(advantageDotChoices(entry('merit:beautiful'))).toEqual([2]);
    expect(advantageDotChoices(entry('merit:thin-blood-day-drinker'))).toEqual([]);
    expect(dotChoicesText([1, 2, 3, 4, 5, 6])).toBe('1–6');
    expect(dotChoicesText([1, 2])).toBe('1 or 2');
    expect(dotChoicesText([1, 3, 5])).toBe('1, 3 or 5');
    expect(dotChoicesText([2])).toBe('2');
  });

  it('reads dot requirements, others stay hints', () => {
    expect(dotRequirement(entry('merit:laboratory'))).toEqual({ name: 'Haven', dots: 2, onlyAbove1: false });
    expect(dotRequirement({ requires: 'more than one dot: Haven ••' })).toEqual({ name: 'Haven', dots: 2, onlyAbove1: true });
    expect(dotRequirement({ requires: 'Fame ••+' })).toEqual({ name: 'Fame', dots: 2, onlyAbove1: false });
    expect(dotRequirement({ requires: 'Blood Potency 1 or lower' })).toBeNull();
  });
});

describe('what a clan is offered', () => {
  it('hides ghoul, coterie, thin-blood and other clans\' entries, and the Loresheets Background', () => {
    const merits = ids(advantageOptions('Ventrue', 'merit'));
    expect(merits).toContain('merit:beautiful');
    expect(merits).not.toContain('merit:iron-gullet'); // Ventrue can't drink it
    expect(merits).not.toContain('merit:caitiff-mark-of-caine');
    expect(merits).not.toContain('merit:coterie-all-access');
    expect(merits).not.toContain('merit:ghoul-blood-empathy');
    expect(merits).not.toContain('merit:thin-blood-day-drinker');
    expect(ids(advantageOptions('Hecata', 'merit'))).toContain('merit:iron-gullet');
    expect(ids(advantageOptions('Ventrue', 'background'))).not.toContain('background:loresheets');
  });

  it('Caitiff: their own Merits, no positive Status, and Suspect from the start', () => {
    expect(ids(advantageOptions('Caitiff', 'merit'))).toContain('merit:caitiff-mark-of-caine');
    expect(ids(advantageOptions('Caitiff', 'background'))).not.toContain('background:status');
    expect(clanFlaws({ clan: 'Caitiff' })).toEqual([{ id: 'flaw:suspect', name: 'Suspect', dots: 1, kind: 'flaw', source: 'clan' }]);
    expect(clanFlaws({ clan: 'Ventrue' })).toEqual([]);
    expect(ownFlawDots({ clan: 'Caitiff', flaws: [row('flaw:dark-secret', 1)] })).toBe(2);
  });

  it('thin-bloods: no Status at creation, their own Merits and Flaws', () => {
    expect(ids(advantageOptions('Thin-blood', 'background'))).not.toContain('background:status');
    expect(ids(thinBloodOptions('merit'))).toEqual(['merit:thin-blood-day-drinker', 'merit:thin-blood-lifelike']);
    expect(ids(thinBloodOptions('flaw'))).toEqual(['flaw:thin-blood-baby-teeth', 'flaw:thin-blood-clan-curse', 'flaw:thin-blood-dead-flesh']);
  });

  it('loresheets follow their clan restriction', () => {
    expect(ids(loresheetOptions({ clan: 'Hecata' }))).toEqual(['loresheet:the-bahari', 'loresheet:harbingers-of-ashur']);
    expect(ids(loresheetOptions({ clan: 'Ventrue' }))).toEqual(['loresheet:the-bahari', 'loresheet:descendant-of-hardestadt']);
  });
});

describe('row checks', () => {
  const v = (advantages = [], flaws = [], extra = {}) => validateV5AdvantageRows({ clan: 'Hecata', advantages, flaws, ...extra });

  it('ratings as printed: Allies goes to 6, Mask is 1 or 2', () => {
    expect(v([row('background:allies', 6)])).toBeNull();
    expect(v([row('background:allies', 7)])).toBe('Allies takes 1–6 dots (you have 7).');
    expect(v([row('background:mask', 3)])).toBe('Mask takes 1 or 2 dots (you have 3).');
  });

  it('entries the clan can\'t take', () => {
    expect(validateV5AdvantageRows({ clan: 'Ventrue', advantages: [row('merit:iron-gullet', 3)] })).toBe(
      "Ventrue can't take Iron Gullet at creation."
    );
    expect(validateV5AdvantageRows({ clan: 'Caitiff', advantages: [row('background:status', 1)] })).toBe(
      "Caitiff can't take Status at creation."
    );
    expect(v([lore('loresheet:descendant-of-hardestadt', [1])])).toBe("Hecata can't take Descendant of Hardestadt at creation.");
  });

  it('how often: once, up to max_instances, the clan Flaw counted', () => {
    expect(v([row('merit:beautiful', 2), row('merit:beautiful', 2)])).toBe('Beautiful can be taken only once.');
    expect(v([row('background:allies', 1), row('background:allies', 2)])).toBeNull(); // repeatable
    const city = row('merit:city-secrets', 1);
    expect(v([city, city, city])).toBeNull();
    expect(v([city, city, city, city])).toBe('City Secrets can be taken at most 3 times.');
    // Suspect listed by the player stands in for the clan's one (an older or typed sheet)
    expect(clanFlaws({ clan: 'Caitiff', flaws: [row('flaw:suspect', 1)] })).toEqual([]);
    expect(clanFlaws({ clan: 'Caitiff', flaws: [{ name: 'Suspect (Camarilla)', dots: 1 }] })).toEqual([]);
    expect(validateV5AdvantageRows({ clan: 'Caitiff', flaws: [row('flaw:suspect', 1)] })).toBeNull();
    expect(validateV5AdvantageRows({ clan: 'Caitiff', flaws: [row('flaw:suspect', 1), row('flaw:suspect', 1)] })).toBe(
      'Suspect can be taken only once.'
    );
    expect(v([lore('loresheet:the-bahari', [1]), lore('loresheet:the-bahari', [2])])).toBe('The Bahari can be taken only once.');
  });

  it('a Background another entry needs', () => {
    expect(v([row('merit:laboratory', 1)])).toBe('Laboratory needs Haven at 2 dots or more.');
    expect(v([row('merit:laboratory', 1), row('background:haven', 1)])).toBe('Laboratory needs Haven at 2 dots or more.');
    expect(v([row('merit:laboratory', 1), row('background:haven', 2)])).toBeNull();
  });

  it('a predator Background counts with the dots bought on top of it (Trapdoor\'s Haven)', () => {
    applyV5Catalog({
      ...fixture,
      predator_types: [
        ...fixture.predator_types,
        { id: 'predator:trapdoor', name: 'Trapdoor', specialty_choice: [], discipline_choice: [],
          advantages: [{ pick: 'all', options: [{ id: 'background:haven', dots: 1 }] }], flaws: [] },
      ],
    });
    const s = { clan: 'Hecata', predatorType: 'Trapdoor' };
    expect(validateV5AdvantageRows({ ...s, advantages: [row('merit:laboratory', 1)] })).toBe('Laboratory needs Haven at 2 dots or more.');
    expect(validateV5AdvantageRows({ ...s, advantages: [row('merit:laboratory', 1), row('background:haven', 1)] })).toBeNull();
    // two havens of the player's own are two Backgrounds, not one at 2
    expect(v([row('merit:laboratory', 1), row('background:haven', 1), row('background:haven', 1)])).toBe(
      'Laboratory needs Haven at 2 dots or more.'
    );
    applyV5Catalog(fixture);
  });

  it('"ancilla or older" entries need an ancilla', () => {
    expect(v([], [row('flaw:archaic', 2)], { age: 'neonate' })).toBe('Archaic is only for ancillae or older.');
    expect(v([], [row('flaw:archaic', 2)], { age: 'ancilla' })).toBeNull();
  });

  it('a loresheet needs a level; custom and free-text rows are left alone', () => {
    expect(v([lore('loresheet:the-bahari', [])])).toBe('Pick at least one level of The Bahari.');
    expect(v([{ name: 'Homebrew Patron', dots: 2, kind: 'background', custom: true }])).toBeNull();
  });
});

describe('predator grants that stand for a group', () => {
  const mythic = (id, name, dots) => ({
    ...fixture.advantages.find((a) => a.id === 'flaw:prey-exclusion'),
    id, name, group: 'Mythic', dots: { min: dots, max: dots },
  });
  beforeAll(() =>
    applyV5Catalog({
      ...fixture,
      advantages: [...fixture.advantages, mythic('flaw:folkloric-bane', 'Folkloric Bane', 1), mythic('flaw:stake-bait', 'Stake Bait', 2)],
      predator_types: fixture.predator_types.map((p) =>
        p.id === 'predator:osiris'
          ? { ...p, flaws: [{ pick: 'split', dots_total: 2, options: [
              { id: 'flaw:enemies', dots: null }, { id: 'flaw:mythic', dots: null, note: 'any Mythic Flaw', group: true }] }] }
          : p
      ),
    })
  );
  afterAll(() => applyV5Catalog(fixture));

  it('"any Mythic Flaw" asks which one and stores it', () => {
    const opt = predatorInfo('Osiris').flaws[0].options[1];
    expect(opt).toMatchObject({ id: 'flaw:mythic', name: 'Mythic', group: 'Mythic', kind: 'flaw' });
    const s = { clan: 'Hecata', predatorType: 'Osiris', predatorChoices: { a0: { 0: 2, 1: 1 }, f0: { 0: 1, 1: 1 } } };
    expect(ids(predatorGroupOptions(s, opt))).toEqual(['flaw:folkloric-bane', 'flaw:stake-bait']);
    expect(resolvePredatorGrants(s).problems).toEqual(['Osiris: choose which Mythic Flaw.']);
    const ok = resolvePredatorGrants({ ...s, predatorChoices: { ...s.predatorChoices, 'f0:1:pick': 'flaw:folkloric-bane' } });
    expect(ok.problems).toEqual([]);
    expect(ok.flaws).toEqual([
      { id: 'flaw:enemies', name: 'Enemies', dots: 1, kind: 'predator' },
      { id: 'flaw:folkloric-bane', name: 'Mythic: Folkloric Bane', dots: 1, kind: 'predator' },
    ]);
  });

  it('without the group\'s entries in the catalog nothing is asked', () => {
    applyV5Catalog({ ...fixture, predator_types: [{ ...fixture.predator_types.find((p) => p.id === 'predator:osiris'),
      flaws: [{ pick: 'all', options: [{ id: 'flaw:mythic', dots: 1, note: 'any Mythic Flaw', group: true }] }] }] });
    const g = resolvePredatorGrants({ clan: 'Hecata', predatorType: 'Osiris', predatorChoices: { a0: { 0: 3 } } });
    expect(g.problems).toEqual([]);
    expect(g.flaws).toEqual([{ id: 'flaw:mythic', name: 'Mythic (any Mythic Flaw)', dots: 1, kind: 'predator', note: 'any Mythic Flaw' }]);
  });
});

describe('free-text rows typed before the catalog arrived', () => {
  it('become catalog rows where the name is known, custom rows otherwise', () => {
    const rows = meritRowsToAdvRows([
      { name: 'Allies (police)', points: 2, note: '' },
      { name: 'Homebrew Patron', points: 1, note: 'my sire' },
      { name: 'Dark Secret', points: -2, note: 'diablerie' },
      { name: '', points: 3 },
      { name: 'Nothing yet', points: 0 },
    ]);
    expect(rows.map(({ key, ...r }) => r)).toEqual([
      { kind: 'background', id: 'background:allies', name: 'Allies', dots: 2, note: 'police' },
      { kind: 'merit', id: 'custom', name: 'Homebrew Patron', dots: 1, note: 'my sire' },
      { kind: 'flaw', id: 'flaw:dark-secret', name: 'Dark Secret', dots: 2, note: 'diablerie' },
    ]);
  });
});

describe('the whole sheet and the payload', () => {
  let base;
  beforeAll(() => {
    base = { clan: 'Hecata', age: 'neonate', generation: 13, flaws: [row('flaw:dark-secret', 2)] };
  });

  it('loresheet dots count toward the 7 Advantage dots', () => {
    const err = validateV5Sheet({ ...base, advantages: [row('background:allies', 3), lore('loresheet:the-bahari', [1, 2, 3])] });
    expect(err[V5_SECTION_IDS.advantages]).toBe('Advantages: at most 7 dots (you have 9).');
  });

  it('1–5 only for free-text and custom rows', () => {
    const ok = validateV5Sheet({ ...base, advantages: [row('background:allies', 6)] });
    expect(ok[V5_SECTION_IDS.advantages]).toBeUndefined();
    const custom = validateV5Sheet({ ...base, advantages: [{ name: 'Patron', dots: 6, kind: 'background', custom: true }] });
    expect(custom[V5_SECTION_IDS.advantages]).toBe('Each Advantage or Flaw is 1–5 dots.');
  });

  it('rows keep id, name with the note, kind, levels and custom; the clan Flaw is stored', () => {
    const p = buildV5Payload({
      ...base,
      clan: 'Caitiff',
      advantages: [
        row('background:allies', 2, { note: 'police' }),
        lore('loresheet:the-bahari', [3, 1]),
        { name: 'Patron', dots: 1, kind: 'merit', custom: true, note: '' },
      ],
    });
    expect(p.wod_meta.advantages).toEqual([
      { id: 'background:allies', name: 'Allies (police)', dots: 2, kind: 'background', note: 'police' },
      { id: 'loresheet:the-bahari', name: 'The Bahari', dots: 4, kind: 'loresheet', levels: [1, 3] },
      { name: 'Patron', dots: 1, kind: 'merit', custom: true },
    ]);
    expect(p.wod_meta.flaws).toEqual([
      { id: 'flaw:suspect', name: 'Suspect', dots: 1, kind: 'flaw', source: 'clan' },
      { id: 'flaw:dark-secret', name: 'Dark Secret', dots: 2, kind: 'flaw' },
    ]);
    expect(p.merits_flaws.entries).toEqual([
      { name: 'Allies (police)', points: 2, note: 'background' },
      { name: 'The Bahari', points: 4, note: 'loresheet' },
      { name: 'Patron', points: 1, note: 'merit' },
      { name: 'Suspect', points: -1, note: 'clan flaw' },
      { name: 'Dark Secret', points: -2, note: 'flaw' },
    ]);
  });

  it('thin-blood Merits and Flaws: equal numbers, each once', () => {
    const tb = { clan: 'Thin-blood', thinBloodMerits: [{ name: 'Day Drinker' }], thinBloodFlaws: [{ name: 'Baby Teeth' }] };
    expect(validateThinBloodMeritsFlaws(tb)).toBeNull();
    expect(
      validateThinBloodMeritsFlaws({ ...tb, thinBloodMerits: [{ name: 'Day Drinker' }, { name: 'Day Drinker' }], thinBloodFlaws: [{ name: 'Baby Teeth' }, { name: 'Clan Curse' }] })
    ).toBe('Day Drinker can be taken only once.');
  });

  it('pairs the book rules out (core p. 183)', () => {
    const tb = { clan: 'Thin-blood', thinBloodMerits: [{ name: 'Lifelike' }], thinBloodFlaws: [{ name: 'Dead Flesh' }] };
    expect(validateThinBloodMeritsFlaws(tb)).toBe("Lifelike and Dead Flesh can't be taken together.");
    expect(validateThinBloodMeritsFlaws({ ...tb, thinBloodMerits: [{ name: 'Day Drinker' }] })).toBeNull();
  });
});

describe('messages in Greek', () => {
  afterEach(async () => {
    await act(() => setLanguage('en', { remember: false, save: false }));
  });

  it('every new message shape is translated', async () => {
    await act(() => setLanguage('el', { remember: false, save: false }));
    [
      "Ventrue can't take Iron Gullet at creation.",
      'Mask takes 1 or 2 dots (you have 3).',
      'Beautiful can be taken only once.',
      'City Secrets can be taken at most 3 times.',
      'Laboratory needs Haven at 2 dots or more.',
      'Pick at least one level of The Bahari.',
      "Lifelike and Dead Flesh can't be taken together.",
      'Archaic is only for ancillae or older.',
      'Osiris: choose which Mythic Flaw.',
    ].forEach((msg) => {
      const el = translateSheetError(msg);
      expect(el).not.toBe(msg);
      expect(el).toMatch(/[α-ω]/);
    });
    expect(translateSheetError('Mask takes 1 or 2 dots (you have 3).')).toBe('Το Mask είναι 1 ή 2 τελείες (έχεις 3).');
  });
});
