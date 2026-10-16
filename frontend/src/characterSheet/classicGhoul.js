/**
 * Classic (Revised) ghouls: the rules of the Classic ghoul forge, pure (no React).
 * Source: docs/rules/CLASSIC_REVISED.md §7 via src/rules/classic.json "ghoul" (Ghouls: Fatal
 * Addiction, the book Revised p. 276 points to). The server checks the bounds only
 * (backend/services/classic_ghoul.py), as for Classic vampires; the budgets live here.
 *
 * - Attributes 6 / 4 / 3 on top of the free dot, Abilities 11 / 7 / 4 (none above 3 before freebies).
 * - Potence 1 (every ghoul) + one dot in one other Discipline: a vassal's from its domitor's (or the
 *   instinctive Celerity / Fortitude), an independent's any; Protean and Thaumaturgy only for vassals
 *   of Gangrel / Tremere. No Discipline above what the domitor's generation allows.
 * - Backgrounds 5 (no Generation, Herd or Status; the Domitor Background), Virtues 1 free each + 7,
 *   Humanity = Conscience + Self-Control, Willpower = Courage.
 * - 21 freebie points (+ up to 7 from Flaws); a Discipline dot costs 10.
 * - A Blood Pool: max 10, 1 point per turn; the starting vitae is a roll of 1d10 (an independent
 *   halves it, rounding up; a vassal may reroll a 1, at the Storyteller's option).
 * - A Blood Bond to the domitor in drinks (0–3: the third binds).
 *
 * Messages are English (tests assert them); the forge shows them through translateSheetError().
 */
import { CLASSIC_GHOUL } from '../rules/classicRules';
import { DISCIPLINE_PRESETS, KNOWLEDGES, SHEET_SECTION_IDS, SKILLS, TALENTS } from './constants';
import { buildMeritsFlawsPayload } from './meritsFlaws';
import { canBeDomitor } from './v5/ghoul';
import {
  abilityPools,
  attributePools,
  computeClassicFreebies,
  deriveClassicMorality,
  finalVirtues,
  validateAbilitySpread,
  validateAttributeSpread,
  validateFreebies,
  validateVirtues,
} from './validation';

const int = (v) => {
  const n = parseInt(v, 10);
  return Number.isFinite(n) ? n : 0;
};
const C = CLASSIC_GHOUL.creation;

export const GHOUL_KINDS = CLASSIC_GHOUL.kinds; // vassal, independent, revenant
export const FORGE_KINDS = CLASSIC_GHOUL.kinds_in_forge; // vassal, independent
export const GHOUL_ATTRIBUTE_PRIORITIES = C.attributes.priorities; // [6, 4, 3]
export const GHOUL_ABILITY_PRIORITIES = C.abilities.priorities; // [11, 7, 4]
export const GHOUL_DISCIPLINE_DOTS = C.disciplines.creation_dots; // 2: Potence 1 + one other
export const GHOUL_BACKGROUND_DOTS = C.backgrounds.dots; // 5
export const GHOUL_NOT_ALLOWED_BACKGROUNDS = C.backgrounds.not_allowed; // Generation, Herd, Status
export const INSTINCTIVE_DISCIPLINES = C.disciplines.instinctive; // Potence, Fortitude, Celerity
export const CLAN_ONLY_DISCIPLINES = C.disciplines.only_for_clan; // {Protean: Gangrel, Thaumaturgy: Tremere}
export const BLOOD_POOL_MAX = CLASSIC_GHOUL.blood_pool.max; // 10
export const BLOOD_POOL_PER_TURN = CLASSIC_GHOUL.blood_pool.per_turn; // 1
export const BOND_DRINKS = CLASSIC_GHOUL.blood_bond.drinks_to_bind; // 3
export const BOND_START = C.blood_bond_start; // {vassal: 3, independent: 0}

/**
 * Text caps, the server's (backend/services/classic_ghoul.py): [sheet key, English name in the
 * messages (i18nErrors translates it), max length, forge section, the server's problem label].
 */
