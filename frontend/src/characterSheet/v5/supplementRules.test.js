/**
 * Forge v2 part F: rules the supplement entries bring (fixture: the jest catalog plus a few entries
 * shaped like the real ones, with invented descriptions).
 */
import fixture from '../../rules/__fixtures__/v5-catalog.json';
import {
  applyV5Catalog,
  findAdvantage,
  findLoresheet,
  formulaEntries,
  levelName,
  loresheetEntries,
  optionName,
  powersOf,
  ritualsOf,
  sharedNames,
} from './rulesData';
import {
  advantageDotChoices,
  advantageUnrated,
  disciplineAccess,
  dotRequirement,
  loresheetAllowed,
  loresheetLevelAllowed,
  loresheetOptions,
  powerAllowed,
  ritualPrereqMissing,
  validateV5AdvantageRows,
  validateV5Powers,
  validateV5Rituals,
  xpLedger,
} from './validation';

const desc = (what) => ({ en: `Test ${what}.`, el: `Δοκιμή ${what}.` });
const levels = (names, extra = {}) => names.map((name, i) => ({ dots: i + 1, name, desc: name ? desc(name) : undefined, ...(extra[i + 1] || {}) }));

const CATALOG = {
  ...fixture,
  books: [
    ...fixture.books,
    { book_id: 'v5-blood-sigils', title: 'Blood Sigils', precedence: 40, tier: 2 },
    { book_id: 'v5-la-by-night-loresheets', title: 'L.A. by Night Loresheets', precedence: 50, tier: 2 },
  ],
  clans: [
    ...fixture.clans,
    { id: 'clan:tzimisce', name: 'Tzimisce', book: 'v5-players-guide', page: 52, disciplines: ['discipline:dominate', 'discipline:auspex', 'discipline:fortitude'] },
  ],
  disciplines: [
    ...fixture.disciplines,
    {
      id: 'discipline:blood-sorcery',
      name: 'Blood Sorcery',
      book: 'v5-corebook',
      page: 271,
      powers: [
        { id: 'power:blood-sorcery:a-taste-for-blood', name: 'A Taste for Blood', level: 1, book: 'v5-corebook', page: 272 },
        {
          id: 'power:blood-sorcery:koldunic-sorcery',
          name: 'Koldunic Sorcery',
          level: 1,
          book: 'v5-blood-sigils',
          page: 61,
          clans_only: ['clan:tzimisce'],
          repeatable: true,
          at_first_dot: true,
        },
      ],
    },
  ],
  rituals: [
    ...fixture.rituals,
    {
      id: 'ritual:elemental-grasp',
      name: 'Elemental Grasp',
      level: 2,
      discipline: 'discipline:blood-sorcery',
      book: 'v5-blood-sigils',
      page: 62,
      koldunic: true,
      prerequisite: { power_id: 'power:blood-sorcery:koldunic-sorcery' },
    },
  ],
  formulae: [
    { id: 'formula:concoct-ashe', name: 'Concoct Ashe', level: 3, book: 'v5-cults-of-the-blood-gods', page: 45 },
    {
      id: 'formula:chemically-induced-flashback',
      name: 'Chemically-Induced Flashback',
      level: 3,
      book: 'v5-cults-of-the-blood-gods',
      page: 45,
      prerequisite: { formula_id: 'formula:concoct-ashe' },
    },
  ],
  advantages: [
    ...fixture.advantages,
    { id: 'background:fame', name: 'Fame', kind: 'background', group: 'Fame', dots: { min: 1, max: 5 }, book: 'v5-corebook', page: 186, repeatable: true },
    { id: 'merit:influencer', name: 'Influencer', kind: 'merit', group: 'Fame', dots: { min: 1, max: 1 }, book: 'v5-succubus-club', page: 25, requires: 'Fame ••+' },
    { id: 'merit:influencer-ashfinders', name: 'Influencer', kind: 'merit', group: 'Ashfinders', dots: { min: 2, max: 2 }, book: 'v5-children-of-the-blood', page: 96 },
    { id: 'merit:mobile', name: 'Mobile', kind: 'merit', group: 'Haven', dots: { allowed: [1, 2] }, book: 'v5-succubus-club', page: 25 },
    { id: 'merit:armored', name: 'Armored', kind: 'merit', group: 'Haven', dots: { min: 1, max: 1 }, book: 'v5-succubus-club', page: 25, requires: 'Mobile' },
    {
      id: 'flaw:ingrained-blunt',
      name: 'Blunt',
      kind: 'flaw',
      group: 'Discipline',
      dots: null,
      book: 'v5-tattered-facade',
      page: 109,
      requires: "Dominate •••+, Storyteller's consent",
    },
    { id: 'merit:moral-dissident', name: 'Moral Dissident', kind: 'merit', group: 'Autarkis', dots: { min: 2, max: 2 }, book: 'v5-courts-of-the-damned', page: 144, requires: 'Autark only' },
  ],
  loresheets: [
    ...fixture.loresheets,
    {
      id: 'loresheet:child-of-the-angel-michael',
      name: 'Child of the Angel Michael',
      book: 'v5-cults-of-the-blood-gods',
      page: 229,
      restriction: 'Unavailable to Nosferatu characters',
      clans_only: null,
      clans_excluded: ['clan:ventrue'], // the fixture has no Nosferatu: the same rule on Ventrue
      levels: levels(['A', 'B', 'C', 'D', 'E']),
    },
    {
      id: 'loresheet:tegyrius-the-vizier',
      name: 'Tegyrius the Vizier',
      book: 'v5-gehenna-war',
      page: 159,
      clans_only: null,
      levels: levels(['One', 'Two', 'Three', 'Perception is Power', 'Five'], { 4: { restriction: 'Hecata characters only', clans_only: ['clan:hecata'] } }),
    },
    {
      id: 'loresheet:salvador-garcia',
      name: 'Salvador Garcia',
      book: 'v5-anarch',
      page: 190,
      source: 'online',
      clans_only: null,
      levels: levels([null, null, null, null, null]),
    },
    {
      id: 'loresheet:student-of-kirin-taunk',
      name: 'Student of Kirin Taunk',
      book: 'v5-blood-sigils',
      page: 178,
      restriction: 'Thin-Blood Alchemists only',
      disciplines_only: ['discipline:thin-blood-alchemy'],
      thin_blood_only: true,
      levels: levels(['1', '2', '3', '4', '5']),
    },
    { id: 'loresheet:annabelle', name: 'Annabelle', book: 'v5-chicago-by-night', page: 262, levels: levels(['1', '2', '3', '4', '5']) },
    { id: 'loresheet:annabelle-la-by-night', name: 'Annabelle', book: 'v5-la-by-night-loresheets', page: 4, levels: levels(['1', '2', '3', '4', '5']) },
  ],
};

