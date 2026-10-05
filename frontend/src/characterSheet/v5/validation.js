/**
 * V5 character creation: pure validators, derived traits and the API payload.
 * Rules: docs/rules/V5.md §4 (core pp. 135–154, Errata 2.0) via src/rules/v5.json.
 *
 * Wizard state ("sheet") shape:
 * {
 *   name, concept, sire, ambition, desire, chronicle_tenets, background,
 *   clan, age: 'childer'|'neonate'|'ancilla', generation: number,
 *   attributes: {strength..resolve}, skillDistribution: 'jack'|'balanced'|'specialist',
 *   skills: {athletics..technology} (flat, BEFORE the predator type's specialty/dot),
 *   specialties: [{skill, name}] (free ones, not the predator one),
 *   disciplines: [{name, level, powers: []}] (creation 2 + 1, BEFORE the predator dot),
 *   predatorType, predatorSpecialty (index into the type's specialty_choice),
 *   startingRitual: string (one free Level 1 ritual with Blood Sorcery 1+),
 *   predatorDiscipline (name), extraPowers: {[discipline]: [power]} (powers for a predator/XP
 *   Discipline that isn't one of the two picks), advantages: [{name, dots, kind: 'merit'|'background'}],
 *   flaws: [{name, dots}], convictions: [{conviction, touchstone}],
 *   fledglingHumanity: bool (childer only: start at Humanity 8 instead of 7),
 *   thinBloodMerits: [{name}], thinBloodFlaws: [{name}] (thin-bloods: 1–3 each, equal counts),
 *   xpPurchases: starting experience (neonates 15, ancillae 35), one entry per dot, in order:
 *     {kind: 'attribute'|'skill', trait: key} | {kind: 'discipline', trait: name}
 *     | {kind: 'specialty', skill: key, trait: name} | {kind: 'ritual', trait: name, level}
 * }
 */
import {
  BLOOD_SORCERY,
  CAITIFF,
  THIN_BLOOD,
  V5_AGE_BRACKETS,
  V5_ADVANTAGE_DOTS,
  V5_ATTRIBUTE_KEYS,
  V5_ATTRIBUTE_SPREAD,
  V5_CLANS,
  V5_CONVICTIONS,
  V5_DISCIPLINE_DOTS,
  V5_DISCIPLINES as V5_DISCIPLINES_ALL,
  V5_FLAWS_MIN_DOTS,
  V5_FLEDGLING_HUMANITY,
  V5_FREE_SPECIALTY_SKILLS,
  V5_PREDATOR_TYPES,
  V5_SECTION_IDS,
  V5_SKILLS,
  V5_SKILL_CATEGORIES,
  V5_SKILL_DISTRIBUTIONS,
  V5_SKILL_KEYS,
  V5_SKILL_LABELS,
  V5_STARTING_HUMANITY,
  V5_STARTING_HUNGER,
  V5_STARTING_RITUAL,
  V5_THIN_BLOOD_MERITS,
  V5_ATTRIBUTES,
  V5_NAME_MAX,
  V5_XP_COSTS,
  V5_XP_MAX_DOTS,
  generationBloodPotency,
  parsePredatorDiscipline,
  parsePredatorSpecialty,
} from './constants';

const int = (v) => {
  const n = parseInt(v, 10);
  return Number.isFinite(n) ? n : 0;
};

export function emptyV5Attributes() {
  return Object.fromEntries(V5_ATTRIBUTE_KEYS.map((k) => [k, 1]));
}

export function emptyV5Skills() {
  return Object.fromEntries(V5_SKILL_KEYS.map((k) => [k, 0]));
}

function countBy(values) {
  const out = {};
  values.forEach((v) => {
    out[v] = (out[v] || 0) + 1;
  });
  return out;
}

// ---------- Attributes ----------

/** [{rating, need, have}] for each rating in the spread (4,3,2,1). */
export function attributeSpreadStatus(attrs) {
  const need = countBy(V5_ATTRIBUTE_SPREAD);
  const have = countBy(V5_ATTRIBUTE_KEYS.map((k) => int(attrs?.[k])));
  return Object.keys(need)
    .map(Number)
    .sort((a, b) => b - a)
    .map((r) => ({ rating: r, need: need[r], have: have[r] || 0 }));
}

