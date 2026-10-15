/**
 * The V5 creation rules the forge reads: clans, Disciplines (with their powers), predator types,
 * rituals and ceremonies, by English name. It starts from src/rules/v5.json and is replaced by the
 * served catalog (GET /api/rules/v5/catalog, docs/rules/v5/catalog) once that has loaded, so the
 * forge works without it and gets dropdowns, descriptions and the Player's Guide clans with it.
 *
 * Shapes (names are the English names stored on sheets):
 *   clan      { id, name, disciplines: [name], bane, bane_desc, compulsion, compulsion_desc, desc, book, page }
 *   predator  { id, name, pool, specialties: [{ skill: key, name }], disciplines: [{ name, clans: [name] | null }],
 *               advantages: [grant], flaws: [grant], humanity, blood_potency, max_blood_potency,
 *               forbidden_clans: [name], ancilla_only, desc, book, page }
 *   grant     { pick: 'all' | 'one_of' | 'split', options: [{ id, name, dots: n | null, note, kind, group }], dots_total }
 *             (group: an option that stands for any entry of that group, e.g. "any Mythic Flaw")
 *   power     { id, name, level, amalgam: { discipline, level } | null,
 *               prerequisite: [[name]] | null (every group needed, any name of a group will do),
 *               clans_only: [name] | null, repeatable, at_first_dot (Koldunic Sorcery: Tzimisce only,
 *               taken with the first Blood Sorcery dot, again per element), dice_pool, rouse_cost, desc, book, page }
 *   ritual    { id, name, level, kind: 'ritual' | 'ceremony', prerequisite: [[name]] | null, koldunic, desc, book, page }
 *   formula   { id, name, level, prerequisite: [[name]] | null (a power or another formula), desc, book, page }
 *             (data only: the forge offers no formulae at creation or for XP)
 *   advantage { id, name, kind: 'background' | 'merit' | 'flaw', group, dots: { min, max } | { allowed } | null,
 *               levels: [{ dots, name }], thin_blood, caitiff, ghoul_only, coterie, clans_only: [name] | null,
 *               cannot_buy_for: [name], repeatable, max_instances, requires, excludes: [id], aliases, desc, book, page }
 *   loresheet { id, name, restriction, clans_only: [name] | null, clans_excluded: [name] | null,
 *               disciplines_only: [name] | null, thin_blood_only,
 *               levels: [{ dots, name (null: not in our sources, the Anarch sheets), restriction,
 *                          clans_only: [name] | null, desc }], source, aliases, desc, book, page }
 * Clans also carry caitiff / thin_blood and `creation` ({ flaws: [{ id, name, dots }],
 * no_positive_status }, the Caitiff rules); without the catalog advantages and loresheets are empty
 * and the forge falls back to free text. Every catalog entry also carries `also_in`: [book_id], the
 * other books it is printed in (a chronicle's allowed books: creationSettings.bookAllowed).
 * books     { book_id, title, tier, precedence } (books.json; empty without the catalog)
 */
import V5_RULES from '../../rules/v5.json';

const toKey = (label) => String(label).trim().toLowerCase().replace(/[^a-z0-9]+/g, '_');

const titleOf = (slug) =>
  String(slug || '')
    .split('-')
    .map((w) => (w ? w[0].toUpperCase() + w.slice(1) : w))
    .join(' ');

/** "background:iron-gullet" → "Iron Gullet"; the kind before the colon. */
function nameFromId(id) {
  const parts = String(id || '').split(':');
  return { kind: parts[0] || 'merit', name: titleOf(parts[parts.length - 1]) };
}

// ---------- from src/rules/v5.json (the fallback) ----------

/** "Blood Sorcery (Tremere only)" → { name, clans: ['Tremere'] } */
function parseDiscipline(text) {
  const m = String(text).match(/^(.*?)\s*\((\w[\w-]*) only\)\s*$/);
  return m ? { name: m[1].trim(), clans: [m[2]] } : { name: String(text).trim(), clans: null };
}

