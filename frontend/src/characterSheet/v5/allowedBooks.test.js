/**
 * A chronicle's allowed books (creation_settings.allowed_books, Forge v2): the forge offers only
 * catalog entries printed in an allowed book (their own or one of also_in), keeps a chosen one
 * with an error, and agrees with the server (backend/services/creation_settings.py book_allowed,
 * v5_chargen.py book_not_allowed). Uses the shared vectors' catalog snapshot (real books and
 * also_in) with the books list of books.json.
 */
import fixture from './__fixtures__/creation-cases.json';
import { CASE_DEFS } from './__fixtures__/creationCaseDefs';
import { V5_SECTION_IDS as S } from './constants';
import { bookAllowed, entryBooks, normalizeCreationSettings } from './creationSettings';
import { eligibleClans, predatorFits } from './guided';
import { applyV5Catalog, bookEntries, bookTitle, getV5Rules, powersOf, ritualsOf } from './rulesData';
import { spendProblemText, validateSpend } from './savedPoints';
import {
  advantageOptions,
  bookErrors,
  clanInBooks,
  inBooks,
  loresheetOptions,
  predatorInBooks,
  settingsErrors,
  thinBloodOptions,
} from './validation';
import { problemSection, serverProblemErrors, translateProblem, translateSheetError } from '../i18nErrors';

// Out of order on purpose: the list sorts core books (tier 1) first, then by precedence.
const BOOKS = [
  { book_id: 'v5-cults-of-the-blood-gods', title: 'Cults of the Blood Gods', precedence: 40, tier: 2 },
  { book_id: 'v5-companion', title: 'Vampire: The Masquerade Companion', precedence: 30, tier: 1 },
  { book_id: 'v5-corebook', title: 'Vampire: The Masquerade Corebook (2019)', precedence: 10, tier: 1 },
  { book_id: 'v5-players-guide', title: 'Players Guide (v2)', precedence: 20, tier: 1 },
];
const books = (...ids) => normalizeCreationSettings({ allowed_books: ids });
const COREBOOK = books('v5-corebook');
const sheetOf = (name) => CASE_DEFS.find((d) => d.name === name).sheet();
const names = (list) => list.map((e) => e.name);
const PG = 'Players Guide (v2)';

beforeAll(() => applyV5Catalog({ ...fixture.catalog, books: BOOKS }));
afterAll(() => applyV5Catalog(null));

describe('the books of an entry', () => {
  test('its own book first, then the ones it is also printed in', () => {
    expect(entryBooks({ book: 'a', also_in: [{ book: 'b', page: 3 }, 'c', { page: 1 }, null, 'b'] })).toEqual(['a', 'b', 'c']);
    [null, 'x', {}, { book: 3, also_in: 'b' }, { book: ' ' }].forEach((bad) => expect(entryBooks(bad)).toEqual([]));
    expect(getV5Rules().clans.find((c) => c.name === 'Tzimisce').also_in).toEqual(['v5-companion']);
  });

  test('allowed through its own book or one it is also printed in; null allows every book', () => {
    const tzimisce = getV5Rules().clans.find((c) => c.name === 'Tzimisce');
    expect(bookAllowed(null, tzimisce)).toBe(true);
    expect(bookAllowed(normalizeCreationSettings({}), tzimisce)).toBe(true);
    expect(bookAllowed(COREBOOK, tzimisce)).toBe(false);
    expect(bookAllowed(books('v5-corebook', 'v5-companion'), tzimisce)).toBe(true);
    expect(bookAllowed(books('v5-players-guide'), tzimisce)).toBe(true);
    // no book (the v5.json fallback) or no entry: nothing to check
    expect(bookAllowed(COREBOOK, { name: 'Brujah' })).toBe(true);
    expect(bookAllowed(COREBOOK, null)).toBe(true);
  });

  test('the books list: core books first, then by precedence; titles by id', () => {
    expect(bookEntries().map((b) => b.book_id)).toEqual(['v5-corebook', 'v5-players-guide', 'v5-companion', 'v5-cults-of-the-blood-gods']);
    expect(bookTitle('v5-players-guide')).toBe(PG);
    expect(bookTitle('a-book-not-installed')).toBe('a-book-not-installed');
  });
});