export function validateV5Attributes(attrs) {
  const vals = V5_ATTRIBUTE_KEYS.map((k) => int(attrs?.[k]));
  if (vals.some((v) => v < 1 || v > 4)) {
    return 'Attributes start between 1 and 4 at creation.';
  }
  const got = [...vals].sort((a, b) => b - a).join(',');
  const want = [...V5_ATTRIBUTE_SPREAD].sort((a, b) => b - a).join(',');
  if (got !== want) {
    return 'Attributes must be one at 4, three at 3, four at 2 and one at 1.';
  }
  return null;
}

// ---------- Skills ----------

/** [{rating, need, have}] for the chosen distribution (ratings > 0). */
export function skillSpreadStatus(skills, distribution) {
  const dist = V5_SKILL_DISTRIBUTIONS[distribution];
  if (!dist) return [];
  const have = countBy(V5_SKILL_KEYS.map((k) => int(skills?.[k])).filter((v) => v > 0));
  return Object.keys(dist.counts)
    .map(Number)
    .sort((a, b) => b - a)
    .map((r) => ({ rating: r, need: dist.counts[r], have: have[r] || 0 }));
}

export function validateV5Skills(skills, distribution) {
  const dist = V5_SKILL_DISTRIBUTIONS[distribution];
  if (!dist) return 'Choose a skill distribution.';
  const vals = V5_SKILL_KEYS.map((k) => int(skills?.[k]));
  const maxRating = Math.max(...Object.keys(dist.counts).map(Number));
  if (vals.some((v) => v < 0 || v > maxRating)) {
    return `${dist.label}: no skill above ${maxRating} at creation.`;
  }
  const have = countBy(vals.filter((v) => v > 0));
  const wrong = Object.keys({ ...dist.counts, ...have })
    .map(Number)
    .filter((r) => (dist.counts[r] || 0) !== (have[r] || 0));
  if (wrong.length) {
    const want = Object.keys(dist.counts)
      .map(Number)
      .sort((a, b) => b - a)
      .map((r) => `${dist.counts[r]} at ${r}`)
      .join(', ');
    return `${dist.label} needs exactly ${want}.`;
  }
  return null;
}

/** Free specialties: one per rated Academics/Craft/Performance/Science, plus one of your choice. */
export function freeSpecialtyCount(skills) {
  return V5_FREE_SPECIALTY_SKILLS.filter((k) => int(skills?.[k]) > 0).length + 1;
}

export function validateV5Specialties(specialties, skills) {
  const list = (specialties || []).filter((s) => s && (s.skill || String(s.name || '').trim()));
  const allowed = freeSpecialtyCount(skills);
  if (list.length > allowed) {
    return `You have ${allowed} free specialties (one per rated Academics/Craft/Performance/Science, plus one).`;
  }
  for (const s of list) {
    if (!s.skill || !V5_SKILL_LABELS[s.skill]) return 'Each specialty needs a skill.';
    if (!String(s.name || '').trim()) return `Name the ${V5_SKILL_LABELS[s.skill]} specialty.`;
    if (int(skills?.[s.skill]) < 1) {
      return `${V5_SKILL_LABELS[s.skill]} needs at least one dot for a specialty.`;
    }
  }
  for (const k of V5_FREE_SPECIALTY_SKILLS) {
    if (int(skills?.[k]) > 0 && !list.some((s) => s.skill === k)) {
      return `${V5_SKILL_LABELS[k]} comes with a free specialty — name it.`;
    }
  }
  return null;
}

// ---------- Clan & disciplines ----------

export function clanInfo(clan) {
  return V5_CLANS.find((c) => c.name === clan) || null;
}

/** Disciplines a clan may take at creation ('any' for Caitiff, none for thin-bloods). */
export function creationDisciplineOptions(clan, allDisciplines) {
  if (clan === THIN_BLOOD) return [];
  if (clan === CAITIFF) return allDisciplines.filter((d) => d !== 'Thin-Blood Alchemy');
  return clanInfo(clan)?.disciplines || [];
}