/** "Intimidation (Stickups)" → { skill: 'intimidation', name: 'Stickups' } */
function parseSpecialty(text) {
  const m = String(text).match(/^(.*?)\s*\((.*)\)\s*$/);
  return m ? { skill: toKey(m[1]), name: m[2].trim() } : { skill: toKey(text), name: '' };
}

const fixedGrant = (rows, kind) =>
  (rows || []).map((r) => ({ pick: 'all', options: [{ name: r.name, dots: r.dots, note: '', kind }], dots_total: null }));

function fromRulesJson() {
  return {
    source: 'rules',
    clans: V5_RULES.clans.map((c) => ({
      id: null,
      name: c.name,
      disciplines: c.disciplines || [],
      bane: c.bane_summary || '',
      bane_desc: null,
      compulsion: c.compulsion || '',
      compulsion_desc: null,
      desc: null,
      book: null,
      page: null,
    })),
    disciplines: V5_RULES.disciplines.map((name) => ({ id: null, name, desc: null, powers: [] })),
    predators: V5_RULES.predator_types.map((p) => ({
      id: null,
      name: p.name,
      pool: p.pool,
      specialties: (p.specialty_choice || []).map(parseSpecialty),
      disciplines: (p.discipline_choice || []).map(parseDiscipline),
      advantages: fixedGrant(p.advantages, 'merit'),
      flaws: fixedGrant(p.flaws, 'flaw'),
      humanity: p.humanity || 0,
      blood_potency: p.blood_potency || 0,
      max_blood_potency: p.max_blood_potency ?? null,
      forbidden_clans: p.forbidden_clans || [],
      ancilla_only: false,
      desc: null,
      book: null,
      page: null,
    })),
    rituals: [],
    formulae: [],
    advantages: [],
    loresheets: [],
    books: [],
  };
}

// ---------- from the served catalog ----------

const pickDesc = (e) => (e && e.desc && (e.desc.en || e.desc.el) ? e.desc : null);
/** also_in ([{book, page}]) as book ids. */
const alsoIn = (e) =>
  (Array.isArray(e?.also_in) ? e.also_in : []).map((x) => (x && typeof x === 'object' ? x.book : x)).filter((b) => typeof b === 'string' && b);

