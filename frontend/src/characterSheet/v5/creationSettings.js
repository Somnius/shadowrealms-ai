/**
 * Per-chronicle creation settings (campaigns.creation_settings, set by the Storyteller in the
 * chronicle settings). Same shape and defaults as backend/services/creation_settings.py; the
 * server normalises before sending, this only guards against a missing or old payload.
 */
export const CREATION_AGES = ['childer', 'neonate', 'ancilla'];
/** The corebook is always allowed (CORE_BOOK in creation_settings.py): the core rules every chronicle plays by. */
export const CORE_BOOK = 'v5-corebook';

export const DEFAULT_CREATION_SETTINGS = {
  v: 1,
  allowed_books: null,
  allowed_clans: null,
  allowed_predators: null,
  allowed_ages: null,
  flaws_max_dots: null,
  fledgling_humanity_8: true,
  saved_points: { advantage_dots_cap: 7, allow_specialty: true },
  st_mode: 'human',
  house_rules: '',
};

const list = (v) => (Array.isArray(v) && v.length ? v.filter((x) => typeof x === 'string' && x.trim()) : null);
/** allowed_books with the corebook in it (an old row, or one stored through the API without it). */
const withCore = (books) => (books && !books.includes(CORE_BOOK) ? [CORE_BOOK, ...books] : books);

export function normalizeCreationSettings(value) {
  const v = value && typeof value === 'object' ? value : {};
  return {
    ...DEFAULT_CREATION_SETTINGS,
    allowed_books: withCore(list(v.allowed_books)),
    allowed_clans: list(v.allowed_clans),
    allowed_predators: list(v.allowed_predators),
    allowed_ages: list(v.allowed_ages),
    flaws_max_dots: Number.isInteger(v.flaws_max_dots) ? v.flaws_max_dots : null,
    fledgling_humanity_8: v.fledgling_humanity_8 !== false,
    saved_points: { ...DEFAULT_CREATION_SETTINGS.saved_points, ...(v.saved_points || {}) },
    st_mode: v.st_mode === 'ai' ? 'ai' : 'human',
    house_rules: typeof v.house_rules === 'string' ? v.house_rules : '',
  };
}

/**
 * The books a catalog entry is printed in: its own `book` first, then `also_in` ([{book, page}] or
 * book ids). Empty for an entry without a book (the v5.json fallback). Same as entry_books in
 * backend/services/creation_settings.py.
 */
export function entryBooks(entry) {
  if (!entry || typeof entry !== 'object') return [];
  const refs = [entry.book, ...(Array.isArray(entry.also_in) ? entry.also_in : [])];
  const out = [];
  refs.forEach((ref) => {
    const b = ref && typeof ref === 'object' ? ref.book : ref;
    if (typeof b === 'string' && b.trim() && !out.includes(b.trim())) out.push(b.trim());
  });
  return out;
}

/**
 * May the chronicle use this catalog entry (clan, power, ritual, ceremony, predator type, Merit,
 * Background, Flaw, loresheet)? Yes when allowed_books is null (every book, also ones the catalog
 * adds later), when the entry names no book (or there is no entry), or when its own book or one it
 * is also printed in is allowed; the corebook always is. Same as book_allowed in
 * backend/services/creation_settings.py.
 */
export function bookAllowed(settings, entry) {
  const allowed = settings?.allowed_books;
  if (!Array.isArray(allowed) || !allowed.length) return true;
  const books = entryBooks(entry);
  return !books.length || books.some((b) => b === CORE_BOOK || allowed.includes(b));
}

/** The settings of the chronicle with this id in a campaigns list (defaults when absent). */
export function settingsForCampaign(campaigns, campaignId) {
  const c = (campaigns || []).find((x) => String(x.id) === String(campaignId));
  return normalizeCreationSettings(c?.creation_settings);
}
