/**
 * V5 ghouls: the pure rules of the ghoul forge (components/characterCreation/ghoul/) and its
 * payload. The server checks the same rules (backend/services/v5_ghoul_chargen.py); the shared
 * vectors (kind 'ghoul' in __fixtures__/creation-cases.json) keep the two in step. Rules:
 * docs/rules/V5.md §7, src/rules/v5.json `mortal_templates` and `ghoul`.
 *
 * Ghoul forge state ("sheet"):
 * {
 *   name, concept, ambition, desire,
 *   template: 'weak' | 'average' | 'gifted' | 'deadly' | 'player',
 *   retainerDots: 1-3 | null (what the domitor's Retainers pay; Retainers •• with 'average' = no Advantages),
 *   age, apparentAge: number | '' , ghouledSince: string,
 *   attributes: {strength..resolve}, skills: {athletics..technology} (flat),
 *   skillDistribution: 'jack' | 'balanced' | 'specialist' (the player ghoul's; a retainer's is its template),
 *   specialties: [{skill, name}] (one per rated Academics/Craft/Performance/Science, the rest the template's),
 *   power: {discipline, name} (one level-1 power of a Discipline the domitor has),
 *   advantages: [{id?, name, dots, kind, note?, custom?, levels?}], flaws: [{id?, name, dots, note?, custom?}],
 *   bonds: [{strength: 0-6 | null, note}, {name, strength, note}?] (the first is to the domitor),
 *   feeding: {last, note} (when it last fed on the domitor's Blood: a note, not a track; a V5 ghoul
 *     has no vitae, Hunger or Blood Potency), humanityTracked: bool, convictions: [{conviction, touchstone}],
 * }
 * `domitor` is the domitor's character as GET /api/characters/ lists it ({id, name, wod_meta, ...}).
 */
import V5_RULES from '../../rules/v5Rules';
import {
  V5_ATTRIBUTE_KEYS,
  V5_ATTRIBUTE_SPREAD,
  V5_FREE_SPECIALTY_SKILLS,
  V5_NAME_MAX,
  V5_SECTION_IDS,
  V5_SKILL_CATEGORIES,
  V5_SKILLS,
  V5_SKILL_DISTRIBUTIONS,
  V5_SKILL_KEYS,
  V5_SKILL_LABELS,
} from './constants';
import { advantageEntries, bookTitle, disciplineNames, findAdvantage, findLoresheet, loresheetEntries, powersOf } from './rulesData';
import { bookAllowed, entryBooks } from './creationSettings';
import {
  advantageDotChoices,
  dotChoicesText,
  dotRequirement,
  duplicateSpecialtyError,
  exclusionError,
  validateV5Skills,
  validateV5Specialties,
} from './validation';

const int = (v) => {
  const n = parseInt(v, 10);
  return Number.isFinite(n) ? n : 0;
};
const named = (rows) => (rows || []).filter((r) => r && String(r.name || '').trim());
const sumDots = (rows) => (rows || []).reduce((s, r) => s + int(r?.dots), 0);
const bare = (name) => String(name || '').replace(/\s*\([^)]*\)\s*$/, '').trim().toLowerCase();

const MT = V5_RULES.mortal_templates;
const G = V5_RULES.ghoul;
const countsOf = (o) => Object.fromEntries(Object.entries(o).map(([k, v]) => [Number(k), v]));