export function validateV5Disciplines(disciplines, clan, allDisciplines) {
  const list = (disciplines || []).filter((d) => d && d.name);
  if (clan === THIN_BLOOD) {
    return list.length ? 'Thin-bloods start with no Disciplines.' : null;
  }
  const options = creationDisciplineOptions(clan, allDisciplines);
  if (list.length !== 2) {
    return clan === CAITIFF
      ? 'Pick two Disciplines: one at 2 dots and one at 1 dot.'
      : 'Pick two clan Disciplines: one at 2 dots and one at 1 dot.';
  }
  if (list[0].name === list[1].name) return 'Pick two different Disciplines.';
  const levels = list.map((d) => int(d.level)).sort((a, b) => b - a);
  if (levels.join(',') !== [...V5_DISCIPLINE_DOTS].sort((a, b) => b - a).join(',')) {
    return 'One Discipline at 2 dots and one at 1 dot.';
  }
  const bad = list.find((d) => !options.includes(d.name));
  if (bad) return `${bad.name} is not a ${clan} clan Discipline.`;
  return null;
}

// ---------- Predator type ----------

export function predatorInfo(name) {
  return V5_PREDATOR_TYPES.find((p) => p.name === name) || null;
}

/** Discipline options of a predator type for this clan (drops "Tremere only" for others). */
export function predatorDisciplineOptions(predatorType, clan) {
  const p = predatorInfo(predatorType);
  if (!p) return [];
  return p.discipline_choice
    .map(parsePredatorDiscipline)
    .filter((d) => !d.clan || d.clan === clan)
    .map((d) => d.name);
}

// ---------- Derived traits ----------

/** The Humanity 8 fledgling option only applies to just-Embraced childer. */
export function fledglingHumanityAllowed(sheet) {
  return sheet?.age === 'childer';
}

// ---------- Thin-blood Merits & Flaws ----------

const namedList = (rows) => (rows || []).filter((r) => r && String(r.name || '').trim());

/**
 * Thin-bloods take 1–3 thin-blood Merits and the same number of thin-blood Flaws.
 * They have no dot value and don't count toward Advantage/Flaw totals (V5.md §2.7, §4 step 2).
 */
export function validateThinBloodMeritsFlaws(sheet) {
  if (sheet?.clan !== THIN_BLOOD) return null;
  const [lo, hi] = V5_THIN_BLOOD_MERITS;
  const m = namedList(sheet.thinBloodMerits).length;
  const f = namedList(sheet.thinBloodFlaws).length;
  if (m < lo || m > hi) {
    return `Thin-bloods take ${lo}–${hi} thin-blood Merits (you have ${m}).`;
  }
  if (f !== m) {
    return `Take as many thin-blood Flaws as thin-blood Merits (${m} Merits, ${f} Flaws).`;
  }
  return null;
}

export function deriveV5(sheet) {
  const s = sheet || {};
  const attrs = finalAttributes(s);
  const p = predatorInfo(s.predatorType);
  const age = V5_AGE_BRACKETS[s.age] || V5_AGE_BRACKETS.neonate;
  const gen = int(s.generation) || 13;
  const genRow = generationBloodPotency(gen);
  const thin = s.clan === THIN_BLOOD || Boolean(genRow?.thin_blood);
  let bp = genRow?.starting_bp ?? genRow?.min_bp ?? 1;
  if (!thin) {
    bp += age.blood_potency_bonus || 0;
    bp += p?.blood_potency || 0;
    if (genRow) bp = Math.min(bp, genRow.max_bp);
  } else {
    bp = 0;
  }
  const startHumanity = fledglingHumanityAllowed(s) && s.fledglingHumanity
    ? V5_FLEDGLING_HUMANITY
    : V5_STARTING_HUMANITY;
  let humanity = startHumanity + (p?.humanity || 0) + (age.humanity_change || 0);
  humanity = Math.max(0, Math.min(10, humanity));
  return {
    health: int(attrs.stamina) + 3,
    willpower: int(attrs.composure) + int(attrs.resolve),
    humanity,
    hunger: V5_STARTING_HUNGER,
    blood_potency: bp,
    blood_potency_range: genRow ? [genRow.min_bp, genRow.max_bp] : null,
    thin_blood: thin,
    advantage_dots: V5_ADVANTAGE_DOTS + (age.advantage_dots_bonus || 0),
    flaw_min_dots: V5_FLAWS_MIN_DOTS + (age.flaw_dots_bonus || 0),
  };
}