export const CLASSIC_GHOUL_TEXT_FIELDS = [
  ['concept', 'Concept', 200, 'identity', 'wod_meta.concept'],
  ['nature', 'Nature', 200, 'identity', 'wod_meta.nature'],
  ['demeanor', 'Demeanor', 200, 'identity', 'wod_meta.demeanor'],
  ['duties', 'Duties', 200, 'identity', 'wod_meta.ghoul.duties'],
  ['ghouledSince', 'Ghoul since', 200, 'identity', 'wod_meta.ghoul.ghouled_since'],
  ['bondNote', 'Bond note', 500, 'bond', 'wod_meta.ghoul.bond.note'],
  ['feedingLast', 'Last fed', 60, 'bond', 'wod_meta.ghoul.feeding.last'],
  ['feedingNote', 'Feeding note', 500, 'bond', 'wod_meta.ghoul.feeding.note'],
  ['overdosing', 'Overdosing', 120, 'bond', 'wod_meta.ghoul.overdosing'],
];
/** sheet key -> max length (the forge's maxLength). */
export const CLASSIC_GHOUL_TEXT_MAX = Object.fromEntries(CLASSIC_GHOUL_TEXT_FIELDS.map(([k, , n]) => [k, n]));
/** A Discipline's or Background's name (the server's rows). */
export const CLASSIC_GHOUL_ROW_NAME_MAX = 60;

/** The forge's sections (the Classic wizard's ids, plus Blood Bond & feeding). */
export const CLASSIC_GHOUL_SECTION_IDS = { ...SHEET_SECTION_IDS, bond: 'section-bond' };

/** computeClassicFreebies' `rules` for a ghoul (FreebieSummary takes its costs and base). */
export const GHOUL_FREEBIE_RULES = {
  points: C.freebies, // 21
  costs: C.freebie_costs,
  disciplineDots: GHOUL_DISCIPLINE_DOTS,
  backgroundDots: GHOUL_BACKGROUND_DOTS,
};

/** Background names the forge offers (Mentor for independents; domitors seldom allow Retainers). */
export const GHOUL_BACKGROUND_PRESETS = ['Domitor', 'Allies', 'Contacts', 'Fame', 'Influence', 'Mentor', 'Resources', 'Retainers'];

/** A Classic domitor (the Classic ghoul forge's list): a Classic vampire, not a ghoul. */
export const isClassicDomitor = (ch) => canBeDomitor(ch) && String(ch.rules_edition || 'classic').toLowerCase() !== 'v5';

export const ghoulAttributePools = (primary) => attributePools(primary, GHOUL_ATTRIBUTE_PRIORITIES);
export const ghoulAbilityPools = (primary) => abilityPools(primary, GHOUL_ABILITY_PRIORITIES);

/** A Classic vampire's generation from its wod_meta ("12", 12, "12th"); 13 when unknown. */
export function domitorGeneration(domitor) {
  const g = domitor?.wod_meta?.generation ?? domitor?.generation;
  const n = typeof g === 'number' ? g : parseInt(String(g ?? '').trim(), 10);
  return Number.isInteger(n) && n >= 3 && n <= 15 ? n : 13;
}

/** The highest Discipline level a ghoul of a donor of this generation learns (13th–8th: 1). */
export function disciplineCap(generation) {
  const table = CLASSIC_GHOUL.discipline_cap_by_donor_generation;
  const g = Number.isInteger(generation) ? generation : 13;
  if (g >= 8) return 1;
  return table[String(Math.max(4, g))] ?? 5;
}

/** The Domitor Background's dots for a domitor of this generation (11th or higher: 1 … 6th: 5). */
export function domitorBackgroundDots(generation) {
  const g = Number.isInteger(generation) ? generation : 13;
  if (g >= 11) return 1;
  if (g >= 9) return 2;
  if (g === 8) return 3;
  if (g === 7) return 4;
  return 5;
}

const clanOf = (domitor) => String(domitor?.wod_meta?.clan || '').trim();

/** May this ghoul learn `name` (Protean / Thaumaturgy: only a vassal of a Gangrel / Tremere)? */
export function clanAllows(name, kind, domitor) {
  const clan = CLAN_ONLY_DISCIPLINES[name];
  return !clan || (kind === 'vassal' && clanOf(domitor).toLowerCase() === clan.toLowerCase());
}