export const PLAYER_GHOUL = 'player';
/** The templates, as the server's MORTAL_TEMPLATES (core p. 185), plus the player ghoul (PG pp. 140-142). */
export const GHOUL_TEMPLATES = Object.fromEntries(
  ['weak', 'average', 'gifted', 'deadly'].map((k) => [
    k,
    {
      attributes: MT[k].attributes,
      skills: countsOf(MT[k].skills),
      specialties: MT[k].specialties,
      advantages_max: MT[k].advantages_max,
      flaws_max: MT[k].flaws_max,
      retainer_dots: MT[k].retainer_dots,
    },
  ])
);
export const GHOUL_TEMPLATE_KEYS = G.templates;
/** English names, as in the messages (i18nErrors translates them: ghoulTemplateName). */
export const GHOUL_TEMPLATE_LABELS = {
  weak: 'Weak mortal',
  average: 'Average mortal',
  gifted: 'Gifted mortal',
  deadly: 'Deadly mortal',
  player: 'Player ghoul',
};
export const GHOUL_HUMANITY = G.humanity;
export const GHOUL_BOND_STRENGTH_MAX = G.bond_strength_max;
export const GHOUL_RETAINER_CONVICTIONS = G.retainer_convictions;
export const TWO_MASTERS = G.second_bond_flaw;
export const CRONES_CURSE = G.crones_curse_flaw;
/** Why a ghoul can't take an entry (PG p. 141), as the server's params.why, and their English text. */
export const GHOUL_RESTRICTION_TEXT = {
  domain: 'Domain belongs to Kindred',
  feeding: 'Feeding Merits and Flaws are for Kindred',
  herd: 'Herd belongs to Kindred',
  thin_blood: 'it is for thin-bloods',
  caitiff: 'it is for Caitiff',
  coterie: "it is a coterie's, bought from the coterie pool",
};

/** Is this character (a GET /api/characters/ row) a ghoul's sheet? */
export const isGhoul = (ch) => Boolean(ch) && (ch.sheet_kind === 'ghoul' || ch.wod_meta?.sheet_kind === 'ghoul');

/** The domitor's character id a ghoul's sheet names, or null. */
export function ghoulDomitorId(ch) {
  const id = ch?.wod_meta?.ghoul?.domitor?.character_id;
  return Number.isInteger(id) && id > 0 ? id : null;
}

/**
 * May this character be a domitor? A vampire (not a ghoul) of the Vampire line, either edition: a V5
 * vampire's ghoul is a V5 sheet (this forge), a Classic one's a Classic sheet (characterSheet/classicGhoul.js).
 */
export const canBeDomitor = (ch) => Boolean(ch) && String(ch.system_type || 'vampire').toLowerCase() === 'vampire' && !isGhoul(ch);

/** A V5 domitor (the V5 ghoul forge's list). */
export const isV5Domitor = (ch) => canBeDomitor(ch) && String(ch.rules_edition || '').toLowerCase() === 'v5';

/** The template the domitor's Retainers rating buys (core p. 194): 1 Weak, 2 Average, 3 Gifted. */
export function templateForRetainerDots(dots) {
  return Object.keys(GHOUL_TEMPLATES).find((k) => GHOUL_TEMPLATES[k].retainer_dots === int(dots)) || 'gifted';
}

// ---------- Attributes and Skills ----------

/** The template's Attribute spread (a player ghoul: the vampire one). */
export const ghoulAttributeSpread = (template) => (GHOUL_TEMPLATES[template] ? GHOUL_TEMPLATES[template].attributes : V5_ATTRIBUTE_SPREAD);

/** Attributes at the template's lowest rating (what a new template starts from). */
export function emptyGhoulAttributes(template) {
  const lo = Math.min(...ghoulAttributeSpread(template));
  return Object.fromEntries(V5_ATTRIBUTE_KEYS.map((k) => [k, lo]));
}

function countBy(values) {
  const out = {};
  values.forEach((v) => {
    out[v] = (out[v] || 0) + 1;
  });
  return out;
}

const statusOf = (need, values) => {
  const have = countBy(values);
  return Object.keys(need)
    .map(Number)
    .sort((a, b) => b - a)
    .map((r) => ({ rating: r, need: need[r], have: have[r] || 0 }));
};

/** [{rating, need, have}] for the template's Attribute spread. */
export const ghoulAttributeStatus = (attrs, template) =>
  statusOf(countBy(ghoulAttributeSpread(template)), V5_ATTRIBUTE_KEYS.map((k) => int(attrs?.[k])));