describe("the forge offers the chronicle's books", () => {
  test('clans and predator types, the guide too', () => {
    expect(clanInBooks(COREBOOK, 'Brujah')).toBe(true);
    expect(clanInBooks(COREBOOK, 'Hecata')).toBe(false);
    expect(clanInBooks(books('v5-corebook', 'v5-companion'), 'Ravnos')).toBe(true); // also in the Companion
    expect(predatorInBooks(COREBOOK, 'Grim Reaper')).toBe(false);
    expect(predatorInBooks(books('v5-cults-of-the-blood-gods'), 'Graverobber')).toBe(true); // also in Cults
    expect(eligibleClans(COREBOOK)).toContain('Brujah');
    expect(eligibleClans(COREBOOK)).not.toContain('Hecata');
    const reaper = getV5Rules().predators.find((p) => p.name === 'Grim Reaper');
    expect(predatorFits(COREBOOK, 'Brujah', reaper)).toBe(false);
    expect(predatorFits(normalizeCreationSettings({}), 'Brujah', reaper)).toBe(true);
  });

  test('powers and rituals', () => {
    const fits = inBooks(COREBOOK);
    expect(names(powersOf('Potence').filter(fits))).not.toContain('Relentless Grasp');
    expect(names(powersOf('Potence').filter(inBooks(null)))).toContain('Relentless Grasp');
    expect(names(ritualsOf('ritual', 1).filter(fits))).not.toContain('Douse the Fear');
    expect(names(ritualsOf('ceremony', 1).filter(fits))).toEqual([]);
  });

  test('Advantages, loresheets and thin-blood Merits', () => {
    expect(names(advantageOptions('Brujah', 'merit'))).toContain('Check the Trunk');
    expect(names(advantageOptions('Brujah', 'merit', COREBOOK))).not.toContain('Check the Trunk');
    expect(names(advantageOptions('Brujah', 'flaw', COREBOOK))).not.toContain('Risk-Taker');
    expect(names(advantageOptions('Brujah', 'flaw', books('v5-corebook', 'v5-companion')))).toContain('Risk-Taker');
    expect(names(thinBloodOptions('merit'))).toContain('Low Appetite');
    expect(names(thinBloodOptions('merit', COREBOOK))).not.toContain('Low Appetite');
    expect(names(loresheetOptions({ clan: 'Hecata' }))).toContain('Bankers of Dunsirn');
    expect(names(loresheetOptions({ clan: 'Hecata' }, COREBOOK))).not.toContain('Bankers of Dunsirn');
  });
});