/** Attributes after XP dots. */
export function finalAttributes(sheet) {
  const out = Object.fromEntries(V5_ATTRIBUTE_KEYS.map((k) => [k, int(sheet?.attributes?.[k])]));
  xpOf(sheet, 'attribute').forEach((x) => {
    if (x.trait in out) out[x.trait] += 1;
  });
  return out;
}

/** Skills + specialties after the predator type's specialty and any XP dots/specialties. */
export function finalSkills(sheet) {
  const { skills, specialties } = creationSkills(sheet);
  xpOf(sheet, 'skill').forEach((x) => {
    if (x.trait in skills) skills[x.trait] += 1;
  });
  xpOf(sheet, 'specialty').forEach((x) => {
    const name = String(x.trait || '').trim();
    if (x.skill && name) specialties.push({ skill: x.skill, name, source: 'xp' });
  });
  return { skills, specialties };
}

/** Skills + specialties after the predator type's specialty (0-dot skill → 1 dot instead). */
function creationSkills(sheet) {
  const skills = { ...emptyV5Skills(), ...(sheet?.skills || {}) };
  Object.keys(skills).forEach((k) => {
    skills[k] = int(skills[k]);
  });
  const specialties = (sheet?.specialties || [])
    .filter((s) => s && s.skill && String(s.name || '').trim())
    .map((s) => ({ skill: s.skill, name: String(s.name).trim() }));
  const p = predatorInfo(sheet?.predatorType);
  const idx = sheet?.predatorSpecialty;
  if (p && idx != null && p.specialty_choice[idx] != null) {
    const ps = parsePredatorSpecialty(p.specialty_choice[idx]);
    if (skills[ps.skill] === 0) {
      skills[ps.skill] = 1;
    } else {
      specialties.push({ skill: ps.skill, name: ps.name, source: 'predator' });
    }
  }
  return { skills, specialties };
}

/**
 * One row per Discipline with where its dots come from, for the forge display and the payload.
 * Clan picks keep their index (`pick`, empty names included so the forge can render the selects);
 * a predator or XP Discipline that isn't a pick gets its own row (`pick: null`), whose powers
 * come from sheet.extraPowers[name]. `powers` has one slot per final dot.
 * [{ name, pick, base, predator: 0|1, xp, level, powers }]
 */
export function disciplineRows(sheet) {
  const s = sheet || {};
  if (s.clan === THIN_BLOOD) return [];
  const extraPowers = s.extraPowers || {};
  const rows = (s.disciplines || []).map((d, i) => ({
    name: d?.name || '',
    pick: i,
    base: int(d?.level),
    predator: 0,
    xp: 0,
    raw: d?.powers || [],
  }));
  const ensure = (name) => {
    let r = rows.find((x) => x.name && x.name === name);
    if (!r) {
      r = { name, pick: null, base: 0, predator: 0, xp: 0, raw: extraPowers[name] || [] };
      rows.push(r);
    }
    return r;
  };
  if (s.predatorDiscipline) ensure(s.predatorDiscipline).predator = 1;
  (s.xpPurchases || []).forEach((x) => {
    if (x?.kind === 'discipline' && x.trait) ensure(x.trait).xp += 1;
  });
  return rows.map(({ raw, ...r }) => {
    const level = r.base + r.predator + r.xp;
    return { ...r, level, powers: Array.from({ length: level }, (_, i) => String(raw[i] || '')) };
  });
}