beforeAll(() => applyV5Catalog(CATALOG));
afterAll(() => applyV5Catalog(null));

const lore = (id, lv) => ({ id, name: findLoresheet({ id }).name, dots: lv.reduce((s, n) => s + n, 0), kind: 'loresheet', levels: lv });

describe('the registry reads the supplement facts', () => {
  it('power restrictions, Koldunic rituals and formula prerequisites', () => {
    const kold = powersOf('Blood Sorcery').find((p) => p.name === 'Koldunic Sorcery');
    expect(kold).toMatchObject({ clans_only: ['Tzimisce'], repeatable: true, at_first_dot: true });
    expect(ritualsOf('ritual').find((r) => r.name === 'Elemental Grasp')).toMatchObject({ koldunic: true, prerequisite: [['Koldunic Sorcery']] });
    expect(formulaEntries().find((f) => f.name === 'Chemically-Induced Flashback').prerequisite).toEqual([['Concoct Ashe']]);
  });

  it('a loresheet: the clans it excludes, a level of its own restriction, unnamed levels', () => {
    expect(findLoresheet({ id: 'loresheet:child-of-the-angel-michael' }).clans_excluded).toEqual(['Ventrue']);
    expect(findLoresheet({ id: 'loresheet:tegyrius-the-vizier' }).levels[3]).toMatchObject({
      name: 'Perception is Power',
      restriction: 'Hecata characters only',
      clans_only: ['Hecata'],
    });
    const salvador = findLoresheet({ id: 'loresheet:salvador-garcia' });
    expect(salvador.levels.map((l) => l.name)).toEqual([null, null, null, null, null]);
    expect(salvador.levels.map(levelName)).toEqual(['Level 1', 'Level 2', 'Level 3', 'Level 4', 'Level 5']);
  });

  it('two entries of one name: found by id, shown with their book', () => {
    expect(findLoresheet({ id: 'loresheet:annabelle-la-by-night', name: 'Annabelle' }).book).toBe('v5-la-by-night-loresheets');
    expect(findAdvantage({ id: 'merit:influencer-ashfinders', name: 'Influencer' }, 'merit').group).toBe('Ashfinders');
    const shared = sharedNames(loresheetEntries());
    expect(optionName(findLoresheet({ id: 'loresheet:annabelle-la-by-night' }), shared)).toBe('Annabelle · L.A. by Night Loresheets');
    expect(optionName(findLoresheet({ id: 'loresheet:the-bahari' }), shared)).toBe('The Bahari');
  });
});