/**
 * The Disciplines a ghoul may take besides Potence: a vassal's domitor's (its sheet's rows) plus the
 * instinctive Celerity and Fortitude; an independent's any. Sorted, without Potence.
 */
export function ghoulDisciplineOptions(domitor, kind) {
  const names = new Set();
  if (kind === 'vassal') {
    (Array.isArray(domitor?.wod_meta?.disciplines) ? domitor.wod_meta.disciplines : []).forEach((d) => {
      const n = String(d?.name || '').trim();
      if (n) names.add(n);
    });
    INSTINCTIVE_DISCIPLINES.forEach((n) => names.add(n));
  } else {
    DISCIPLINE_PRESETS.forEach((n) => names.add(n));
  }
  return [...names].filter((n) => n.toLowerCase() !== 'potence' && clanAllows(n, kind, domitor)).sort((a, b) => a.localeCompare(b));
}

/**
 * The starting Blood Pool: a roll of 1d10 (`rng` returns [0, 1)). An independent halves it, rounding
 * up (1–5); a vassal who rolls a 1 may reroll it if the Storyteller allows (`rerollable`).
 */
export function rollStartingPool(kind, rng = Math.random) {
  const roll = Math.min(10, 1 + Math.floor(rng() * 10));
  const pool = kind === 'independent' ? Math.ceil(roll / 2) : roll;
  return { roll, pool, rerollable: kind === 'vassal' && roll === 1 };
}

/** 'Vassal' / 'Independent' / 'Revenant' (English; the views translate with sheet:classicGhoul.kind.*). */
export const KIND_LABELS = { vassal: 'Vassal', independent: 'Independent', revenant: 'Revenant' };

/** Disciplines with Potence first, as the 1997 ghoul sheet prints them. */
export function potenceFirst(disciplines) {
  const rows = (Array.isArray(disciplines) ? disciplines : []).filter((d) => d && String(d.name || '').trim());
  const isPot = (d) => String(d.name).trim().toLowerCase() === 'potence';
  return [...rows.filter(isPot), ...rows.filter((d) => !isPot(d))];
}

const named = (rows) => (rows || []).filter((r) => r && String(r.name || '').trim());

/** Morality, final Virtues and the freebie ledger of the forge's sheet. */
export function deriveClassicGhoul(sheet) {
  const m = deriveClassicMorality(sheet.virtues, sheet.virtueFreebies);
  const freebies = computeClassicFreebies({
    systemType: 'vampire',
    attrs: sheet.attributes,
    attrPools: ghoulAttributePools(sheet.attrPriority),
    abilities: sheet.abilities,
    abilityPoolsSel: ghoulAbilityPools(sheet.abilityPriority),
    customAbilities: sheet.customAbilities,
    disciplines: named(sheet.disciplines),
    backgrounds: named(sheet.backgrounds),
    virtues: sheet.virtues,
    virtueFreebies: sheet.virtueFreebies,
    humanityBonus: sheet.humanityBonus,
    willpowerBonus: sheet.willpowerBonus,
    meritRows: sheet.meritRows,
    rules: GHOUL_FREEBIE_RULES,
  });
  return {
    humanity: Math.min(10, m.humanityBase + int(sheet.humanityBonus)),
    willpower: Math.min(10, m.willpowerBase + int(sheet.willpowerBonus)),
    virtues: finalVirtues(sheet.virtues, sheet.virtueFreebies),
    freebies,
  };
}

/**
 * Problems with the forge's sheet by section ({} when it is fine). `domitor`: the Classic vampire
 * (a GET /api/characters/ row).
 */
