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
 *   grant     { pick: 'all' | 'one_of' | 'split', options: [{ name, dots: n | null, note, kind }], dots_total }
 *   power     { id, name, level, amalgam: { discipline, level } | null, prerequisite: [name] | null,
 *               dice_pool, rouse_cost, desc, book, page }
 *   ritual    { id, name, level, kind: 'ritual' | 'ceremony', prerequisite: name | null, desc, book, page }
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
  const [kind, slug] = String(id || '').split(':');
  return { kind: kind || 'merit', name: titleOf(slug || kind) };
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
    books: [],
  };
}

// ---------- from the served catalog ----------

const pickDesc = (e) => (e && e.desc && (e.desc.en || e.desc.el) ? e.desc : null);

function fromCatalog(cat) {
  const clanName = Object.fromEntries((cat.clans || []).map((c) => [c.id, c.name]));
  const discName = Object.fromEntries((cat.disciplines || []).map((d) => [d.id, d.name]));
  const powerName = {};
  (cat.disciplines || []).forEach((d) => (d.powers || []).forEach((p) => (powerName[p.id] = p.name)));
  const grant = (g, fallbackKind) => ({
    pick: g.pick || 'all',
    dots_total: g.dots_total ?? null,
    options: (g.options || []).map((o) => {
      const { kind, name } = nameFromId(o.id);
      return { id: o.id, name, dots: o.dots ?? null, note: o.note || '', kind: kind || fallbackKind };
    }),
  });
  const prereq = (p) => {
    if (!p) return null;
    if (p.power_id) return [powerName[p.power_id] || nameFromId(p.power_id).name];
    if (Array.isArray(p.any_of)) return p.any_of.map((x) => powerName[x.power_id || x] || nameFromId(x.power_id || x).name);
    return null;
  };
  const ritualOf = (kind) => (r) => ({
    id: r.id,
    name: r.name,
    level: r.level,
    kind,
    discipline: discName[r.discipline] || null,
    prerequisite: prereq(r.prerequisite)?.[0] || null,
    desc: pickDesc(r),
    book: r.book,
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
      page: c.page,
    })),
    disciplines: (cat.disciplines || []).map((d) => ({
      id: d.id,
      name: d.name,
      desc: pickDesc(d),
      powers: (d.powers || []).map((p) => ({
        id: p.id,
        name: p.name,
        level: p.level,
        amalgam: p.amalgam ? { discipline: discName[p.amalgam.discipline] || nameFromId(p.amalgam.discipline).name, level: p.amalgam.level } : null,
        prerequisite: prereq(p.prerequisite),
        dice_pool: p.dice_pool || null,
        rouse_cost: p.rouse_cost ?? null,
        desc: pickDesc(p),
        book: p.book,
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
      page: p.page,
    })),
    rituals: [...(cat.rituals || []).map(ritualOf('ritual')), ...(cat.ceremonies || []).map(ritualOf('ceremony'))],
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