function fromCatalog(cat) {
  const clanName = Object.fromEntries((cat.clans || []).map((c) => [c.id, c.name]));
  const discName = Object.fromEntries((cat.disciplines || []).map((d) => [d.id, d.name]));
  const powerName = {};
  (cat.disciplines || []).forEach((d) => (d.powers || []).forEach((p) => (powerName[p.id] = p.name)));
  const advName = Object.fromEntries((cat.advantages || []).map((a) => [a.id, a.name]));
  const clanNamesOf = (ids) => (Array.isArray(ids) && ids.length ? ids.map((c) => clanName[c] || nameFromId(c).name) : null);
  const slug = (s) => String(s || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  // "flaw:mythic" with group: true means any Flaw of the Mythic group: its group name as printed.
  const groupOf = (id) => {
    const [kind, g] = String(id || '').split(':');
    return (cat.advantages || []).find((a) => a.kind === kind && slug(a.group) === g)?.group || titleOf(g);
  };
  // Predator grants name catalog Merits, Backgrounds and Flaws by id: use their real names.
  const grant = (g, fallbackKind) => ({
    pick: g.pick || 'all',
    dots_total: g.dots_total ?? null,
    options: (g.options || []).map((o) => {
      const { kind, name } = nameFromId(o.id);
      return {
        id: o.id,
        name: advName[o.id] || name,
        dots: o.dots ?? null,
        note: o.note || '',
        kind: kind || fallbackKind,
        group: o.group ? groupOf(o.id) : null,
      };
    }),
  });
  const formulaName = Object.fromEntries((cat.formulae || []).map((x) => [x.id, x.name]));
  const pname = (x) => {
    const id = typeof x === 'string' ? x : x?.power_id;
    return powerName[id] || nameFromId(id).name;
  };
  // {power_id} | {formula_id} | {any_of: [...]} | {all_of: [{power_id} | {any_of}]} → [[name]]: all groups,
  // any name in a group. A formula may need another formula (the Ashfinders' Concoct Ashe, Cults p. 45).
  const group = (p) =>
    p.power_id
      ? [pname(p)]
      : p.formula_id
        ? [formulaName[p.formula_id] || nameFromId(p.formula_id).name]
        : Array.isArray(p.any_of)
          ? p.any_of.map(pname)
          : null;
  const prereq = (p) => {
    if (!p) return null;
    if (Array.isArray(p.all_of)) {
      const groups = p.all_of.map(group).filter(Boolean);
      return groups.length ? groups : null;
    }
    const g = group(p);
    return g ? [g] : null;
  };
  const ritualOf = (kind) => (r) => ({
    id: r.id,
    name: r.name,
    level: r.level,
    kind,
    discipline: discName[r.discipline] || null,
    prerequisite: prereq(r.prerequisite),
    koldunic: Boolean(r.koldunic),
    desc: pickDesc(r),
    book: r.book,
    also_in: alsoIn(r),
    page: r.page,
  });
  return {
    source: 'catalog',
    clans: (cat.clans || []).map((c) => ({
      id: c.id,
      name: c.name,
      disciplines: (c.disciplines || []).map((d) => discName[d] || nameFromId(d).name),
      bane: c.bane?.name || '',
      bane_desc: pickDesc(c.bane),
      compulsion: c.compulsion?.name || '',
      compulsion_desc: pickDesc(c.compulsion),
      desc: pickDesc(c),
      book: c.book,
      also_in: alsoIn(c),
      page: c.page,
      caitiff: Boolean(c.caitiff),
      thin_blood: Boolean(c.thin_blood),
      creation: c.creation
        ? {
            flaws: (c.creation.flaws || []).map((f) => ({ id: f.id, name: advName[f.id] || nameFromId(f.id).name, dots: f.dots })),
            no_positive_status: Boolean(c.creation.no_positive_status),
            book: c.creation.book || c.book,
            page: c.creation.page || null,
          }
        : null,
    })),
    disciplines: (cat.disciplines || []).map((d) => ({
      id: d.id,
      name: d.name,
      desc: pickDesc(d),
      book: d.book,
      also_in: alsoIn(d),
      powers: (d.powers || []).map((p) => ({
        id: p.id,
        name: p.name,
        level: p.level,
        amalgam: p.amalgam ? { discipline: discName[p.amalgam.discipline] || nameFromId(p.amalgam.discipline).name, level: p.amalgam.level } : null,
        prerequisite: prereq(p.prerequisite),
        clans_only: clanNamesOf(p.clans_only),
        repeatable: Boolean(p.repeatable),
        at_first_dot: Boolean(p.at_first_dot),
        dice_pool: p.dice_pool || null,
        rouse_cost: p.rouse_cost ?? null,
        desc: pickDesc(p),
        book: p.book,
        also_in: alsoIn(p),
        page: p.page,
        aliases: p.aliases || [],
      })),
    })),
    predators: (cat.predator_types || []).map((p) => ({
      id: p.id,
      name: p.name,
      pool: p.pool || '',
      specialties: (p.specialty_choice || []).map((s) => ({ skill: toKey(s.skill), name: s.name })),
      disciplines: (p.discipline_choice || []).map((d) => ({
        name: discName[d.discipline] || nameFromId(d.discipline).name,
        clans: d.clans_only ? d.clans_only.map((c) => clanName[c] || nameFromId(c).name) : null,
      })),
      advantages: (p.advantages || []).map((g) => grant(g, 'merit')),
      flaws: (p.flaws || []).map((g) => grant(g, 'flaw')),
      humanity: p.humanity || 0,
      blood_potency: p.blood_potency || 0,
      max_blood_potency: p.max_blood_potency ?? null,
      forbidden_clans: (p.forbidden_clans || []).map((c) => clanName[c] || nameFromId(c).name),
      ancilla_only: Boolean(p.ancilla_only),
      desc: pickDesc(p),
      book: p.book,
      also_in: alsoIn(p),
      page: p.page,
    })),
    rituals: [...(cat.rituals || []).map(ritualOf('ritual')), ...(cat.ceremonies || []).map(ritualOf('ceremony'))],
    formulae: (cat.formulae || []).map((x) => ({
      id: x.id,
      name: x.name,
      level: x.level,
      prerequisite: prereq(x.prerequisite),
      desc: pickDesc(x),
      book: x.book,
      also_in: alsoIn(x),
      page: x.page,
    })),
    advantages: (cat.advantages || []).map((a) => ({
      id: a.id,
      name: a.name,
      kind: a.kind,
      group: a.group || '',
      dots: a.dots || null,
      levels: (a.levels || []).map((l) => ({ dots: l.dots, name: l.name, desc: pickDesc(l) })),
      thin_blood: Boolean(a.thin_blood),
      caitiff: Boolean(a.caitiff),
      ghoul_only: Boolean(a.ghoul_only),
      coterie: Boolean(a.coterie),
      clans_only: clanNamesOf(a.clans_only),
      cannot_buy_for: (a.cannot_buy_for || []).map((c) => clanName[c.clan] || nameFromId(c.clan).name),
      repeatable: Boolean(a.repeatable),
      max_instances: a.max_instances ?? null,
      requires: a.requires || null,
      excludes: a.excludes || [],
      aliases: a.aliases || [],
      desc: pickDesc(a),
      book: a.book,
      also_in: alsoIn(a),
      page: a.page,
    })),
    loresheets: (cat.loresheets || []).map((l) => ({
      id: l.id,
      name: l.name,
      restriction: l.restriction || null,
      clans_only: clanNamesOf(l.clans_only),
      clans_excluded: clanNamesOf(l.clans_excluded),
      disciplines_only: Array.isArray(l.disciplines_only) && l.disciplines_only.length
        ? l.disciplines_only.map((d) => discName[d] || nameFromId(d).name)
        : null,
      thin_blood_only: Boolean(l.thin_blood_only),
      levels: (l.levels || []).map((x) => ({
        dots: x.dots,
        name: x.name ?? null,
        restriction: x.restriction || null,
        clans_only: clanNamesOf(x.clans_only),
        desc: pickDesc(x),
      })),
      source: l.source || 'pdf',
      aliases: l.aliases || [],
      desc: pickDesc(l),
      book: l.book,
      also_in: alsoIn(l),
      page: l.page,
    })),
    books: cat.books || [],
  };
}

// ---------- the registry ----------

let current = fromRulesJson();
let version = 0;

/** The rules in use (the v5.json fallback until a catalog is applied). */
export function getV5Rules() {
  return current;
}

/** Bumps on every change, so components can re-render. */
export function v5RulesVersion() {
  return version;
}

/** Use the served catalog from now on (null: back to v5.json). */
export function applyV5Catalog(catalog) {
  current = catalog ? fromCatalog(catalog) : fromRulesJson();
  version += 1;
  return current;
}

export const clanNames = () => current.clans.map((c) => c.name);
export const disciplineNames = () => current.disciplines.map((d) => d.name);
export const predatorNames = () => current.predators.map((p) => p.name);

/** Powers of a Discipline (empty without a catalog: the forge falls back to free text). */
export function powersOf(discipline) {
  return current.disciplines.find((d) => d.name === discipline)?.powers || [];
}

/** Rituals ('ritual') or Oblivion ceremonies ('ceremony') of a level or lower. */
export function ritualsOf(kind, maxLevel = 5) {
  return current.rituals.filter((r) => r.kind === kind && r.level <= maxLevel);
}

/** Thin-blood alchemy formulae (data only; empty without the catalog). */
export const formulaEntries = () => current.formulae || [];

/**
 * Lower-cased names that more than one of these entries carries (two "Annabelle" loresheets, two
 * "Influencer" Merits): a dropdown shows the book next to them.
 */
export function sharedNames(entries) {
  const seen = new Map();
  (entries || []).forEach((e) => {
    const k = String(e?.name || '').trim().toLowerCase();
    if (k) seen.set(k, (seen.get(k) || 0) + 1);
  });
  return new Set([...seen].filter(([, n]) => n > 1).map(([k]) => k));
}

/** "Annabelle" or, when `shared` holds the name, "Annabelle · L.A. by Night Loresheets". */
export function optionName(entry, shared) {
  const name = entry?.name || '';
  return shared && shared.has(name.trim().toLowerCase()) && entry.book ? `${name} · ${bookTitle(entry.book)}` : name;
}

/** A loresheet level's name, or "Level N" when our sources don't give it (the Anarch sheets). */
export function levelName(level) {
  return level?.name || `Level ${level?.dots ?? '?'}`;
}

/** Catalog Merits, Backgrounds and Flaws (empty without the catalog). */
export const advantageEntries = () => current.advantages || [];
/** Catalog loresheets (empty without the catalog). */
export const loresheetEntries = () => current.loresheets || [];

const bareName = (name) => String(name || '').replace(/\s*\([^)]*\)\s*$/, '').trim().toLowerCase();
const named = (e, want) => [e.name, ...(e.aliases || [])].some((n) => String(n).toLowerCase() === want);