/** Disciplines after the predator type's extra dot and any XP dots: [{name, level, powers}]. */
export function finalDisciplines(sheet) {
  return disciplineRows(sheet)
    .filter((r) => r.name && r.level > 0)
    .map((r) => ({
      name: r.name,
      level: r.level,
      powers: r.powers.map((x) => x.trim()).filter(Boolean),
    }));
}

// ---------- Rituals ----------

/** Final Blood Sorcery rating (picks + predator dot + XP dots). */
export function bloodSorceryLevel(sheet) {
  return disciplineRows(sheet).find((r) => r.name === BLOOD_SORCERY)?.level || 0;
}

/** The free Level 1 ritual needs at least one dot in Blood Sorcery. */
export function startingRitualAllowed(sheet) {
  return bloodSorceryLevel(sheet) >= 1;
}

/**
 * Rituals for wod_meta.rituals: the free starting one (if allowed and named), then XP ones.
 * [{ name, level, source: 'creation'|'xp' }]
 */
export function finalRituals(sheet) {
  const out = [];
  const start = String(sheet?.startingRitual || '').trim();
  if (start && startingRitualAllowed(sheet)) {
    out.push({ name: start, level: V5_STARTING_RITUAL.level, source: 'creation' });
  }
  (sheet?.xpPurchases || []).forEach((x) => {
    if (x?.kind === 'ritual' && String(x.trait || '').trim()) {
      out.push({ name: String(x.trait).trim(), level: int(x.level), source: 'xp' });
    }
  });
  return out;
}

// ---------- Starting experience (V5.md §4 step 14, XP costs p. 151) ----------

function xpOf(sheet, kind) {
  return (sheet?.xpPurchases || []).filter((x) => x && x.kind === kind);
}

/** XP a new character gets from its age: neonates 15, ancillae 35, childer none. */
export function startingXp(sheet) {
  if (sheet?.clan === THIN_BLOOD) return 0;
  return V5_AGE_BRACKETS[sheet?.age]?.xp || 0;
}

const ATTRIBUTE_LABELS = Object.fromEntries([
  ...V5_ATTRIBUTES.physical,
  ...V5_ATTRIBUTES.social,
  ...V5_ATTRIBUTES.mental,
]);

/** Disciplines XP can buy: everything but Thin-Blood Alchemy (thin-bloods buy nothing here). */
export function xpDisciplineOptions(sheet, allDisciplines) {
  if (sheet?.clan === THIN_BLOOD) return [];
  return allDisciplines.filter((d) => d !== 'Thin-Blood Alchemy');
}

/** XP multiplier for a Discipline: Caitiff 6, clan 5, anything else 7. */
export function disciplineXpMultiplier(sheet, name) {
  if (sheet?.clan === CAITIFF) return V5_XP_COSTS.caitiff_discipline;
  return (clanInfo(sheet?.clan)?.disciplines || []).includes(name)
    ? V5_XP_COSTS.clan_discipline
    : V5_XP_COSTS.other_discipline;
}

/**
 * Walk sheet.xpPurchases in order and price each one. Dots are bought one at a time, each costing
 * the new rating × the multiplier; a specialty is flat; a ritual is level × 3 and needs Blood
 * Sorcery at least its level. Returns { total, spent, unspent, log, errors }, where log entries are
 * { kind, trait, what, from, to, cost } (specialty: from 0 to 1; ritual: from 0 to its level).
 */