describe('loresheet restrictions', () => {
  it('a sheet a clan is excluded from is not offered to it', () => {
    const angel = findLoresheet({ id: 'loresheet:child-of-the-angel-michael' });
    expect(loresheetAllowed(angel, { clan: 'Ventrue' })).toBe(false);
    expect(loresheetAllowed(angel, { clan: 'Hecata' })).toBe(true);
    expect(loresheetOptions({ clan: 'Ventrue' }).map((l) => l.id)).not.toContain(angel.id);
    const sheet = { clan: 'Ventrue', advantages: [lore('loresheet:child-of-the-angel-michael', [1])] };
    expect(validateV5AdvantageRows(sheet)).toBe("Ventrue can't take Child of the Angel Michael at creation.");
  });

  it('Student of Kirin Taunk asks for Thin-Blood Alchemy, which the Thin-Blood Alchemist Merit brings', () => {
    const kirin = findLoresheet({ id: 'loresheet:student-of-kirin-taunk' });
    expect(kirin.disciplines_only).toEqual(['Thin-Blood Alchemy']);
    const tb = { clan: 'Thin-blood', thinBloodMerits: [{ name: 'Day Drinker' }, { name: 'Lifelike' }] };
    expect(disciplineAccess(tb)).toEqual([]);
    expect(loresheetAllowed(kirin, tb)).toBe(false);
    const alchemist = { ...tb, thinBloodMerits: [{ name: 'Day Drinker' }, { name: 'Thin-Blood Alchemist' }] };
    expect(disciplineAccess(alchemist)).toEqual(['Thin-Blood Alchemy']);
    expect(loresheetAllowed(kirin, alchemist)).toBe(true);
    expect(loresheetOptions(alchemist).map((l) => l.id)).toContain(kirin.id);
    expect(validateV5AdvantageRows({ ...alchemist, advantages: [lore('loresheet:student-of-kirin-taunk', [1])] })).toBeNull();
    expect(validateV5AdvantageRows({ ...tb, advantages: [lore('loresheet:student-of-kirin-taunk', [1])] })).toBe(
      "Thin-blood can't take Student of Kirin Taunk at creation."
    );
  });

  it('a level with its own restriction: refused for others, the rest of the sheet is fine', () => {
    const teg = findLoresheet({ id: 'loresheet:tegyrius-the-vizier' });
    expect(loresheetLevelAllowed(teg.levels[3], { clan: 'Ventrue' })).toBe(false);
    expect(loresheetLevelAllowed(teg.levels[3], { clan: 'Hecata' })).toBe(true);
    expect(loresheetLevelAllowed(teg.levels[0], { clan: 'Ventrue' })).toBe(true);
    expect(validateV5AdvantageRows({ clan: 'Ventrue', advantages: [lore('loresheet:tegyrius-the-vizier', [1, 3])] })).toBeNull();
    expect(validateV5AdvantageRows({ clan: 'Ventrue', advantages: [lore('loresheet:tegyrius-the-vizier', [4])] })).toBe(
      "Ventrue can't take Tegyrius the Vizier level 4 at creation."
    );
    expect(validateV5AdvantageRows({ clan: 'Hecata', advantages: [lore('loresheet:tegyrius-the-vizier', [4])] })).toBeNull();
  });

  it('a sheet whose level names our sources lack: the levels are still taken', () => {
    expect(validateV5AdvantageRows({ clan: 'Ventrue', advantages: [lore('loresheet:salvador-garcia', [2])] })).toBeNull();
  });
});

