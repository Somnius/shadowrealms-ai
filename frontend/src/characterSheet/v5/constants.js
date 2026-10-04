/**
 * V5 sheet lists and creation constants. Rule data comes from src/rules/v5.json
 * (verbatim copy of docs/rules/v5.json); this module only reshapes it for the UI.
 */
import V5_RULES, {
  V5_BACKGROUNDS,
  V5_CLANS,
  V5_DISCIPLINES,
  V5_GENERATION_BP,
  V5_PREDATOR_TYPES,
  V5_SKILLS_WITH_FREE_SPECIALTY,
} from '../../rules/v5Rules';

/** 'Animal Ken' → 'animal_ken' (storage keys used by backend/services/character_sheet_v5.py). */
export const toKey = (label) => String(label).trim().toLowerCase().replace(/[^a-z0-9]+/g, '_');

const pairs = (labels) => labels.map((l) => [toKey(l), l]);

export const V5_ATTRIBUTES = {
  physical: pairs(V5_RULES.attributes.physical),
  social: pairs(V5_RULES.attributes.social),
  mental: pairs(V5_RULES.attributes.mental),
};
export const V5_ATTRIBUTE_KEYS = [
  ...V5_ATTRIBUTES.physical,
  ...V5_ATTRIBUTES.social,
  ...V5_ATTRIBUTES.mental,
].map(([k]) => k);

export const V5_SKILLS = {
  physical: pairs(V5_RULES.skills.physical),
  social: pairs(V5_RULES.skills.social),
  mental: pairs(V5_RULES.skills.mental),
};
export const V5_SKILL_CATEGORIES = ['physical', 'social', 'mental'];
export const V5_SKILL_KEYS = V5_SKILL_CATEGORIES.flatMap((c) => V5_SKILLS[c].map(([k]) => k));
export const V5_SKILL_LABELS = Object.fromEntries(
  V5_SKILL_CATEGORIES.flatMap((c) => V5_SKILLS[c])
);
export const V5_FREE_SPECIALTY_SKILLS = V5_SKILLS_WITH_FREE_SPECIALTY.map(toKey);

/** One at 4, three at 3, four at 2, one at 1 (Errata 2.0). */
export const V5_ATTRIBUTE_SPREAD = V5_RULES.creation.attributes.spread;

const DIST = V5_RULES.creation.skill_distributions;
const countsOf = (o) => Object.fromEntries(Object.entries(o).map(([k, v]) => [Number(k), v]));
export const V5_SKILL_DISTRIBUTIONS = {
  jack: { label: 'Jack of all trades', counts: countsOf(DIST.jack_of_all_trades) },
  balanced: { label: 'Balanced', counts: countsOf(DIST.balanced) },
  specialist: { label: 'Specialist', counts: countsOf(DIST.specialist) },
};

export const V5_ADVANTAGE_DOTS = V5_RULES.creation.advantages_dots; // 7
export const V5_FLAWS_MIN_DOTS = V5_RULES.creation.flaws_min_dots; // 2
export const V5_DISCIPLINE_DOTS = V5_RULES.creation.disciplines.dots; // [2, 1]
export const V5_STARTING_HUMANITY = V5_RULES.creation.humanity; // 7
/** Optional fledgling start (V5.md §2.6 / §4 step 9: default 7, ST option 8). */
export const V5_FLEDGLING_HUMANITY = V5_RULES.humanity.start_fledgling_option; // 8
/** Thin-blood Merits: 1–3, with the same number of thin-blood Flaws, no dot value (p. 142, 182). */
export const V5_THIN_BLOOD_MERITS = V5_RULES.creation.thin_blood.merits; // [1, 3]
export const V5_STARTING_HUNGER = 1;
export const V5_CONVICTIONS = V5_RULES.creation.convictions; // [1, 3]

export { V5_BACKGROUNDS, V5_CLANS, V5_DISCIPLINES, V5_PREDATOR_TYPES };
export const V5_CLAN_NAMES = V5_CLANS.map((c) => c.name);
export const THIN_BLOOD = 'Thin-blood';
export const CAITIFF = 'Caitiff';

/** Age brackets (Sea of Time, p. 151) and the generations they allow. */
const AGES = V5_RULES.creation.age_brackets;
export const V5_AGE_BRACKETS = {
  childer: { label: 'Childe / fledgling', generations: [12, 13, 14, 15, 16], xp: AGES.childer.xp },
  neonate: { label: 'Neonate', generations: [12, 13], xp: AGES.neonate.xp },
  ancilla: {
    label: 'Ancilla',
    generations: [10, 11],
    xp: AGES.ancilla.xp,
    blood_potency_bonus: AGES.ancilla.blood_potency_bonus,
    advantage_dots_bonus: AGES.ancilla.advantage_dots_bonus,
    flaw_dots_bonus: AGES.ancilla.flaw_dots_bonus,
    humanity_change: AGES.ancilla.humanity_change,
  },
};

/** Generation → {min_bp, max_bp, starting_bp?, thin_blood?} from the v5.json table. */
export function generationBloodPotency(generation) {
  const g = parseInt(generation, 10);
  if (!Number.isFinite(g)) return null;
  for (const row of V5_GENERATION_BP) {
    const [lo, hi] = String(row.generation).split('-').map((x) => parseInt(x, 10));
    if (g >= lo && g <= (hi || lo)) return row;
  }
  return null;
}

/** "Blood Sorcery (Tremere only)" → { name: 'Blood Sorcery', clan: 'Tremere' } */
export function parsePredatorDiscipline(text) {
  const m = String(text).match(/^(.*?)\s*\((\w[\w-]*) only\)\s*$/);
  if (m) return { name: m[1].trim(), clan: m[2] };
  return { name: String(text).trim(), clan: null };
}

/** "Intimidation (Stickups)" → { skill: 'intimidation', name: 'Stickups' } */
export function parsePredatorSpecialty(text) {
  const m = String(text).match(/^(.*?)\s*\((.*)\)\s*$/);
  if (!m) return { skill: toKey(text), name: '' };
  return { skill: toKey(m[1]), name: m[2].trim() };
}

export const V5_SECTION_IDS = {
  identity: 'v5-section-identity',
  clan: 'v5-section-clan',
  attributes: 'v5-section-attributes',
  skills: 'v5-section-skills',
  disciplines: 'v5-section-disciplines',
  predator: 'v5-section-predator',
  advantages: 'v5-section-advantages',
  humanity: 'v5-section-humanity',
  story: 'v5-section-story',
};