export function xpLedger(sheet, allDisciplines = V5_DISCIPLINES_ALL) {
  const s = sheet || {};
  const total = startingXp(s);
  const purchases = (s.xpPurchases || []).filter(Boolean);
  const log = [];
  const errors = [];
  const at = {};
  const rows = disciplineRows(s);
  const creation = creationSkills(s).skills;
  const skillsNow = finalSkills(s).skills;
  const bs = bloodSorceryLevel(s);
  const discOk = xpDisciplineOptions(s, allDisciplines);

  if (purchases.length && !total) errors.push('This age has no starting experience to spend.');
  purchases.forEach((x) => {
    const trait = String(x.trait || '').trim();
    const step = (label, base, mult) => {
      const id = `${x.kind}:${trait}`;
      const from = at[id] ?? base;
      const to = from + 1;
      at[id] = to;
      if (to > V5_XP_MAX_DOTS) errors.push(`${label} can't go above ${V5_XP_MAX_DOTS} dots.`);
      log.push({ kind: x.kind, trait, what: label, from, to, cost: to * mult });
    };
    if (x.kind === 'attribute' && ATTRIBUTE_LABELS[trait]) {
      step(ATTRIBUTE_LABELS[trait], int(s.attributes?.[trait]), V5_XP_COSTS.attribute);
    } else if (x.kind === 'skill' && V5_SKILL_LABELS[trait]) {
      step(V5_SKILL_LABELS[trait], creation[trait], V5_XP_COSTS.skill);
    } else if (x.kind === 'discipline' && discOk.includes(trait)) {
      const row = rows.find((r) => r.name === trait);
      step(trait, row ? row.base + row.predator : 0, disciplineXpMultiplier(s, trait));
    } else if (x.kind === 'specialty' && V5_SKILL_LABELS[x.skill]) {
      const label = V5_SKILL_LABELS[x.skill];
      if (!trait) errors.push(`Name the ${label} specialty.`);
      else if (trait.length > V5_NAME_MAX) errors.push(`Names are at most ${V5_NAME_MAX} characters.`);
      if (int(skillsNow[x.skill]) < 1) errors.push(`${label} needs at least one dot for a specialty.`);
      log.push({ kind: 'specialty', trait, skill: x.skill, what: `${label} specialty: ${trait}`, from: 0, to: 1, cost: V5_XP_COSTS.specialty });
    } else if (x.kind === 'ritual') {
      const level = int(x.level);
      if (!trait) errors.push('Name each ritual bought with XP.');
      else if (trait.length > V5_NAME_MAX) errors.push(`Names are at most ${V5_NAME_MAX} characters.`);
      if (level < 1 || level > V5_XP_MAX_DOTS) errors.push('Rituals are level 1 to 5.');
      else if (level > bs) errors.push(`A level ${level} ritual needs Blood Sorcery ${level} (you have ${bs}).`);
      log.push({ kind: 'ritual', trait, what: `Ritual: ${trait}`, from: 0, to: level, cost: level * V5_XP_COSTS.ritual });
    } else {
      errors.push('One XP purchase is not something this step can buy.');
    }
  });
  const spent = log.reduce((sum, e) => sum + e.cost, 0);
  if (spent > total && total) errors.push(`Starting experience overspent: ${spent} of ${total} XP.`);
  return { total, spent, unspent: Math.max(0, total - spent), log, errors };
}

export function validateV5Experience(sheet, allDisciplines) {
  return xpLedger(sheet, allDisciplines).errors[0] || null;
}

/** What one more purchase would cost, and the first problem it would cause (null if none). */
export function xpPreview(sheet, purchase, allDisciplines) {
  const before = xpLedger(sheet, allDisciplines);
  const after = xpLedger({ ...sheet, xpPurchases: [...(sheet?.xpPurchases || []), purchase] }, allDisciplines);
  const error = after.errors.find((e) => !before.errors.includes(e)) || null;
  return { cost: after.spent - before.spent, error };
}

/** The wod_meta.experience block, or null when the age gives no XP. */
export function experienceMeta(sheet) {
  const l = xpLedger(sheet);
  if (!l.total) return null;
  return { total: l.total, spent: l.spent, unspent: l.unspent, log: l.log };
}

const sumDots = (rows) => (rows || []).reduce((s, r) => s + int(r?.dots), 0);
const named = (rows) => (rows || []).filter((r) => r && String(r.name || '').trim());

export function predatorAdvantages(sheet) {
  const p = predatorInfo(sheet?.predatorType);
  if (!p) return { advantages: [], flaws: [] };
  return {
    advantages: (p.advantages || []).map((a) => ({ name: a.name, dots: a.dots, kind: 'predator' })),
    flaws: (p.flaws || []).map((f) => ({ name: f.name, dots: f.dots, kind: 'predator' })),
  };
}

