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
 *   startingCeremony: string (one free Level 1 Oblivion ceremony whose prerequisite power is taken),
 *   predatorChoices: the player's picks among the predator type's grants (see resolvePredatorGrants),
 *   predatorDiscipline (name), extraPowers: {[discipline]: [power]} (powers for a predator/XP
 *   Discipline that isn't one of the two picks),
 *   advantages: [{id?, name, dots, kind: 'merit'|'background'|'loresheet', note?, custom?, levels?}]
 *   (catalog rows have the id; `custom` rows are free text for the Storyteller to approve; a
 *   loresheet row has the levels taken, its dots are their sum), flaws: [{id?, name, dots, note?, custom?}]
 *   (the clan's own Flaws, Caitiff Suspect, are added from the catalog: see clanFlaws),
 *   convictions: [{conviction, touchstone}],
 *   fledglingHumanity: bool (childer only: start at Humanity 8 instead of 7),
 *   thinBloodMerits: [{name, id?}], thinBloodFlaws: [{name, id?}] (thin-bloods: 1–3 each, equal counts),
 *   xpPurchases: starting experience (neonates 15, ancillae 35), one entry per dot, in order:
 *     {kind: 'attribute'|'skill', trait: key, specialty?: name (free one with a first dot in
 *     Academics/Craft/Performance/Science)} | {kind: 'discipline', trait: name}
 *     | {kind: 'specialty', skill: key, trait: name} | {kind: 'ritual', trait: name, level}
 * }
 */
import {
  BLOOD_SORCERY,
  OBLIVION,
  CAITIFF,
  THIN_BLOOD,
  V5_AGE_BRACKETS,
  V5_ADVANTAGE_DOTS,
  V5_ATTRIBUTE_KEYS,
  V5_ATTRIBUTE_SPREAD,
  V5_CONVICTIONS,
  V5_DISCIPLINE_DOTS,
  V5_FLAWS_MIN_DOTS,
  V5_FLEDGLING_HUMANITY,
  V5_FREE_SPECIALTY_SKILLS,
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
  V5_RITUALS_MAX,
  generationBloodPotency,
} from './constants';
import {
  advantageEntries,
  disciplineNames,
  findAdvantage,
  findLoresheet,
  getV5Rules,
  loresheetEntries,
  powersOf,
  ritualsOf,
} from './rulesData';
import { CREATION_AGES } from './creationSettings';

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

const specialtyKey = (skill, name) => `${skill}:${String(name || '').trim().toLowerCase()}`;

/** First specialty that repeats on the same skill (case-insensitive), as an error message. */
export function duplicateSpecialtyError(specialties) {
  const seen = new Set();
  for (const sp of specialties || []) {
    if (!sp || !sp.skill || !String(sp.name || '').trim()) continue;
    const key = specialtyKey(sp.skill, sp.name);
    if (seen.has(key)) {
      return `${V5_SKILL_LABELS[sp.skill] || sp.skill} already has the ${String(sp.name).trim()} specialty.`;
    }
    seen.add(key);
  }
  return null;
}

// ---------- Clan & disciplines ----------

export function clanInfo(clan) {
  return getV5Rules().clans.find((c) => c.name === clan) || null;
}

/** Disciplines a clan may take at creation ('any' for Caitiff, none for thin-bloods). */
export function creationDisciplineOptions(clan, allDisciplines = disciplineNames()) {
  if (clan === THIN_BLOOD) return [];
  if (clan === CAITIFF) return allDisciplines.filter((d) => d !== 'Thin-Blood Alchemy');
  return clanInfo(clan)?.disciplines || [];
}

export function validateV5Disciplines(disciplines, clan, allDisciplines = disciplineNames()) {
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
  return getV5Rules().predators.find((p) => p.name === name) || null;
}

/** Discipline options of a predator type for this clan (drops "Tremere only" for others). */
export function predatorDisciplineOptions(predatorType, clan) {
  const p = predatorInfo(predatorType);
  if (!p) return [];
  return p.disciplines.filter((d) => !d.clans || d.clans.includes(clan)).map((d) => d.name);
}

/** "Skill (Name)" labels of a predator type's specialty options. */
export function predatorSpecialtyLabels(p) {
  return (p?.specialties || []).map((s) => `${V5_SKILL_LABELS[s.skill] || s.skill} (${s.name})`);
}

const KIND_WORD = { background: 'Background', merit: 'Merit', flaw: 'Flaw' };

/**
 * The catalog entries a predator grant option that stands for a whole group ("any Mythic Flaw")
 * lets this sheet pick from; empty for an ordinary option or without the catalog's advantages.
 */
export function predatorGroupOptions(sheet, option) {
  if (!option?.group) return [];
  return advantageOptions(sheet?.clan, option.kind).filter((a) => a.group === option.group);
}

/**
 * The advantages and flaws a predator type grants, after the player's choices.
 * sheet.predatorChoices: { 'a0': optionIndex } for "one of", { 'a1': { [optionIndex]: dots } } for
 * a split of dots, { 'f0:dots': n } where the book prints no rating for an option, and
 * { 'f0:1:pick': id } for the entry chosen for an option that stands for a group.
 * Returns { advantages, flaws, problems }: rows {id, name, dots, kind: 'predator', note}. A group
 * pick is stored as "Mythic: Folkloric Bane" with the chosen entry's id (the group name kept so a
 * reader that only knows the grant still recognises it).
 */
export function resolvePredatorGrants(sheet) {
  const p = predatorInfo(sheet?.predatorType);
  const out = { advantages: [], flaws: [], problems: [] };
  if (!p) return out;
  const choices = sheet?.predatorChoices || {};
  const label = (o) => (o.note ? `${o.name} (${o.note})` : o.name);
  const row = (o, dots, key, oi) => {
    const options = predatorGroupOptions(sheet, o);
    if (options.length) {
      const picked = options.find((a) => a.id === choices[`${key}:${oi}:pick`]);
      if (picked) return { id: picked.id, name: `${o.group}: ${picked.name}`, dots, kind: 'predator' };
      out.problems.push(`${p.name}: choose which ${o.group} ${KIND_WORD[o.kind] || o.kind}.`);
    }
    return {
      ...(o.id ? { id: o.id } : {}),
      name: label(o),
      dots,
      kind: 'predator',
      ...(o.note ? { note: o.note } : {}),
    };
  };
  const walk = (grants, prefix, list) =>
    grants.forEach((g, gi) => {
      const key = `${prefix}${gi}`;
      const dotsOf = (o, oi) => {
        if (o.dots != null) return o.dots;
        const n = int(choices[`${key}:${oi}:dots`]);
        if (n < 1 || n > 5) out.problems.push(`${p.name}: choose the dots for ${o.name} (ask your Storyteller; the book prints none).`);
        return n;
      };
      if (g.pick === 'one_of') {
        const oi = choices[key];
        const o = g.options[oi];
        if (!o) out.problems.push(`${p.name}: choose one of ${g.options.map((x) => x.name).join(' or ')}.`);
        else list.push(row(o, dotsOf(o, oi), key, oi));
      } else if (g.pick === 'split') {
        const split = choices[key] || {};
        let total = 0;
        g.options.forEach((o, oi) => {
          const n = int(split[oi]);
          total += n;
          if (n > 0) list.push(row(o, n, key, oi));
        });
        if (total !== g.dots_total) {
          out.problems.push(`${p.name}: share ${g.dots_total} dots between ${g.options.map((x) => x.name).join(' and ')} (you have ${total}).`);
        }
      } else {
        g.options.forEach((o, oi) => list.push(row(o, dotsOf(o, oi), key, oi)));
      }
    });
  walk(p.advantages, 'a', out.advantages);
  walk(p.flaws, 'f', out.flaws);
  return out;
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
  const seen = new Set();
  for (const r of [...namedList(sheet.thinBloodMerits), ...namedList(sheet.thinBloodFlaws)]) {
    const key = String(r.name).trim().toLowerCase();
    if (seen.has(key)) return `${String(r.name).trim()} can be taken only once.`;
    seen.add(key);
  }
  // Pairs the book rules out (core p. 183: Dead Flesh and Lifelike, Mortal Frailty and Vampiric
  // Resilience, Shunned by the Anarchs and Anarch Comrades), from the catalog's `excludes`.
  return exclusionError([
    ...namedList(sheet.thinBloodMerits).map((r) => findAdvantage(r, 'merit', 'thin_blood')),
    ...namedList(sheet.thinBloodFlaws).map((r) => findAdvantage(r, 'flaw', 'thin_blood')),
  ]);
}

/** "A and B can't be taken together." for the first pair of entries one of which excludes the other. */
export function exclusionError(entries) {
  const list = (entries || []).filter(Boolean);
  for (const e of list) {
    const other = list.find((x) => x !== e && ((e.excludes || []).includes(x.id) || (x.excludes || []).includes(e.id)));
    if (other) return `${e.name} and ${other.name} can't be taken together.`;
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
    if (!(x.trait in skills)) return;
    // A first dot in Academics/Craft/Performance/Science brings its free specialty.
    const free = String(x.specialty || '').trim();
    if (skills[x.trait] === 0 && V5_FREE_SPECIALTY_SKILLS.includes(x.trait) && free) {
      specialties.push({ skill: x.trait, name: free });
    }
    skills[x.trait] += 1;
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
  if (p && idx != null && p.specialties[idx] != null) {
    const ps = p.specialties[idx];
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

/** Final Oblivion rating (picks + predator dot + XP dots). */
export function oblivionLevel(sheet) {
  return disciplineRows(sheet).find((r) => r.name === OBLIVION)?.level || 0;
}

/**
 * Level 1 Oblivion ceremonies the sheet may take for free at creation: one whose prerequisite
 * Oblivion power the character has (Players Guide p. 91). Empty without the catalog.
 */
export function startingCeremonyOptions(sheet) {
  if (oblivionLevel(sheet) < 1) return [];
  const powers = disciplineRows(sheet).find((r) => r.name === OBLIVION)?.powers || [];
  return ritualsOf('ceremony', 1).filter((c) => (c.prerequisite || []).every((g) => g.some((pre) => powers.includes(pre))));
}

// ---------- Discipline powers (catalog) ----------

/**
 * First problem with the chosen powers, or null: each must be a power of that Discipline at or
 * below its final rating, its amalgam Discipline at the printed level, its prerequisite power
 * taken, and no power twice. Disciplines the catalog has no powers for are free text (unchecked).
 */
export function validateV5Powers(sheet) {
  const rows = disciplineRows(sheet).filter((r) => r.name);
  const level = Object.fromEntries(rows.map((r) => [r.name, r.level]));
  // A prerequisite may sit in another Discipline (Messenger's Command: Animal Messenger + Compel or Mesmerize).
  const allChosen = rows.flatMap((r) => r.powers.map((x) => String(x || '').trim()).filter(Boolean));
  for (const r of rows) {
    const list = powersOf(r.name);
    if (!list.length) continue;
    const chosen = r.powers.map((x) => String(x || '').trim()).filter(Boolean);
    const seen = new Set();
    for (const name of chosen) {
      if (seen.has(name)) return `${r.name}: ${name} is taken twice.`;
      seen.add(name);
      const pw = list.find((x) => x.name === name || (x.aliases || []).includes(name));
      if (!pw) return `${name} is not a ${r.name} power.`;
      if (pw.level > r.level) return `${name} is a level ${pw.level} power; ${r.name} is at ${r.level}.`;
      if (pw.amalgam && (level[pw.amalgam.discipline] || 0) < pw.amalgam.level) {
        return `${name} also needs ${pw.amalgam.discipline} ${pw.amalgam.level}.`;
      }
      const missing = (pw.prerequisite || []).find((g) => !g.some((pre) => allChosen.includes(pre)));
      if (missing) return `${name} needs ${missing.join(' or ')} first.`;
    }
  }
  return null;
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
  const ceremony = String(sheet?.startingCeremony || '').trim();
  if (ceremony && startingCeremonyOptions(sheet).some((c) => c.name === ceremony)) {
    out.push({ name: ceremony, level: 1, source: 'creation', kind: 'ceremony' });
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
 * { kind, trait, what, from, to, cost, purchase } (specialty: from 0 to 1; ritual: from 0 to its
 * level; a skill's first dot in Academics/Craft/Performance/Science also has `specialty`).
 * `purchase` is the index in sheet.xpPurchases (the forge removes by it; not saved).
 */
export function xpLedger(sheet, allDisciplines = disciplineNames()) {
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
  const specialtiesSeen = creationSkills(s).specialties.map((sp) => specialtyKey(sp.skill, sp.name));
  const nameOk = (name) => {
    if (name.length > V5_NAME_MAX) errors.push(`Names are at most ${V5_NAME_MAX} characters.`);
  };
  const newSpecialty = (skill, name) => {
    const key = specialtyKey(skill, name);
    if (specialtiesSeen.includes(key)) errors.push(`${V5_SKILL_LABELS[skill]} already has the ${name} specialty.`);
    specialtiesSeen.push(key);
  };

  if (purchases.length && !total) errors.push('This age has no starting experience to spend.');
  (s.xpPurchases || []).forEach((x, purchase) => {
    if (!x) return;
    const trait = String(x.trait || '').trim();
    const add = (entry) => log.push({ ...entry, purchase });
    const step = (label, base, mult, extra) => {
      const id = `${x.kind}:${trait}`;
      const from = at[id] ?? base;
      const to = from + 1;
      at[id] = to;
      if (to > V5_XP_MAX_DOTS) errors.push(`${label} can't go above ${V5_XP_MAX_DOTS} dots.`);
      add({ kind: x.kind, trait, what: label, from, to, cost: to * mult, ...(extra ? extra(from) : {}) });
    };
    if (x.kind === 'attribute' && ATTRIBUTE_LABELS[trait]) {
      step(ATTRIBUTE_LABELS[trait], int(s.attributes?.[trait]), V5_XP_COSTS.attribute);
    } else if (x.kind === 'skill' && V5_SKILL_LABELS[trait]) {
      const label = V5_SKILL_LABELS[trait];
      step(label, creation[trait], V5_XP_COSTS.skill, (from) => {
        if (from !== 0 || !V5_FREE_SPECIALTY_SKILLS.includes(trait)) return null;
        const free = String(x.specialty || '').trim();
        if (!free) {
          errors.push(`${label} comes with a free specialty — name it.`);
          return null;
        }
        nameOk(free);
        newSpecialty(trait, free);
        return { specialty: free };
      });
    } else if (x.kind === 'discipline' && discOk.includes(trait)) {
      const row = rows.find((r) => r.name === trait);
      step(trait, row ? row.base + row.predator : 0, disciplineXpMultiplier(s, trait));
    } else if (x.kind === 'specialty' && V5_SKILL_LABELS[x.skill]) {
      const label = V5_SKILL_LABELS[x.skill];
      if (!trait) errors.push(`Name the ${label} specialty.`);
      else {
        nameOk(trait);
        newSpecialty(x.skill, trait);
      }
      if (int(skillsNow[x.skill]) < 1) errors.push(`${label} needs at least one dot for a specialty.`);
      add({ kind: 'specialty', trait, skill: x.skill, what: `${label} specialty: ${trait}`, from: 0, to: 1, cost: V5_XP_COSTS.specialty });
    } else if (x.kind === 'ritual') {
      const level = int(x.level);
      if (!trait) errors.push('Name each ritual bought with XP.');
      else nameOk(trait);
      if (level < 1 || level > V5_XP_MAX_DOTS) errors.push('Rituals are level 1 to 5.');
      else if (level > bs) errors.push(`A level ${level} ritual needs Blood Sorcery ${level} (you have ${bs}).`);
      // A catalog ritual costs its printed level (the server re-prices it the same way).
      const known = ritualsOf('ritual').find((r) => r.name === trait);
      if (known && known.level !== level) errors.push(`${trait} is a level ${known.level} ritual.`);
      add({ kind: 'ritual', trait, what: `Ritual: ${trait}`, from: 0, to: level, cost: level * V5_XP_COSTS.ritual });
    } else {
      errors.push('One XP purchase is not something this step can buy.');
    }
  });
  const rituals = finalRituals(s).length;
  if (rituals > V5_RITUALS_MAX) errors.push(`At most ${V5_RITUALS_MAX} rituals (you have ${rituals}).`);
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
  // Count each message, so a second copy of an existing problem still shows.
  const counts = (list) => list.reduce((m, e) => m.set(e, (m.get(e) || 0) + 1), new Map());
  const had = counts(before.errors);
  const now = counts(after.errors);
  const error = after.errors.find((e) => now.get(e) > (had.get(e) || 0)) || null;
  return { cost: after.spent - before.spent, error };
}

/** The wod_meta.experience block, or null when the age gives no XP. */
export function experienceMeta(sheet) {
  const l = xpLedger(sheet);
  if (!l.total) return null;
  return { total: l.total, spent: l.spent, unspent: l.unspent, log: l.log.map(({ purchase, ...e }) => e) };
}

const sumDots = (rows) => (rows || []).reduce((s, r) => s + int(r?.dots), 0);
const named = (rows) => (rows || []).filter((r) => r && String(r.name || '').trim());

export function predatorAdvantages(sheet) {
  const { advantages, flaws } = resolvePredatorGrants(sheet);
  return { advantages, flaws };
}

/** "Allies (police)" → "allies": a row's name without its note, for matching. */
const bareName = (name) => String(name || '').replace(/\s*\([^)]*\)\s*$/, '').trim().toLowerCase();

/**
 * Flaws the clan starts with, from the catalog clan's creation rules (Caitiff: Suspect •, core
 * p. 107), unless the player already listed them. The book doesn't say they are extra the way the
 * predator type's are (p. 136), so they count as the player's own:
 * [{ id, name, dots, kind: 'flaw', source: 'clan' }].
 */
export function clanFlaws(sheet) {
  const own = named(sheet?.flaws);
  const listed = (f) => own.some((r) => (r.id ? r.id === f.id : bareName(r.name) === bareName(f.name)));
  return (clanInfo(sheet?.clan)?.creation?.flaws || [])
    .filter((f) => !listed(f))
    .map((f) => ({ id: f.id, name: f.name, dots: f.dots, kind: 'flaw', source: 'clan' }));
}

/** The player's own Flaw dots, the clan's included (the predator type's flaws don't count toward the minimum). */
export function ownFlawDots(sheet) {
  return sumDots(named(sheet?.flaws)) + sumDots(clanFlaws(sheet));
}

// ---------- Advantages, Flaws and loresheets from the catalog ----------

/** Ratings printed "•+" go up to this at creation. */
const OPEN_MAX_DOTS = 5;

/** The dot values a catalog entry may take: its allowed list, else min..max ([] for none). */
export function advantageDotChoices(entry) {
  const d = entry?.dots;
  if (!d) return [];
  if (Array.isArray(d.allowed)) return [...d.allowed].map(int).sort((a, b) => a - b);
  const lo = Math.max(1, int(d.min) || 1);
  const hi = d.max == null ? Math.max(lo, OPEN_MAX_DOTS) : int(d.max);
  return Array.from({ length: Math.max(0, hi - lo + 1) }, (_, i) => lo + i);
}

/** [1,2,3,4,5,6] → "1–6", [2,3] → "2 or 3", [3] → "3", [1,3,5] → "1, 3 or 5". */
export function dotChoicesText(choices) {
  const c = choices || [];
  if (c.length <= 1) return String(c[0] ?? '');
  const contiguous = c.every((v, i) => !i || v === c[i - 1] + 1);
  if (contiguous && c.length > 2) return `${c[0]}–${c[c.length - 1]}`;
  return `${c.slice(0, -1).join(', ')} or ${c[c.length - 1]}`;
}

/**
 * May a character of this clan take this catalog Merit/Background/Flaw at creation? Ghoul and
 * coterie entries never (not character Advantages); Caitiff and thin-blood ones only for those;
 * clans_only and cannot_buy_for as printed; a clan whose creation rules forbid positive Status
 * (Caitiff, core p. 107) can't buy the Status Background.
 */
export function advantageAllowed(entry, clan) {
  if (!entry) return true;
  const c = clanInfo(clan);
  if (entry.ghoul_only || entry.coterie) return false;
  if (entry.caitiff && !(clan === CAITIFF || c?.caitiff)) return false;
  if (entry.thin_blood && !(clan === THIN_BLOOD || c?.thin_blood)) return false;
  if (entry.clans_only && !entry.clans_only.includes(clan)) return false;
  if ((entry.cannot_buy_for || []).includes(clan)) return false;
  if (c?.creation?.no_positive_status && entry.kind === 'background' && entry.group === 'Status') return false;
  return true;
}

/**
 * Catalog entries a section offers ('background' | 'merit' | 'flaw') to this clan. Thin-blood
 * Merits/Flaws have their own lists; the Loresheets Background is the Loresheets section.
 */
export function advantageOptions(clan, kind) {
  return advantageEntries().filter(
    (a) => a.kind === kind && !a.thin_blood && a.group !== 'Loresheets' && advantageAllowed(a, clan)
  );
}

/** Thin-blood Merits ('merit') or Flaws ('flaw') from the catalog. */
export function thinBloodOptions(kind) {
  return advantageEntries().filter((a) => a.thin_blood && a.kind === kind);
}

/** May the sheet take this loresheet (clan, thin-blood or Discipline restriction)? */
export function loresheetAllowed(ls, sheet) {
  if (!ls) return true;
  const clan = sheet?.clan;
  if (ls.clans_only && !ls.clans_only.includes(clan)) return false;
  if (ls.thin_blood_only && clan !== THIN_BLOOD) return false;
  if (ls.disciplines_only) {
    const have = finalDisciplines(sheet).map((d) => d.name);
    if (!ls.disciplines_only.some((d) => have.includes(d))) return false;
  }
  return true;
}

export function loresheetOptions(sheet) {
  return loresheetEntries().filter((l) => loresheetAllowed(l, sheet));
}

/** "Haven ••" or "more than one dot: Haven ••": another Background at that rating. */
const DOT_REQUIREMENT = /^(more than one dot:\s*)?([A-Za-z][\w' -]*?)\s+(•+)\+?$/;

/** { name, dots, onlyAbove1 } for a requirement the forge can check, else null (shown as a hint only). */
export function dotRequirement(entry) {
  const m = String(entry?.requires || '').trim().match(DOT_REQUIREMENT);
  return m ? { name: m[2], dots: m[3].length, onlyAbove1: Boolean(m[1]) } : null;
}

/**
 * First problem with the catalog rows of Advantages, Flaws and loresheets, or null: not open to
 * the clan, dots outside the printed rating, taken more often than allowed, a Background another
 * entry needs, a loresheet without a level. Free-text and custom rows are left to the Storyteller.
 */
export function validateV5AdvantageRows(sheet) {
  const s = sheet || {};
  const own = [...named(s.advantages).map((r) => [r, false]), ...named(s.flaws).map((r) => [r, true])];
  const pred = resolvePredatorGrants(s);
  // every row with its catalog entry, the clan's and the predator type's included
  const withEntry = [
    ...clanFlaws(s).map((r) => [r, true]),
    ...own,
    ...pred.advantages.map((r) => [r, false]),
    ...pred.flaws.map((r) => [r, true]),
  ].map(([r, flaw]) => [r, r.kind === 'loresheet' ? findLoresheet(r) : r.custom ? null : findAdvantage(r, flaw ? 'flaw' : r.kind), flaw]);
  const counts = {};
  withEntry.forEach(([, e]) => {
    if (e) counts[e.id] = (counts[e.id] || 0) + 1;
  });
  const bare = (r, e) => (e ? e.name.toLowerCase() : bareName(r.name));
  // A Background's rating for a requirement: the predator type's rows of it (Trapdoor's Haven) plus
  // the dots bought on top of them; the player's own separate rows (two havens) are not added up,
  // the highest counts.
  const backgroundDots = (name) => {
    const rows = withEntry.filter(([r, e, flaw]) => !flaw && r.kind !== 'loresheet' && bare(r, e) === name.toLowerCase());
    const pred = rows.filter(([r]) => r.kind === 'predator').reduce((sum, [r]) => sum + int(r.dots), 0);
    return pred + Math.max(0, ...rows.filter(([r]) => r.kind !== 'predator').map(([r]) => int(r.dots)));
  };
  const ownIds = new Set(own.map(([r]) => r));
  for (const [r, e] of withEntry) {
    if (!e || !ownIds.has(r)) continue;
    if (r.kind === 'loresheet') {
      if (!(r.levels || []).length) return `Pick at least one level of ${e.name}.`;
      if (!loresheetAllowed(e, s)) return `${s.clan} can't take ${e.name} at creation.`;
      if (counts[e.id] > 1) return `${e.name} can be taken only once.`;
      continue;
    }
    if (!advantageAllowed(e, s.clan)) return `${s.clan} can't take ${e.name} at creation.`;
    const choices = advantageDotChoices(e);
    if (choices.length && !choices.includes(int(r.dots))) {
      return `${e.name} takes ${dotChoicesText(choices)} dots (you have ${int(r.dots)}).`;
    }
    if (!e.repeatable && counts[e.id] > 1) return `${e.name} can be taken only once.`;
    if (e.repeatable && e.max_instances && counts[e.id] > e.max_instances) {
      return `${e.name} can be taken at most ${e.max_instances} times.`;
    }
    const req = dotRequirement(e);
    if (req && (!req.onlyAbove1 || int(r.dots) > 1) && backgroundDots(req.name) < req.dots) {
      return `${e.name} needs ${req.name} at ${req.dots} dots or more.`;
    }
    // Archaic and Living in the Past (core p. 180); the forge's oldest age is ancilla
    if (/^ancilla or older$/i.test(String(e.requires || '').trim()) && s.age !== 'ancilla') {
      return `${e.name} is only for ancillae or older.`;
    }
  }
  return exclusionError(withEntry.filter(([, e]) => e && e.excludes).map(([, e]) => e));
}

// ---------- Chronicle creation settings (set by the Storyteller) ----------

const allowedName = (list, value) =>
  !list || !value || list.some((x) => x.toLowerCase() === String(value).toLowerCase());

/** Is this clan / predator type / age allowed by the chronicle's settings (null settings: all)? */
export function clanAllowed(settings, clan) {
  return allowedName(settings?.allowed_clans, clan);
}
export function predatorAllowed(settings, name) {
  return allowedName(settings?.allowed_predators, name);
}
export function ageAllowed(settings, age) {
  return allowedName(settings?.allowed_ages, age);
}

/** The age the forge starts a character at: neonate where allowed, else the first allowed age. */
export function defaultCreationAge(settings) {
  if (ageAllowed(settings, 'neonate')) return 'neonate';
  return CREATION_AGES.find((a) => ageAllowed(settings, a)) || 'neonate';
}

/** What the sheet breaks in the chronicle's creation settings: { sectionId: message }. */
export function settingsErrors(sheet, settings) {
  const s = sheet || {};
  const err = {};
  if (!settings) return err;
  if (s.clan && !clanAllowed(settings, s.clan)) {
    err[V5_SECTION_IDS.clan] = `The Storyteller doesn't allow ${s.clan} in this chronicle.`;
  }
  if (s.predatorType && !predatorAllowed(settings, s.predatorType)) {
    err[V5_SECTION_IDS.predator] = `The Storyteller doesn't allow the ${s.predatorType} predator type in this chronicle.`;
  }
  if (s.age && !ageAllowed(settings, s.age)) {
    err[V5_SECTION_IDS.age] = `The Storyteller doesn't allow ${V5_AGE_BRACKETS[s.age]?.label || s.age} characters in this chronicle.`;
  }
  const cap = settings.flaws_max_dots;
  const own = ownFlawDots(s);
  if (cap != null && own > cap) {
    err[V5_SECTION_IDS.advantages] = `This chronicle allows at most ${cap} dots of Flaws of your own (you have ${own}).`;
  }
  if (s.fledglingHumanity && settings.fledgling_humanity_8 === false) {
    err[V5_SECTION_IDS.humanity] = "The Storyteller doesn't offer the Humanity 8 fledgling start in this chronicle.";
  }
  return err;
}

// ---------- Whole sheet ----------

export function validateV5Sheet(sheet, allDisciplines = disciplineNames(), settings) {
  const s = sheet || {};
  const err = {};
  const add = (id, msg) => {
    if (msg && !err[id]) err[id] = msg;
  };
  if (!String(s.name || '').trim()) add(V5_SECTION_IDS.identity, 'Character name is required.');

  if (!clanInfo(s.clan)) add(V5_SECTION_IDS.clan, 'Choose a clan.');
  const age = V5_AGE_BRACKETS[s.age];
  if (!age) add(V5_SECTION_IDS.age, 'Choose an age.');
  else if (!age.generations.includes(int(s.generation))) {
    add(V5_SECTION_IDS.age, `${age.label}s are generation ${age.generations[0]}–${age.generations[age.generations.length - 1]}.`);
  }
  const thinGen = int(s.generation) >= 14;
  if (s.clan === THIN_BLOOD && !thinGen) add(V5_SECTION_IDS.age, 'Thin-bloods are 14th–16th generation.');
  if (s.clan && s.clan !== THIN_BLOOD && thinGen) {
    add(V5_SECTION_IDS.age, '14th–16th generation vampires are thin-bloods.');
  }

  add(V5_SECTION_IDS.attributes, validateV5Attributes(s.attributes));
  add(V5_SECTION_IDS.skills, validateV5Skills(s.skills, s.skillDistribution));
  add(V5_SECTION_IDS.skills, validateV5Specialties(s.specialties, s.skills));
  add(V5_SECTION_IDS.skills, duplicateSpecialtyError(creationSkills(s).specialties));
  add(V5_SECTION_IDS.disciplines, validateV5Disciplines(s.disciplines, s.clan, allDisciplines));
  add(V5_SECTION_IDS.disciplines, validateV5Powers(s));

  // Predator type (thin-bloods may skip it)
  const p = predatorInfo(s.predatorType);
  if (!p && s.clan !== THIN_BLOOD) add(V5_SECTION_IDS.predator, 'Choose a predator type.');
  if (p) {
    if ((p.forbidden_clans || []).includes(s.clan)) {
      add(V5_SECTION_IDS.predator, `${s.clan} cannot take the ${p.name} predator type.`);
    }
    if (s.predatorSpecialty == null || p.specialties[s.predatorSpecialty] == null) {
      add(V5_SECTION_IDS.predator, 'Pick the predator type specialty.');
    }
    resolvePredatorGrants(s).problems.forEach((msg) => add(V5_SECTION_IDS.predator, msg));
    if (p.ancilla_only && s.age !== 'ancilla') {
      add(V5_SECTION_IDS.predator, `${p.name} is for ancillae only.`);
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

  // Advantages & flaws. The predator type's advantages and flaws are extra: the 7 dots and the
  // 2 Flaw dots are the player's own (core p. 136: "in addition to the ones gained from your
  // Predator type").
  const d = deriveV5(s);
  const advDots = sumDots(named(s.advantages));
  if (advDots > d.advantage_dots) {
    add(V5_SECTION_IDS.advantages, `Advantages: at most ${d.advantage_dots} dots (you have ${advDots}).`);
  }
  const flawDots = ownFlawDots(s);
  if (flawDots < d.flaw_min_dots) {
    add(V5_SECTION_IDS.advantages, `Take at least ${d.flaw_min_dots} dots of Flaws (you have ${flawDots}).`);
  }
  add(V5_SECTION_IDS.advantages, validateV5AdvantageRows(s));
  // Rows the catalog doesn't know (custom ones, or any row without the catalog): 1–5 dots. Rows it
  // knows, by id or by name, are held to their printed rating above (Allies goes to 6), as on the
  // server (backend/services/v5_chargen.py); a loresheet's dots are the levels it takes.
  const unknownRow = (r, kind) => r.custom || !findAdvantage(r, kind);
  const freeRows = [
    ...named(s.advantages).filter((r) => r.kind !== 'loresheet' && unknownRow(r, r.kind)),
    ...named(s.flaws).filter((r) => unknownRow(r, 'flaw')),
  ];
  if (freeRows.some((r) => int(r.dots) < 1 || int(r.dots) > 5)) {
    add(V5_SECTION_IDS.advantages, 'Each Advantage or Flaw is 1–5 dots.');
  }
  add(V5_SECTION_IDS.advantages, validateThinBloodMeritsFlaws(s));
  add(V5_SECTION_IDS.experience, validateV5Experience(s, allDisciplines));
  Object.entries(settingsErrors(s, settings)).forEach(([id, msg]) => add(id, msg));

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
  // Rows keep the English name (with the note in brackets, as the predator rows do), plus the
  // catalog id, the note, `custom` for free-text rows on a catalog sheet, and a loresheet's levels.
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
  const advantages = [...named(s.advantages).map((a) => ownRow(a, advKind(a.kind))), ...pred.advantages];
  const flaws = [...clanFlaws(s), ...named(s.flaws).map((f) => ownRow(f, 'flaw')), ...pred.flaws];
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
    // Which forge rules built the sheet (Forge v2: predator flaws extra, chronicle creation rules).
    forge: { version: 2, settings_v: 1 },
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
        note: f.kind === 'predator' ? 'predator type' : f.source === 'clan' ? 'clan flaw' : 'flaw',
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