/** The Skill counts {rating: n}: the template's, or the player ghoul's distribution. */
export function ghoulSkillCounts(template, distribution) {
  if (GHOUL_TEMPLATES[template]) return GHOUL_TEMPLATES[template].skills;
  return V5_SKILL_DISTRIBUTIONS[distribution]?.counts || null;
}

/** [{rating, need, have}] for the Skill counts. */
export function ghoulSkillStatus(skills, template, distribution) {
  const counts = ghoulSkillCounts(template, distribution);
  return counts ? statusOf(counts, V5_SKILL_KEYS.map((k) => int(skills?.[k])).filter((v) => v > 0)) : [];
}

/** Specialties the sheet may name: the template's own plus one per rated Academics/Craft/Performance/Science. */
export function ghoulSpecialtyCount(template, skills) {
  const free = V5_FREE_SPECIALTY_SKILLS.filter((k) => int(skills?.[k]) > 0).length;
  return GHOUL_TEMPLATES[template] ? GHOUL_TEMPLATES[template].specialties + free : free + 1;
}

const spreadText = (counts) =>
  Object.keys(counts)
    .map(Number)
    .sort((a, b) => b - a)
    .map((r) => `${counts[r]} at ${r}`)
    .join(', ');

function attributeError(attrs, template) {
  const got = V5_ATTRIBUTE_KEYS.map((k) => int(attrs?.[k])).sort((a, b) => b - a).join(',');
  const want = [...ghoulAttributeSpread(template)].sort((a, b) => b - a).join(',');
  return got === want ? null : `Attributes don't match the ${GHOUL_TEMPLATE_LABELS[template]} spread.`;
}

function skillError(skills, template) {
  const counts = GHOUL_TEMPLATES[template].skills;
  const have = countBy(V5_SKILL_KEYS.map((k) => int(skills?.[k])).filter((v) => v > 0));
  const wrong = Object.keys({ ...counts, ...have }).some((r) => (counts[r] || 0) !== (have[r] || 0));
  return wrong ? `Skills don't match the ${GHOUL_TEMPLATE_LABELS[template]} template: ${spreadText(counts)}.` : null;
}

/**
 * The template's own specialties: all but the first one on each rated Academics, Craft, Performance
 * or Science (that one is the free specialty, core p. 159). Same split as the server's
 * template_specialties.
 */
export function templateSpecialties(specialties, skills) {
  const free = new Set();
  return (specialties || []).filter((sp) => {
    if (V5_FREE_SPECIALTY_SKILLS.includes(sp.skill) && int(skills?.[sp.skill]) > 0 && !free.has(sp.skill)) {
      free.add(sp.skill);
      return false;
    }
    return true;
  });
}

function specialtyError(specialties, skills, template) {
  const list = (specialties || []).filter((s) => s && (s.skill || String(s.name || '').trim()));
  const allowed = ghoulSpecialtyCount(template, skills);
  if (list.length > allowed) {
    return `The ${GHOUL_TEMPLATE_LABELS[template]} template gives ${allowed} specialties here (you named ${list.length}).`;
  }
  for (const s of list) {
    if (!s.skill || !V5_SKILL_LABELS[s.skill]) return 'Each specialty needs a skill.';
    if (!String(s.name || '').trim()) return `Name the ${V5_SKILL_LABELS[s.skill]} specialty.`;
    if (int(skills?.[s.skill]) < 1) return `${V5_SKILL_LABELS[s.skill]} needs at least one dot for a specialty.`;
  }
  for (const k of V5_FREE_SPECIALTY_SKILLS) {
    if (int(skills?.[k]) > 0 && !list.some((s) => s.skill === k)) return `${V5_SKILL_LABELS[k]} comes with a free specialty — name it.`;
  }
  // the template's own (Gifted 1, on one of its two Skills at 4; Deadly 3; core p. 185)
  const own = templateSpecialties(list, skills);
  const need = GHOUL_TEMPLATES[template].specialties;
  if (own.length < need) {
    return `The ${GHOUL_TEMPLATE_LABELS[template]} template has ${need} specialties of its own (you named ${own.length}).`;
  }
  if (template === 'gifted' && need && !own.some((sp) => int(skills?.[sp.skill]) === 4)) {
    return "The Gifted mortal template's specialty goes on one of its Skills at 4.";
  }
  if (list.some((s) => String(s.name || '').trim().length > V5_NAME_MAX)) return `Names are at most ${V5_NAME_MAX} characters.`;
  return null;
}