// ---------- Whole sheet ----------

export function validateV5Sheet(sheet, allDisciplines) {
  const s = sheet || {};
  const err = {};
  const add = (id, msg) => {
    if (msg && !err[id]) err[id] = msg;
  };
  if (!String(s.name || '').trim()) add(V5_SECTION_IDS.identity, 'Character name is required.');

  if (!clanInfo(s.clan)) add(V5_SECTION_IDS.clan, 'Choose a clan.');
  const age = V5_AGE_BRACKETS[s.age];
  if (!age) add(V5_SECTION_IDS.clan, 'Choose an age.');
  else if (!age.generations.includes(int(s.generation))) {
    add(V5_SECTION_IDS.clan, `${age.label}s are generation ${age.generations[0]}–${age.generations[age.generations.length - 1]}.`);
  }
  const thinGen = int(s.generation) >= 14;
  if (s.clan === THIN_BLOOD && !thinGen) add(V5_SECTION_IDS.clan, 'Thin-bloods are 14th–16th generation.');
  if (s.clan && s.clan !== THIN_BLOOD && thinGen) {
    add(V5_SECTION_IDS.clan, '14th–16th generation vampires are thin-bloods.');
  }

  add(V5_SECTION_IDS.attributes, validateV5Attributes(s.attributes));
  add(V5_SECTION_IDS.skills, validateV5Skills(s.skills, s.skillDistribution));
  add(V5_SECTION_IDS.skills, validateV5Specialties(s.specialties, s.skills));
  add(V5_SECTION_IDS.disciplines, validateV5Disciplines(s.disciplines, s.clan, allDisciplines));

  // Predator type (thin-bloods may skip it)
  const p = predatorInfo(s.predatorType);
  if (!p && s.clan !== THIN_BLOOD) add(V5_SECTION_IDS.predator, 'Choose a predator type.');
  if (p) {
    if ((p.forbidden_clans || []).includes(s.clan)) {
      add(V5_SECTION_IDS.predator, `${s.clan} cannot take the ${p.name} predator type.`);
    }
    if (s.predatorSpecialty == null || p.specialty_choice[s.predatorSpecialty] == null) {
      add(V5_SECTION_IDS.predator, 'Pick the predator type specialty.');
    }
    if (s.clan !== THIN_BLOOD) {
      const opts = predatorDisciplineOptions(s.predatorType, s.clan);
      if (!opts.includes(s.predatorDiscipline)) {
        add(V5_SECTION_IDS.predator, 'Pick the predator type Discipline.');
      }
    }
    const d = deriveV5(s);
    if (p.max_blood_potency != null && d.blood_potency > p.max_blood_potency) {
      add(V5_SECTION_IDS.predator, `${p.name} needs Blood Potency ${p.max_blood_potency} or less.`);
    }
  }

  // Advantages & flaws (predator ones are extra; predator flaws count toward the minimum)
  const d = deriveV5(s);
  const advDots = sumDots(named(s.advantages));
  if (advDots > d.advantage_dots) {
    add(V5_SECTION_IDS.advantages, `Advantages: at most ${d.advantage_dots} dots (you have ${advDots}).`);
  }
  const flawDots = sumDots(named(s.flaws)) + sumDots(predatorAdvantages(s).flaws);
  if (flawDots < d.flaw_min_dots) {
    add(V5_SECTION_IDS.advantages, `Take at least ${d.flaw_min_dots} dots of Flaws (you have ${flawDots}).`);
  }
  if ([...named(s.advantages), ...named(s.flaws)].some((r) => int(r.dots) < 1 || int(r.dots) > 5)) {
    add(V5_SECTION_IDS.advantages, 'Each Advantage or Flaw is 1–5 dots.');
  }
  add(V5_SECTION_IDS.advantages, validateThinBloodMeritsFlaws(s));
  add(V5_SECTION_IDS.experience, validateV5Experience(s, allDisciplines));

  // Convictions & touchstones
  const conv = (s.convictions || []).filter(
    (c) => c && (String(c.conviction || '').trim() || String(c.touchstone || '').trim())
  );
  const [cMin, cMax] = V5_CONVICTIONS;
  if (conv.length < cMin || conv.length > cMax) {
    add(V5_SECTION_IDS.humanity, `Write ${cMin}–${cMax} Convictions, each with a Touchstone.`);
  } else if (conv.some((c) => !String(c.conviction || '').trim() || !String(c.touchstone || '').trim())) {
    add(V5_SECTION_IDS.humanity, 'Each Conviction needs a Touchstone (and vice versa).');
  }
  return err;
}