describe('Koldunic Sorcery (Blood Sigils p. 61)', () => {
  const sheet = (clan, powers, extra = {}) => ({ clan, disciplines: [{ name: 'Blood Sorcery', level: 2, powers }], ...extra });

  it('Tzimisce only', () => {
    expect(powerAllowed(powersOf('Blood Sorcery')[1], 'Ventrue')).toBe(false);
    expect(validateV5Powers(sheet('Ventrue', ['Koldunic Sorcery']))).toBe('Koldunic Sorcery is only for Tzimisce.');
    expect(validateV5Powers(sheet('Tzimisce', ['Koldunic Sorcery']))).toBeNull();
  });

  it('any creation slot (creation dots come all at once), and again for another element', () => {
    expect(validateV5Powers(sheet('Tzimisce', ['A Taste for Blood', 'Koldunic Sorcery']))).toBeNull();
    expect(validateV5Powers(sheet('Ventrue', ['A Taste for Blood', 'Koldunic Sorcery']))).toBe('Koldunic Sorcery is only for Tzimisce.');
    expect(validateV5Powers(sheet('Tzimisce', ['Koldunic Sorcery', 'Koldunic Sorcery']))).toBeNull();
    expect(validateV5Powers(sheet('Tzimisce', ['A Taste for Blood', 'A Taste for Blood']))).toBe('Blood Sorcery: A Taste for Blood is taken twice.');
  });

  it('a Koldunic ritual needs the power, at creation and with XP', () => {
    const grasp = ritualsOf('ritual').find((r) => r.name === 'Elemental Grasp');
    expect(ritualPrereqMissing(sheet('Tzimisce', ['A Taste for Blood']), grasp)).toEqual(['Koldunic Sorcery']);
    expect(ritualPrereqMissing(sheet('Tzimisce', ['Koldunic Sorcery']), grasp)).toBeNull();
    // a starting ritual names it (the forge doesn't offer it, an old sheet may have it)
    expect(validateV5Rituals(sheet('Tzimisce', ['A Taste for Blood'], { startingRitual: 'Elemental Grasp' }))).toBe(
      'The Elemental Grasp ritual needs the Koldunic Sorcery power.'
    );
    const xp = sheet('Tzimisce', ['A Taste for Blood', 'A Taste for Blood'], {
      age: 'neonate',
      xpPurchases: [{ kind: 'ritual', trait: 'Elemental Grasp', level: 2 }],
    });
    expect(xpLedger(xp).errors).toContain('The Elemental Grasp ritual needs the Koldunic Sorcery power.');
  });
});

describe('ratings the book does not print, and prerequisites', () => {
  it('an unrated Flaw takes 1–5; thin-blood ones stay without dots', () => {
    const blunt = findAdvantage({ id: 'flaw:ingrained-blunt' }, 'flaw');
    expect(advantageUnrated(blunt)).toBe(true);
    expect(advantageDotChoices(blunt)).toEqual([1, 2, 3, 4, 5]);
    const day = findAdvantage({ id: 'merit:thin-blood-day-drinker' }, 'merit');
    expect(advantageUnrated(day)).toBe(false);
    expect(advantageDotChoices(day)).toEqual([]);
  });

  it('reads Background, Merit and Discipline requirements; the rest stay hints', () => {
    expect(dotRequirement({ requires: 'Mawla 1+' })).toEqual({ name: 'Mawla', dots: 1, onlyAbove1: false, kind: 'advantage' });
    expect(dotRequirement({ requires: 'Mobile' })).toEqual({ name: 'Mobile', dots: 1, onlyAbove1: false, kind: 'advantage' });
    expect(dotRequirement({ requires: "Dominate •••+, Storyteller's consent" })).toEqual({
      name: 'Dominate',
      dots: 3,
      onlyAbove1: false,
      kind: 'discipline',
    });
    expect(dotRequirement({ requires: 'Autark only' })).toBeNull();
    expect(dotRequirement({ requires: 'Gangrel, Ministry, or Tzimisce' })).toBeNull();
  });

  it('enforces them on the sheet', () => {
    const inf = { id: 'merit:influencer', name: 'Influencer', dots: 1, kind: 'merit' };
    expect(validateV5AdvantageRows({ clan: 'Ventrue', advantages: [inf] })).toBe('Influencer needs Fame at 2 dots or more.');
    expect(validateV5AdvantageRows({ clan: 'Ventrue', advantages: [inf, { id: 'background:fame', name: 'Fame', dots: 2, kind: 'background' }] })).toBeNull();
    // the Ashfinders' Influencer is another Merit: no Fame needed
    expect(validateV5AdvantageRows({ clan: 'Ventrue', advantages: [{ id: 'merit:influencer-ashfinders', name: 'Influencer', dots: 2, kind: 'merit' }] })).toBeNull();
    const armored = { id: 'merit:armored', name: 'Armored', dots: 1, kind: 'merit' };
    expect(validateV5AdvantageRows({ clan: 'Ventrue', advantages: [armored] })).toBe('Armored needs Mobile on the sheet.');
    expect(validateV5AdvantageRows({ clan: 'Ventrue', advantages: [armored, { id: 'merit:mobile', name: 'Mobile', dots: 1, kind: 'merit' }] })).toBeNull();
    const blunt = { id: 'flaw:ingrained-blunt', name: 'Blunt', dots: 2 };
    const ventrue = (level) => ({ clan: 'Ventrue', disciplines: [{ name: 'Dominate', level, powers: [] }], flaws: [blunt] });
    expect(validateV5AdvantageRows(ventrue(2))).toBe('Blunt needs Dominate at 3 dots or more.');
    expect(validateV5AdvantageRows(ventrue(3))).toBeNull();
    // a hint only: nothing to check
    expect(validateV5AdvantageRows({ clan: 'Ventrue', advantages: [{ id: 'merit:moral-dissident', name: 'Moral Dissident', dots: 2, kind: 'merit' }] })).toBeNull();
  });
});