/**
 * The catalog entry of a sheet row: by id, else (or when the id is unknown) by name or alias (a
 * trailing "(note)" ignored).
 * kind 'flaw' looks among Flaws only, anything else among Merits and Backgrounds. Names shared by
 * several entries ("Clan Curse") prefer the `special` one ('thin_blood' | 'caitiff': the sheet's
 * clan), then the plain one.
 */
export function findAdvantage(row, kind, special = null) {
  const list = advantageEntries();
  const byId = row?.id ? list.find((a) => a.id === row.id) : null;
  if (byId) return byId;
  // an id the catalog doesn't know (renamed, another book) falls back to the name
  const want = bareName(row && typeof row === 'object' ? row.name : row);
  if (!want) return null;
  const flaw = kind === 'flaw';
  const hits = list.filter((a) => (a.kind === 'flaw') === flaw && named(a, want));
  return (
    hits.find((a) => special && a[special]) ||
    hits.find((a) => !a.thin_blood && !a.caitiff) ||
    hits[0] ||
    null
  );
}

/** The catalog loresheet of a sheet row: by id, else (or when the id is unknown) by name or alias. */
export function findLoresheet(row) {
  const list = loresheetEntries();
  const byId = row?.id ? list.find((l) => l.id === row.id) : null;
  if (byId) return byId;
  const want = bareName(row && typeof row === 'object' ? row.name : row);
  return want ? list.find((l) => named(l, want)) || null : null;
}