export function validateClassicGhoulSheet(sheet, domitor) {
  const S = CLASSIC_GHOUL_SECTION_IDS;
  const err = {};
  const add = (id, msg) => {
    err[id] = err[id] ? `${err[id]} ${msg}` : msg;
  };
  if (!domitor) add(S.identity, "Choose the ghoul's domitor.");
  if (!String(sheet.name || '').trim()) add(S.identity, 'Character name is required.');
  if (!FORGE_KINDS.includes(sheet.kind)) add(S.identity, 'Choose whether the ghoul is a vassal or independent.');
  if (!String(sheet.nature || '').trim()) add(S.identity, 'Enter your Nature (free text), or pick a preset archetype.');
  if (!String(sheet.demeanor || '').trim()) add(S.identity, 'Enter your Demeanor (free text), or pick a preset archetype.');
  CLASSIC_GHOUL_TEXT_FIELDS.forEach(([k, label, max, section]) => {
    if (String(sheet[k] || '').trim().length > max) add(S[section], `${label}: at most ${max} characters.`);
  });

  const a = validateAttributeSpread(sheet.attributes, ghoulAttributePools(sheet.attrPriority), { allowFreebies: true });
  if (a) add(S.attributes, a);
  const ab = validateAbilitySpread(sheet.abilities, ghoulAbilityPools(sheet.abilityPriority), sheet.customAbilities, { allowFreebies: true });
  if (ab) add(S.abilities, ab);

  const discs = named(sheet.disciplines);
  const isPot = (d) => String(d.name).trim().toLowerCase() === 'potence';
  if (!discs.some((d) => isPot(d) && int(d.dots) >= 1)) add(S.advantages, 'Every ghoul has Potence 1 or more.');
  if (!discs.some((d) => !isPot(d) && int(d.dots) >= 1)) add(S.advantages, 'Place the dot in a Discipline besides Potence.');
  const gen = domitorGeneration(domitor);
  const cap = disciplineCap(gen);
  const options = ghoulDisciplineOptions(domitor, sheet.kind);
  discs.forEach((d) => {
    const n = String(d.name).trim();
    if (int(d.dots) > cap) add(S.advantages, `${n} ${int(d.dots)}: the ghoul of a generation ${gen} domitor learns Disciplines up to ${cap}.`);
    if (!isPot(d) && !options.includes(n)) add(S.advantages, `${n} is not a Discipline this ghoul can learn.`);
  });
  const bgs = named(sheet.backgrounds);
  [...discs, ...bgs].forEach((r) => {
    const n = String(r.name).trim();
    if (n.length > CLASSIC_GHOUL_ROW_NAME_MAX) add(S.advantages, `${n.slice(0, 20)}…: a name is at most ${CLASSIC_GHOUL_ROW_NAME_MAX} characters.`);
  });
  // Fatal Addiction p. 65: vassals may buy Domitor; an independent ghoul has no master
  if (sheet.kind !== 'vassal' && bgs.some((b) => String(b.name).trim().toLowerCase() === 'domitor' && int(b.dots) > 0)) {
    add(S.advantages, 'Only a vassal takes the Domitor Background.');
  }
  bgs.forEach((b) => {
    if (GHOUL_NOT_ALLOWED_BACKGROUNDS.some((x) => x.toLowerCase() === String(b.name).trim().toLowerCase())) {
      add(S.advantages, `Ghouls take no ${String(b.name).trim()} Background.`);
    }
  });
  const bgSum = bgs.reduce((s, b) => s + int(b.dots), 0);
  if (bgSum < GHOUL_BACKGROUND_DOTS) add(S.advantages, `Place all ${GHOUL_BACKGROUND_DOTS} Background dots.`);
  const v = validateVirtues(sheet.virtues);
  if (v) add(S.advantages, v);
  const pool = sheet.bloodPool;
  if (!Number.isInteger(pool) || pool < 1 || pool > BLOOD_POOL_MAX) {
    add(S.advantages, `Roll or set the starting Blood Pool (1–${BLOOD_POOL_MAX}).`);
  }
  const stage = sheet.bondStage;
  if (!Number.isInteger(stage) || stage < 0 || stage > BOND_DRINKS) add(S.bond, `Blood Bond: 0 to ${BOND_DRINKS} drinks.`);

  const f = validateFreebies(deriveClassicGhoul(sheet).freebies);
  if (f) add(S.freebies, f);
  return err;
}

/**
 * The server's bounds problems (POST answer `problems`, English) by forge section; a text that is
 * too long becomes the client's message, so it is translated like the client's own checks.
 */