// ---------- the ghoul power ----------

const sameName = (a, b) => String(a || '').trim().toLowerCase() === String(b || '').trim().toLowerCase();

/** The domitor's Disciplines with a dot ({name: the catalog's, level, powers: [names]}). */
export function domitorDisciplines(domitor) {
  const rows = Array.isArray(domitor?.wod_meta?.disciplines) ? domitor.wod_meta.disciplines : [];
  return rows
    .filter((d) => d && String(d.name || '').trim() && int(d.level) > 0)
    .map((d) => ({
      name: disciplineNames().find((n) => sameName(n, d.name)) || String(d.name).trim(),
      level: int(d.level),
      powers: (Array.isArray(d.powers) ? d.powers : []).map((p) => (p && typeof p === 'object' ? p.name : p)).filter(Boolean),
    }));
}

const powerNamed = (list, name) => list.find((p) => sameName(p.name, name) || (p.aliases || []).some((a) => sameName(a, name))) || null;

/** Does the domitor's sheet list this power (by name or alias)? null when it lists no powers there. */
function domitorHasPower(domitor, discipline, power) {
  const d = domitorDisciplines(domitor).find((x) => sameName(x.name, discipline));
  if (!d || !d.powers.length) return null;
  const entry = powerNamed(powersOf(d.name), power);
  const names = entry ? [entry.name, ...(entry.aliases || [])] : [power];
  return d.powers.some((p) => names.some((n) => sameName(n, p)));
}

/**
 * The level-1 powers of one of the domitor's Disciplines: [{name, entry, domitorHas}], the ones the
 * domitor has first. Without the catalog: the powers the domitor's sheet lists.
 */
export function ghoulPowerOptions(domitor, discipline) {
  const catalog = powersOf(discipline);
  if (!catalog.length) {
    const d = domitorDisciplines(domitor).find((x) => sameName(x.name, discipline));
    return (d?.powers || []).map((name) => ({ name, entry: null, domitorHas: true }));
  }
  return catalog
    .filter((p) => int(p.level) === 1)
    .map((p) => ({ name: p.name, entry: p, domitorHas: domitorHasPower(domitor, discipline, p.name) === true }))
    .sort((a, b) => Number(b.domitorHas) - Number(a.domitorHas));
}

function powerError(power, domitor) {
  const disc = String(power?.discipline || '').trim();
  const name = String(power?.name || '').trim();
  if (!disc || !name) return 'A ghoul starts with exactly one level-1 power (you have 0).';
  if (domitor && !domitorDisciplines(domitor).some((d) => sameName(d.name, disc))) {
    return `${disc} is not one of the domitor's Disciplines.`;
  }
  const list = powersOf(disc);
  const entry = powerNamed(list, name);
  if (list.length && !entry) return `${name} is not a ${disc} power.`;
  if (entry && int(entry.level) > 1) return `${disc}: a ghoul's power is level 1.`;
  if (domitor && domitorHasPower(domitor, disc, name) === false) {
    return `The domitor doesn't have ${entry ? entry.name : name} (${disc}): the first power is one the domitor has.`;
  }
  return null;
}

// ---------- Advantages, Flaws, loresheets ----------