describe('a chosen entry outside the books is an error', () => {
  const hecata = () => sheetOf('valid: Hecata Grim Reaper with Allies and the Summon Spirit ceremony');

  test('first per section, with the book title', () => {
    const err = settingsErrors(hecata(), COREBOOK);
    expect(err[S.clan]).toBe(`Hecata comes from a book this chronicle doesn't use (${PG}).`);
    expect(err[S.predator]).toBe(`Grim Reaper comes from a book this chronicle doesn't use (${PG}).`);
    expect(err[S.disciplines]).toBe(`The Binding Fetter comes from a book this chronicle doesn't use (${PG}).`);
    // Haven, Resources and Herd are corebook ones; Allies and Prey Exclusion come with Grim Reaper
    expect(err[S.advantages]).toBeUndefined();
    // nothing to say with every book, or without settings
    expect(settingsErrors(hecata(), normalizeCreationSettings({}))).toEqual({});
    expect(bookErrors(hecata(), null)).toEqual({});
  });

  test('the allowed-clans message comes first in its section', () => {
    const err = settingsErrors(hecata(), normalizeCreationSettings({ allowed_books: ['v5-corebook'], allowed_clans: ['Tremere'] }));
    expect(err[S.clan]).toBe("The Storyteller doesn't allow Hecata in this chronicle.");
  });

  test('XP rituals in the experience section, the starting ritual with the Disciplines', () => {
    const tremere = sheetOf('books: a Players Guide ritual bought with XP with only the corebook');
    expect(bookErrors(tremere, COREBOOK)).toEqual({
      [S.experience]: `Calix Secretus comes from a book this chronicle doesn't use (${PG}).`,
    });
    expect(bookErrors({ ...tremere, xpPurchases: [], startingRitual: 'Douse the Fear' }, COREBOOK)).toEqual({
      [S.disciplines]: `Douse the Fear comes from a book this chronicle doesn't use (${PG}).`,
    });
  });

  test("own rows and thin-blood Merits are checked; the clan's own Flaws come with it", () => {
    const tz = sheetOf('valid: allowed books: a Players Guide clan and Flaw the Companion reprints (also_in)');
    expect(bookErrors(tz, books('v5-corebook', 'v5-companion'))).toEqual({});
    expect(bookErrors(tz, COREBOOK)[S.advantages]).toBe(`Risk-Taker comes from a book this chronicle doesn't use (${PG}).`);
    const thin = sheetOf('books: a Players Guide thin-blood Merit with only the corebook');
    expect(bookErrors(thin, COREBOOK)[S.advantages]).toMatch(/^Low Appetite comes from a book/);
    // Caitiff start with Suspect (core): in a Players Guide-only chronicle it still comes with the clan
    const caitiff = sheetOf('valid: Caitiff Osiris, Performance 0 becomes 1, split grants, Caitiff XP');
    const pgOnly = books('v5-players-guide');
    expect(bookErrors({ ...caitiff, flaws: [] }, pgOnly)[S.advantages]).toBeUndefined();
    expect(bookErrors({ ...caitiff, flaws: [{ name: 'Addiction', dots: 1 }] }, pgOnly)[S.advantages]).toMatch(/^Addiction comes/);
  });
});

describe('messages', () => {
  test("the server's problem in words, with the book title, in its entry's section", () => {
    const p = { code: 'book_not_allowed', params: { name: 'Hecata', book: 'v5-players-guide', kind: 'clan' } };
    const text = `Hecata comes from a book this chronicle doesn't use (${PG}).`;
    expect(translateProblem(p)).toBe(text);
    expect(serverProblemErrors([p]).bySection).toEqual({ [S.clan]: text });
    expect(problemSection('book_not_allowed', { kind: 'power' })).toBe(S.disciplines);
    expect(problemSection('book_not_allowed', { kind: 'ceremony' })).toBe(S.disciplines);
    expect(problemSection('book_not_allowed', { kind: 'thin_blood' })).toBe(S.advantages);
    expect(problemSection('book_not_allowed', { kind: 'loresheet' })).toBe(S.advantages);
    expect(problemSection('book_not_allowed', {})).toBe(S.identity);
  });

  test("the forge's message is recognised", () => {
    const msg = `Players Guide Thing comes from a book this chronicle doesn't use (${PG}).`;
    expect(translateSheetError(msg)).toBe(msg);
  });

  test('the spend preview checks the books too, through also_in', () => {
    const meta = { clan: 'Brujah', saved: { advantage_dots: 3 }, advantages: [] };
    const spend = (name, kind = 'merit') => ({ kind: 'saved_advantage', items: [{ name, kind, dots: 1 }] });
    const out = validateSpend(meta, spend('Check the Trunk'), { allowed_books: ['v5-corebook'] });
    expect(out.problems).toEqual([
      { code: 'book_not_allowed', params: { name: 'Check the Trunk', book: 'v5-players-guide', kind: 'advantage' } },
    ]);
    expect(spendProblemText(out.problems[0])).toBe(`Check the Trunk comes from a book this chronicle doesn't use (${PG}).`);
    // Allies is a corebook Background the Players Guide reprints
    expect(validateSpend(meta, spend('Allies', 'background'), { allowed_books: ['v5-players-guide'] }).ok).toBe(true);
    expect(validateSpend(meta, spend('Allies', 'background'), { allowed_books: ['v5-companion'] }).problems.map((p) => p.code)).toEqual([
      'book_not_allowed',
    ]);
    expect(validateSpend(meta, spend('Check the Trunk'), null).ok).toBe(true);
  });
});