/**
 * The catalog's books (books.json), the core ones (tier 1) first, then by precedence and title;
 * empty without the catalog.
 */
export function bookEntries() {
  const num = (v, d) => (Number.isFinite(v) ? v : d);
  return (current.books || [])
    .filter((b) => b && typeof b.book_id === 'string' && b.book_id)
    .slice()
    .sort(
      (a, b) =>
        num(a.tier, 99) - num(b.tier, 99) ||
        num(a.precedence, 999) - num(b.precedence, 999) ||
        String(a.title || a.book_id).localeCompare(String(b.title || b.book_id))
    );
}

/** A book's title (books.json), else its id. */
export function bookTitle(bookId) {
  return current.books.find((b) => b.book_id === bookId)?.title || bookId || '';
}

/** A description in the UI language, English as fallback. */
export function descIn(entry, lang) {
  const d = entry?.desc || entry;
  if (!d || typeof d !== 'object') return '';
  return d[lang] || d.en || '';
}

/** "Corebook p. 245" style reference for an entry. */
export function bookRef(entry) {
  if (!entry?.book) return '';
  const b = current.books.find((x) => x.book_id === entry.book);
  const short = { 'v5-corebook': 'Corebook', 'v5-players-guide': "Players Guide", 'v5-companion': 'Companion' }[entry.book];
  return `${short || b?.title || entry.book}${entry.page ? `, p. ${entry.page}` : ''}`;
}