/** Body pieces for POST /api/characters/ (V5 storage shape). */
export function buildV5Payload(sheet) {
  const s = sheet || {};
  const d = deriveV5(s);
  const { skills, specialties } = finalSkills(s);
  const skillsPayload = {};
  V5_SKILL_CATEGORIES.forEach((cat) => {
    skillsPayload[cat] = Object.fromEntries(V5_SKILLS[cat].map(([k]) => [k, skills[k]]));
  });
  skillsPayload.specialties = specialties;
  skillsPayload.distribution = s.skillDistribution;

  const attributes = finalAttributes(s);
  const pred = predatorAdvantages(s);
  const advantages = [
    ...named(s.advantages).map((a) => ({
      name: String(a.name).trim(),
      dots: int(a.dots),
      kind: a.kind === 'background' ? 'background' : 'merit',
    })),
    ...pred.advantages,
  ];
  const flaws = [
    ...named(s.flaws).map((f) => ({ name: String(f.name).trim(), dots: int(f.dots), kind: 'flaw' })),
    ...pred.flaws,
  ];
  const touchstones = (s.convictions || [])
    .filter((c) => c && String(c.conviction || '').trim())
    .map((c) => ({ name: String(c.touchstone || '').trim(), conviction: String(c.conviction).trim() }));

  const wodMeta = {
    edition: 'v5',
    concept: String(s.concept || '').trim(),
    clan: s.clan,
    generation: int(s.generation),
    age: s.age,
    sire: String(s.sire || '').trim(),
    predator_type: s.predatorType || null,
    ambition: String(s.ambition || '').trim(),
    desire: String(s.desire || '').trim(),
    hunger: d.hunger,
    humanity: d.humanity,
    stains: 0,
    blood_potency: d.blood_potency,
    health: { max: d.health, superficial: 0, aggravated: 0 },
    willpower: { max: d.willpower, superficial: 0, aggravated: 0 },
    disciplines: finalDisciplines(s),
    touchstones,
    chronicle_tenets: String(s.chronicle_tenets || '').trim(),
    advantages,
    flaws,
  };
  const rituals = finalRituals(s);
  if (rituals.length) wodMeta.rituals = rituals;
  const experience = experienceMeta(s);
  if (experience) wodMeta.experience = experience;
  if (s.clan === THIN_BLOOD) {
    wodMeta.thin_blood_merits = namedList(s.thinBloodMerits).map((r) => String(r.name).trim());
    wodMeta.thin_blood_flaws = namedList(s.thinBloodFlaws).map((r) => String(r.name).trim());
  }

  const meritsFlaws = {
    entries: [
      ...advantages.map((a) => ({
        name: a.name,
        points: a.dots,
        note: a.kind === 'predator' ? 'predator type' : a.kind,
      })),
      ...flaws.map((f) => ({
        name: f.name,
        points: -f.dots,
        note: f.kind === 'predator' ? 'predator type' : 'flaw',
      })),
      ...(wodMeta.thin_blood_merits || []).map((n) => ({ name: n, points: 0, note: 'thin-blood merit' })),
      ...(wodMeta.thin_blood_flaws || []).map((n) => ({ name: n, points: 0, note: 'thin-blood flaw' })),
    ],
  };
  if (!meritsFlaws.entries.length) delete meritsFlaws.entries;

  return {
    system_type: 'vampire',
    attributes,
    skills: skillsPayload,
    merits_flaws: meritsFlaws,
    wod_meta: wodMeta,
  };
}