/** Why a ghoul can't take this catalog entry (PG p. 141), or null: the Domain, Feeding and Herd
 * groups, thin-blood, Caitiff and coterie entries. Ghoul-only entries are open. */
export function ghoulRestriction(entry) {
  if (!entry) return null;
  const group = String(entry.group || '').toLowerCase();
  const byGroup = G.cannot_buy_groups.find((g) => g.toLowerCase() === group);
  if (byGroup) return byGroup.toLowerCase();
  return G.cannot_buy_flags.find((f) => entry[f]) || null;
}

/** Catalog Backgrounds, Merits or Flaws a ghoul may take (from the chronicle's books when `settings` are given). */
export function ghoulAdvantageOptions(kind, settings = null) {
  return advantageEntries().filter((a) => a.kind === kind && a.group !== 'Loresheets' && !ghoulRestriction(a) && bookAllowed(settings, a));
}

/** Loresheets a ghoul may take: Kindred ones too, through the domitor's connections (PG p. 141); not thin-blood ones. */
export function ghoulLoresheetOptions(settings = null) {
  return loresheetEntries().filter((l) => !l.thin_blood_only && bookAllowed(settings, l));
}

const hasEntry = (rows, id) => {
  const want = id.split(':').pop().replace(/^ghoul-/, '').replace(/-/g, ' ');
  return named(rows).some((r) => r.id === id || bare(r.name).replace(/['’]/g, '') === want);
};

/** Does the sheet carry the Two Masters Flaw (a second Blood Bond, Blood-Stained Love p. 151)? */
export const hasTwoMasters = (sheet) => hasEntry(sheet?.flaws, TWO_MASTERS);

/** First problem with the catalog rows (as validateV5AdvantageRows, without clan rules), or null. */
export function validateGhoulAdvantageRows(sheet) {
  const s = sheet || {};
  const rows = [...named(s.advantages).map((r) => [r, false]), ...named(s.flaws).map((r) => [r, true])].map(([r, flaw]) => [
    r,
    r.kind === 'loresheet' ? findLoresheet(r) : r.custom ? null : findAdvantage(r, flaw ? 'flaw' : r.kind),
    flaw,
  ]);
  const counts = {};
  rows.forEach(([, e]) => {
    if (e) counts[e.id] = (counts[e.id] || 0) + 1;
  });
  for (const [r, e] of rows) {
    if (!e) continue;
    if (r.kind === 'loresheet') {
      if (!(r.levels || []).length) return `Pick at least one level of ${e.name}.`;
      if (e.thin_blood_only) return `${e.name} is not open to ghouls: ${GHOUL_RESTRICTION_TEXT.thin_blood} (Players Guide p. 141).`;
      if (counts[e.id] > 1) return `${e.name} can be taken only once.`;
      continue;
    }
    const why = ghoulRestriction(e);
    if (why) return `${r.name} is not open to ghouls: ${GHOUL_RESTRICTION_TEXT[why]} (Players Guide p. 141).`;
    const choices = advantageDotChoices(e);
    if (choices.length && !choices.includes(int(r.dots))) return `${e.name} takes ${dotChoicesText(choices)} dots (you have ${int(r.dots)}).`;
    if (!e.repeatable && counts[e.id] > 1) return `${e.name} can be taken only once.`;
    if (e.repeatable && e.max_instances && counts[e.id] > e.max_instances) return `${e.name} can be taken at most ${e.max_instances} times.`;
    const req = dotRequirement(e);
    if (req && (!req.onlyAbove1 || int(r.dots) > 1)) {
      const have =
        req.kind === 'discipline'
          ? sameName(req.name, s.power?.discipline) ? 1 : 0
          : Math.max(0, ...rows.filter(([x, xe, flaw]) => !flaw && x.kind !== 'loresheet' && (xe ? xe.name.toLowerCase() : bare(x.name)) === req.name.toLowerCase()).map(([x]) => int(x.dots)));
      if (have < req.dots) return req.dots > 1 ? `${e.name} needs ${req.name} at ${req.dots} dots or more.` : `${e.name} needs ${req.name} on the sheet.`;
    }
    if (/^ancilla or older$/i.test(String(e.requires || '').trim())) return `${e.name} is only for ancillae or older.`;
  }
  return exclusionError(rows.filter(([, e]) => e && e.excludes).map(([, e]) => e));
}

// ---------- derived values ----------

/** Health, Willpower, Humanity and the Advantage/Flaw budget of the sheet. */
export function deriveGhoul(sheet) {
  const s = sheet || {};
  const a = s.attributes || {};
  const tpl = GHOUL_TEMPLATES[s.template];
  const crone = hasEntry(s.flaws, CRONES_CURSE) ? G.crones_curse_health : 0;
  const noAdvantages = s.template === 'average' && int(s.retainerDots) === G.retainer_ghoul_no_advantages_at;
  return {
    health: int(a.stamina) + 3 + crone,
    willpower: int(a.composure) + int(a.resolve),
    humanity: s.template === PLAYER_GHOUL || s.humanityTracked ? GHOUL_HUMANITY : null,
    advantage_dots: tpl ? (noAdvantages ? 0 : tpl.advantages_max) : G.player_template.advantages_dots,
    flaw_max_dots: tpl ? tpl.flaws_max : null,
    flaw_min_dots: tpl ? 0 : G.player_template.flaws_min_dots,
  };
}

// ---------- the whole sheet ----------

const S = V5_SECTION_IDS;

/** Problems per forge section ({sectionId: English message}; i18nErrors translates them). */
export function validateGhoulSheet(sheet, domitor, settings) {
  const s = sheet || {};
  const err = {};
  const add = (id, msg) => {
    if (msg && !err[id]) err[id] = msg;
  };
  const template = s.template;
  const tpl = GHOUL_TEMPLATES[template];
  const player = template === PLAYER_GHOUL;
  if (!String(s.name || '').trim()) add(S.identity, 'Character name is required.');
  if (!tpl && !player) add(S.identity, 'Choose a template for the ghoul.');
  if (!domitor) add(S.identity, "Choose the ghoul's domitor.");
  if (tpl && s.retainerDots != null && s.retainerDots !== '') {
    if (tpl.retainer_dots == null) add(S.identity, 'No Retainers rating buys a Deadly mortal.');
    else if (int(s.retainerDots) !== tpl.retainer_dots) {
      add(S.identity, `A ${GHOUL_TEMPLATE_LABELS[template]} ghoul takes Retainers ${tpl.retainer_dots}; the domitor pays ${int(s.retainerDots)}.`);
    }
  }
  if (tpl || player) {
    add(S.attributes, attributeError(s.attributes, template));
    if (player) {
      add(S.skills, validateV5Skills(s.skills, s.skillDistribution));
      add(S.skills, validateV5Specialties(s.specialties, s.skills));
    } else {
      add(S.skills, skillError(s.skills, template));
      add(S.skills, specialtyError(s.specialties, s.skills, template));
    }
    add(S.skills, duplicateSpecialtyError(s.specialties));
  }
  add(S.disciplines, powerError(s.power, domitor));

  const d = deriveGhoul(s);
  const adv = sumDots(named(s.advantages));
  const flaws = sumDots(named(s.flaws));
  if (tpl || player) {
    if (adv > d.advantage_dots) add(S.advantages, `Advantages: at most ${d.advantage_dots} dots (you have ${adv}).`);
    if (flaws < d.flaw_min_dots) add(S.advantages, `Take at least ${d.flaw_min_dots} dots of Flaws (you have ${flaws}).`);
    if (d.flaw_max_dots != null && flaws > d.flaw_max_dots) {
      add(S.advantages, `The ${GHOUL_TEMPLATE_LABELS[template]} template allows at most ${d.flaw_max_dots} dots of Flaws (you have ${flaws}).`);
    }
  }
  const cap = settings?.flaws_max_dots;
  if (cap != null && flaws > cap) add(S.advantages, `This chronicle allows at most ${cap} dots of Flaws of your own (you have ${flaws}).`);
  add(S.advantages, validateGhoulAdvantageRows(s));
  const unknown = (r, kind) => r.custom || !findAdvantage(r, kind);
  const free = [...named(s.advantages).filter((r) => r.kind !== 'loresheet' && unknown(r, r.kind)), ...named(s.flaws).filter((r) => unknown(r, 'flaw'))];
  if (free.some((r) => int(r.dots) < 1 || int(r.dots) > 5)) add(S.advantages, 'Each Advantage or Flaw is 1–5 dots.');
  if (settings?.allowed_books?.length) {
    [...named(s.advantages).map((r) => [r, r.kind]), ...named(s.flaws).map((r) => [r, 'flaw'])]
      .filter(([r]) => !r.custom)
      .forEach(([r, kind]) => {
        const e = kind === 'loresheet' ? findLoresheet(r) : findAdvantage(r, kind);
        if (e && !bookAllowed(settings, e)) add(S.advantages, `${r.name} comes from a book this chronicle doesn't use (${bookTitle(entryBooks(e)[0])}).`);
      });
  }

  const bonds = Array.isArray(s.bonds) ? s.bonds : [];
  if (!bonds.length || bonds.length > 2) add(S.bond, 'A ghoul has one Blood Bond, to the domitor (two with Two Masters).');
  if (bonds.some((b) => b && b.strength != null && b.strength !== '' && (int(b.strength) < 0 || int(b.strength) > GHOUL_BOND_STRENGTH_MAX))) {
    add(S.bond, `Bond Strength is 0–${GHOUL_BOND_STRENGTH_MAX}.`);
  }
  if (bonds.length > 1 && !hasTwoMasters(s)) add(S.bond, 'A second Blood Bond needs the Two Masters Flaw.');

  const conv = (s.convictions || []).filter((c) => c && (String(c.conviction || '').trim() || String(c.touchstone || '').trim()));
  const [lo, hi] = player ? V5_RULES.creation.convictions : GHOUL_RETAINER_CONVICTIONS;
  if (conv.length < lo || conv.length > hi) add(S.humanity, `Write ${lo}–${hi} Convictions, each with a Touchstone.`);
  else if (conv.some((c) => !String(c.conviction || '').trim() || !String(c.touchstone || '').trim())) {
    add(S.humanity, 'Each Conviction needs a Touchstone (and vice versa).');
  }
  return err;
}

const optInt = (v, lo, hi) => {
  if (v === '' || v == null) return null;
  const n = parseInt(v, 10);
  return Number.isFinite(n) ? Math.max(lo, Math.min(hi, n)) : null;
};
const text = (v, max) => String(v || '').trim().slice(0, max);

/** Specialties as stored: the free Academics/Craft/Performance/Science ones bare, the template's `source: 'template'`. */
function storedSpecialties(sheet) {
  const list = (sheet.specialties || []).filter((sp) => sp && sp.skill && String(sp.name || '').trim());
  const own = new Set(GHOUL_TEMPLATES[sheet.template] ? templateSpecialties(list, sheet.skills) : []);
  return list.map((sp) => ({ skill: sp.skill, name: String(sp.name).trim(), ...(own.has(sp) ? { source: 'template' } : {}) }));
}

/** Body pieces for POST /api/characters/ (campaign_id null): the ghoul's V5 storage shape. */
export function buildGhoulPayload(sheet, domitor) {
  const s = sheet || {};
  const d = deriveGhoul(s);
  const skills = {};
  V5_SKILL_CATEGORIES.forEach((cat) => {
    skills[cat] = Object.fromEntries(V5_SKILLS[cat].map(([k]) => [k, int(s.skills?.[k])]));
  });
  skills.specialties = storedSpecialties(s);
  skills.distribution = s.template === PLAYER_GHOUL ? s.skillDistribution : s.template;
  const attributes = Object.fromEntries(V5_ATTRIBUTE_KEYS.map((k) => [k, int(s.attributes?.[k])]));

  // the same rows as buildV5Payload: the English name with the note in brackets, the catalog id
  const ownRow = (a, kind) => {
    const name = String(a.name).trim();
    const note = String(a.note || '').trim();
    return {
      ...(a.id ? { id: a.id } : {}),
      name: note && kind !== 'loresheet' ? `${name} (${note})` : name,
      dots: int(a.dots),
      kind,
      ...(note ? { note } : {}),
      ...(a.custom ? { custom: true } : {}),
      ...(kind === 'loresheet' ? { levels: [...(a.levels || [])].map(int).sort((x, y) => x - y) } : {}),
    };
  };
  const advKind = (k) => (k === 'background' || k === 'loresheet' ? k : 'merit');
  const advantages = named(s.advantages).map((a) => ownRow(a, advKind(a.kind)));
  const flaws = named(s.flaws).map((f) => ownRow(f, 'flaw'));
  const touchstones = (s.convictions || [])
    .filter((c) => c && String(c.conviction || '').trim())
    .map((c) => ({ name: String(c.touchstone || '').trim(), conviction: String(c.conviction).trim() }));

  const domId = domitor ? int(domitor.id) : null;
  const domName = domitor ? String(domitor.name || '') : '';
  const bonds = (Array.isArray(s.bonds) ? s.bonds : []).slice(0, 2).map((b, i) => ({
    character_id: i === 0 ? domId : null,
    name: i === 0 ? domName : text(b?.name, 120),
    strength: optInt(b?.strength, 0, GHOUL_BOND_STRENGTH_MAX),
    note: text(b?.note, 500),
  }));
  const power = s.power && String(s.power.discipline || '').trim() ? s.power : null;
  const wodMeta = {
    edition: 'v5',
    sheet_kind: 'ghoul',
    concept: String(s.concept || '').trim(),
    ambition: String(s.ambition || '').trim(),
    desire: String(s.desire || '').trim(),
    ghoul: {
      template: s.template,
      retainer_dots: optInt(s.retainerDots, 1, 3),
      domitor: { character_id: domId, name: domName, clan: domitor?.wod_meta?.clan || null },
      age: optInt(s.age, 0, 150),
      apparent_age: optInt(s.apparentAge, 0, 150),
      ghouled_since: text(s.ghouledSince, 200),
      bonds,
      // a note on feeding, not a track: a V5 ghoul has no vitae, Hunger or Blood Potency (core p. 234)
      feeding: { last: text(s.feeding?.last, 60), note: text(s.feeding?.note, 500) },
    },
    disciplines: power
      ? [{ name: String(power.discipline).trim(), level: 1, powers: String(power.name || '').trim() ? [String(power.name).trim()] : [], ghoul: true }]
      : [],
    ...(d.humanity != null ? { humanity: d.humanity, stains: 0 } : {}),
    health: { max: d.health, superficial: 0, aggravated: 0 },
    willpower: { max: d.willpower, superficial: 0, aggravated: 0 },
    advantages,
    flaws,
    touchstones,
    chronicle_tenets: '',
    // which forge built the sheet (the ghoul forge, Forge v2's settings)
    forge: { version: 2, kind: 'ghoul', settings_v: 1 },
  };
  const entries = [
    ...advantages.map((a) => ({ name: a.name, points: a.dots, note: a.kind })),
    ...flaws.map((f) => ({ name: f.name, points: -f.dots, note: 'flaw' })),
  ];
  return {
    system_type: 'vampire',
    attributes,
    skills,
    merits_flaws: entries.length ? { entries } : {},
    wod_meta: wodMeta,
  };
}