export function classicGhoulServerErrors(problems) {
  const S = CLASSIC_GHOUL_SECTION_IDS;
  const err = {};
  (problems || []).forEach((p) => {
    const text = String(p);
    const field = CLASSIC_GHOUL_TEXT_FIELDS.find(([, , , , label]) => text.startsWith(`${label} `));
    let id = S.identity;
    let msg = text;
    if (field) {
      id = S[field[3]];
      const m = text.match(/at most (\d+) characters/);
      if (m) msg = `${field[1]}: at most ${m[1]} characters.`;
    } else if (/^wod_meta\.ghoul\.(bond|feeding|overdosing)/.test(text)) id = S.bond;
    else if (/^wod_meta\.(disciplines|backgrounds|virtues|blood_pool|humanity|path|willpower|health_damage)/.test(text)) id = S.advantages;
    else if (/^attributes/.test(text)) id = S.attributes;
    else if (/^skills/.test(text)) id = S.abilities;
    else if (/^merits_flaws/.test(text)) id = S.story;
    err[id] = err[id] ? `${err[id]} ${msg}` : msg;
  });
  return err;
}

const posInt = (v) => {
  const n = parseInt(v, 10);
  return Number.isInteger(n) && n >= 0 ? n : null;
};

/** The POST /api/characters/ body's sheet part (name, background and flags are the caller's). */
export function buildClassicGhoulPayload(sheet, domitor) {
  const d = deriveClassicGhoul(sheet);
  const ab = sheet.abilities || {};
  const skills = {
    talents: Object.fromEntries(TALENTS.map(([k]) => [k, int(ab[k])])),
    skills: Object.fromEntries(SKILLS.map(([k]) => [k, int(ab[k])])),
    knowledges: Object.fromEntries(KNOWLEDGES.map(([k]) => [k, int(ab[k])])),
    allocation: { primary: sheet.abilityPriority, pools: ghoulAbilityPools(sheet.abilityPriority) },
    notes: '',
  };
  const custom = {};
  ['talents', 'skills', 'knowledges'].forEach((cat) => {
    const rows = (sheet.customAbilities?.[cat] || []).filter((r) => String(r.label || '').trim());
    if (rows.length) {
      custom[cat] = rows.map((r) => ({
        key: `custom_${cat}_${r.id}`,
        label: String(r.label).trim(),
        dots: Math.min(5, Math.max(0, int(r.dots))),
      }));
    }
  });
  if (Object.keys(custom).length) skills.custom = custom;
  const clean = (rows) => named(rows).map((r) => ({ name: String(r.name).trim(), dots: Math.min(5, Math.max(0, int(r.dots))) }));
  const ghoul = {
    kind: sheet.kind,
    domitor: { character_id: domitor?.id ?? null, name: domitor?.name || '', clan: clanOf(domitor) },
    duties: String(sheet.duties || '').trim(),
    ghouled_since: String(sheet.ghouledSince || '').trim(),
    bond: { stage: sheet.bondStage, note: String(sheet.bondNote || '').trim() },
    feeding: { last: String(sheet.feedingLast || '').trim(), note: String(sheet.feedingNote || '').trim() },
    overdosing: String(sheet.overdosing || '').trim(),
  };
  const age = posInt(sheet.age);
  const looks = posInt(sheet.apparentAge);
  if (age != null) ghoul.age = age;
  if (looks != null) ghoul.apparent_age = looks;
  return {
    system_type: 'vampire',
    attributes: { ...sheet.attributes },
    skills,
    merits_flaws: buildMeritsFlawsPayload(sheet.meritRows, sheet.meritNotes),
    wod_meta: {
      sheet_kind: 'ghoul',
      concept: String(sheet.concept || '').trim(),
      nature: sheet.nature || '',
      demeanor: sheet.demeanor || '',
      ghoul,
      blood_pool: { max: BLOOD_POOL_MAX, current: sheet.bloodPool, per_turn: BLOOD_POOL_PER_TURN },
      disciplines: potenceFirst(clean(sheet.disciplines)),
      backgrounds: clean(sheet.backgrounds),
      virtues: d.virtues,
      humanity: d.humanity,
      willpower: d.willpower,
    },
  };
}
