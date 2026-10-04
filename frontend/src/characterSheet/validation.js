/**
 * Classic (Revised) character creation rules.
 * Source: docs/rules/CLASSIC_REVISED.md §creation via src/rules/classic.json.
 *
 * - Attributes: every Attribute starts with 1 free dot; 7 / 5 / 3 dots are ADDED on top
 *   (category totals 10 / 8 / 6 before freebies).
 * - Abilities: 13 / 9 / 5 dots, no Ability above 3 before freebies.
 * - Vampire: 3 Discipline dots, 5 Background dots, Virtues 1 free each + 7 (total 10),
 *   Humanity = Conscience + Self-Control, Willpower = Courage (worked out before freebies).
 *   Freebie Virtue dots are kept apart from the creation Virtues and never change them.
 * - Nosferatu: Appearance 0, never raised.
 * - 15 freebie points (+ up to 7 from Flaws). Costs per dot from classic.json.
 *
 * The wizard stores FINAL ratings. Dots beyond the creation budgets are counted as
 * freebie dots and priced by `computeClassicFreebies`.
 */
import {
  ABILITY_MAX_BEFORE_FREEBIES,
  ABILITY_PRIORITIES,
  ATTRIBUTE_PRIORITIES,
  BACKGROUND_DOTS,
  DISCIPLINE_DOTS,
  FLAWS_MAX_POINTS,
  FREEBIE_COSTS,
  FREEBIE_POINTS,
  NOSFERATU_APPEARANCE,
  VIRTUE_DOTS,
} from '../rules/classicRules';
import {
  KNOWLEDGES,
  MENTAL,
  MTA_SPHERES,
  PHYSICAL,
  SKILLS,
  SOCIAL,
  TALENTS,
} from './constants';

const int = (v) => {
  const n = parseInt(v, 10);
  return Number.isFinite(n) ? n : 0;
};

/** Free base dot in every Attribute. */
export const ATTRIBUTE_BASE = 1;
/** Free dot in each of the three Virtues (Humanity followers). */
export const VIRTUE_BASE = 1;
export const VIRTUE_KEYS = ['conscience', 'self_control', 'courage'];
export const VIRTUE_TOTAL_AT_CREATION = VIRTUE_DOTS + VIRTUE_BASE * VIRTUE_KEYS.length; // 10

export function emptyAttrMap() {
  const o = {};
  [...PHYSICAL, ...SOCIAL, ...MENTAL].forEach((k) => {
    o[k] = ATTRIBUTE_BASE;
  });
  return o;
}

export function emptyAbilityMap() {
  const o = {};
  [...TALENTS, ...SKILLS, ...KNOWLEDGES].forEach(([k]) => {
    o[k] = 0;
  });
  return o;
}

export function emptySphereMap() {
  const o = {};
  MTA_SPHERES.forEach(([k]) => {
    o[k] = 0;
  });
  return o;
}

export function emptyVirtues() {
  return { conscience: VIRTUE_BASE, self_control: VIRTUE_BASE, courage: VIRTUE_BASE };
}

/** {physical, social, mental} dots to add, by primary/secondary/tertiary choice. */
export function attributePools(primary) {
  const [a, b, c] = ATTRIBUTE_PRIORITIES;
  if (primary === 'social') return { physical: b, social: a, mental: c };
  if (primary === 'mental') return { physical: c, social: b, mental: a };
  return { physical: a, social: b, mental: c };
}

/** {talents, skills, knowledges} dots, by primary column choice (secondary/tertiary fixed as before). */
export function abilityPools(primary) {
  const [a, b, c] = ABILITY_PRIORITIES;
  if (primary === 'skills') return { talents: b, skills: a, knowledges: c };
  if (primary === 'knowledges') return { talents: c, skills: b, knowledges: a };
  return { talents: a, skills: b, knowledges: c };
}

export function sumAbilitiesInCategory(abilities, keys) {
  return keys.reduce((s, [k]) => s + int(abilities[k]), 0);
}

const ATTR_CATS = [
  ['physical', 'Physical', PHYSICAL],
  ['social', 'Social', SOCIAL],
  ['mental', 'Mental', MENTAL],
];

/** Free base dot for one Attribute (Nosferatu Appearance has none: it stays 0). */
export function attributeBase(key, { nosferatu = false } = {}) {
  return nosferatu && key === 'appearance' ? NOSFERATU_APPEARANCE : ATTRIBUTE_BASE;
}

/** Dots added above the free base, per category. */
export function attributeAddedDots(attrs, { nosferatu = false } = {}) {
  const out = {};
  ATTR_CATS.forEach(([cat, , keys]) => {
    out[cat] = keys.reduce(
      (s, k) => s + int(attrs[k]) - attributeBase(k, { nosferatu }),
      0
    );
  });
  return out;
}

/**
 * @param pools - dots to ADD per category ({physical: 7, social: 5, mental: 3})
 * @param [opts.allowFreebies] - extra dots allowed (priced as freebies elsewhere)
 * @param [opts.nosferatu] - Appearance must be 0 and has no free dot
 */
export function validateAttributeSpread(
  attrs,
  pools,
  { allowFreebies = false, nosferatu = false } = {}
) {
  for (const k of [...PHYSICAL, ...SOCIAL, ...MENTAL]) {
    const v = parseInt(attrs[k], 10);
    if (nosferatu && k === 'appearance') {
      if (v !== NOSFERATU_APPEARANCE) {
        return `Nosferatu have Appearance ${NOSFERATU_APPEARANCE} and can never raise it.`;
      }
      continue;
    }
    if (Number.isNaN(v) || v < 1 || v > 5) {
      return `Each attribute must be between 1 and 5 (${k}).`;
    }
  }
  const added = attributeAddedDots(attrs, { nosferatu });
  for (const [cat, label] of ATTR_CATS) {
    if (added[cat] < pools[cat] || (!allowFreebies && added[cat] > pools[cat])) {
      return `${label}: add exactly ${pools[cat]} dots on top of the free dot in each attribute (added ${added[cat]}).`;
    }
  }
  return null;
}

function sumCustomDots(customList) {
  return (customList || []).reduce((s, r) => s + int(r.dots), 0);
}

const ABILITY_CATS = [
  ['talents', 'Talents', TALENTS],
  ['skills', 'Skills', SKILLS],
  ['knowledges', 'Knowledges', KNOWLEDGES],
];

/** All ratings of one ability column (base + custom rows). */
function abilityValues(abilities, list, customRows) {
  return [...list.map(([k]) => int(abilities[k])), ...(customRows || []).map((r) => int(r.dots))];
}

/**
 * Per column: creation dots (each ability counts at most 3) and freebie dots
 * (dots above 3 + creation dots beyond the column budget).
 */
export function abilityDotBreakdown(abilities, pools, custom) {
  const out = {};
  ABILITY_CATS.forEach(([cat, , list]) => {
    const vals = abilityValues(abilities, list, custom?.[cat]);
    const total = vals.reduce((s, v) => s + v, 0);
    const capped = vals.reduce((s, v) => s + Math.min(v, ABILITY_MAX_BEFORE_FREEBIES), 0);
    out[cat] = {
      total,
      creation: Math.min(capped, pools[cat]),
      remaining: Math.max(0, pools[cat] - capped),
      freebieDots: Math.max(0, total - pools[cat]),
    };
  });
  return out;
}

/**
 * @param abilities - base key map
 * @param pools - { talents, skills, knowledges }
 * @param [custom] - { talents?: [], skills?: [], knowledges?: [] } each row { dots }
 * @param [opts.allowFreebies] - dots above 3 / above the budget allowed (priced as freebies)
 */
export function validateAbilitySpread(abilities, pools, custom, { allowFreebies = false } = {}) {
  for (const [k] of [...TALENTS, ...SKILLS, ...KNOWLEDGES]) {
    const v = parseInt(abilities[k], 10);
    if (Number.isNaN(v) || v < 0 || v > 5) {
      return `Each ability must be between 0 and 5 (${k}).`;
    }
  }
  for (const list of [custom?.talents, custom?.skills, custom?.knowledges]) {
    for (const r of list || []) {
      const v = parseInt(r.dots, 10);
      if (Number.isNaN(v) || v < 0 || v > 5) {
        return 'Each ability (including custom rows) must be between 0 and 5.';
      }
    }
  }
  for (const [cat, label, list] of ABILITY_CATS) {
    const vals = abilityValues(abilities, list, custom?.[cat]);
    if (!allowFreebies && vals.some((v) => v > ABILITY_MAX_BEFORE_FREEBIES)) {
      return `No ability above ${ABILITY_MAX_BEFORE_FREEBIES} before freebie points (${label}).`;
    }
    const capped = vals.reduce((s, v) => s + Math.min(v, ABILITY_MAX_BEFORE_FREEBIES), 0);
    const total = vals.reduce((s, v) => s + v, 0);
    if (capped < pools[cat] || (!allowFreebies && total !== pools[cat])) {
      return `${label} must use all ${pools[cat]} dots, no ability above ${ABILITY_MAX_BEFORE_FREEBIES} (currently ${capped}).`;
    }
  }
  return null;
}

/**
 * Virtues: 1 free dot in each + 7 to spend (total 10). With freebies, more is allowed.
 */
export function validateVirtues(v, { allowFreebies = false } = {}) {
  const vals = VIRTUE_KEYS.map((k) => int(v?.[k]));
  if (vals.some((x) => x < 1 || x > 5)) {
    return 'Each virtue must be between 1 and 5.';
  }
  const total = vals.reduce((s, x) => s + x, 0);
  if (total < VIRTUE_TOTAL_AT_CREATION || (!allowFreebies && total !== VIRTUE_TOTAL_AT_CREATION)) {
    return `Virtues: 1 free dot each plus ${VIRTUE_DOTS} more (total ${VIRTUE_TOTAL_AT_CREATION}; currently ${total}).`;
  }
  return null;
}

/** Virtue dots bought with freebies, kept apart from the creation Virtues. */
export function emptyVirtueFreebies() {
  return { conscience: 0, self_control: 0, courage: 0 };
}

/** Final Virtue ratings = creation dots + freebie dots. */
export function finalVirtues(creationVirtues, virtueFreebies) {
  const out = {};
  VIRTUE_KEYS.forEach((k) => {
    out[k] = int(creationVirtues?.[k]) + Math.max(0, int(virtueFreebies?.[k]));
  });
  return out;
}

/**
 * Humanity = Conscience + Self-Control, Willpower = Courage, worked out from the
 * CREATION Virtues only (classic.json / CLASSIC_REVISED.md: before freebies). Virtue
 * dots bought with freebies are tracked separately and never raise Humanity/Willpower;
 * freebie Humanity/Willpower dots are added on top by the caller.
 *
 * @param creationVirtues - the 1 free + 7 dots placed at creation
 * @param [virtueFreebies] - extra Virtue dots bought with freebies, per Virtue
 */
export function deriveClassicMorality(creationVirtues, virtueFreebies) {
  const c = int(creationVirtues?.conscience);
  const sc = int(creationVirtues?.self_control);
  const co = int(creationVirtues?.courage);
  const virtueFreebieDots = VIRTUE_KEYS.reduce(
    (s, k) => s + Math.max(0, int(virtueFreebies?.[k])),
    0
  );
  return {
    humanityBase: c + sc,
    willpowerBase: co,
    virtueFreebieDots,
  };
}

/** Classic Nosferatu start with Appearance 0 (classic.json creation.attributes.nosferatu_appearance). */
export function isNosferatu(systemType, clan) {
  return (
    String(systemType || '').toLowerCase() === 'vampire' &&
    String(clan || '').trim().toLowerCase() === 'nosferatu'
  );
}

/** Merit rows: positive points = merit cost, negative = flaw bonus (capped at 7). */
export function meritFlawPoints(meritRows) {
  let merits = 0;
  let flaws = 0;
  (meritRows || []).forEach((r) => {
    if (!r || !String(r.name || '').trim()) return;
    const p = int(r.points);
    if (p > 0) merits += p;
    else flaws += -p;
  });
  return { merits, flaws, flawBonus: Math.min(flaws, FLAWS_MAX_POINTS) };
}

/**
 * Freebie points spent by a classic sheet.
 * Attributes/Abilities/Merits/Flaws apply to every Revised line; Disciplines,
 * Backgrounds, Virtues, Humanity and Willpower only to Vampire.
 *
 * @returns {{ lines: Array<{key,label,dots,cost}>, spent, available, remaining, flaws }}
 */
export function computeClassicFreebies({
  systemType,
  attrs,
  attrPools,
  abilities,
  abilityPoolsSel,
  customAbilities,
  disciplines,
  backgrounds,
  virtues,
  virtueFreebies,
  humanityBonus = 0,
  willpowerBonus = 0,
  meritRows,
  nosferatu = false,
}) {
  const lines = [];
  const push = (key, label, dots, perDot) => {
    if (dots > 0) lines.push({ key, label, dots, cost: dots * perDot });
  };

  const added = attributeAddedDots(attrs || {}, { nosferatu });
  const attrExtra = ['physical', 'social', 'mental'].reduce(
    (s, cat) => s + Math.max(0, added[cat] - (attrPools?.[cat] || 0)),
    0
  );
  push('attributes', 'Attributes', attrExtra, FREEBIE_COSTS.attribute);

  const ab = abilityDotBreakdown(abilities || {}, abilityPoolsSel || {}, customAbilities);
  const abExtra = Object.values(ab).reduce((s, x) => s + x.freebieDots, 0);
  push('abilities', 'Abilities', abExtra, FREEBIE_COSTS.ability);

  if (String(systemType || '').toLowerCase() === 'vampire') {
    const dSum = (disciplines || []).reduce((s, d) => s + int(d.dots), 0);
    push('disciplines', 'Disciplines', Math.max(0, dSum - DISCIPLINE_DOTS), FREEBIE_COSTS.discipline);
    const bSum = (backgrounds || []).reduce((s, b) => s + int(b.dots), 0);
    push('backgrounds', 'Backgrounds', Math.max(0, bSum - BACKGROUND_DOTS), FREEBIE_COSTS.background);
    const m = deriveClassicMorality(virtues, virtueFreebies);
    push('virtues', 'Virtues', m.virtueFreebieDots, FREEBIE_COSTS.virtue);
    push('humanity', 'Humanity', Math.max(0, int(humanityBonus)), FREEBIE_COSTS.humanity_or_path);
    push('willpower', 'Willpower', Math.max(0, int(willpowerBonus)), FREEBIE_COSTS.willpower);
  }

  const mf = meritFlawPoints(meritRows);
  if (mf.merits > 0) lines.push({ key: 'merits', label: 'Merits', dots: mf.merits, cost: mf.merits });

  const spent = lines.reduce((s, l) => s + l.cost, 0);
  const available = FREEBIE_POINTS + mf.flawBonus;
  return { lines, spent, available, remaining: available - spent, flaws: mf };
}

/** Error text when the sheet overspends freebies (or claims too many Flaw points). */
export function validateFreebies(freebies) {
  if (!freebies) return null;
  if (freebies.flaws.flaws > FLAWS_MAX_POINTS) {
    return `Flaws give at most ${FLAWS_MAX_POINTS} extra freebie points (you listed ${freebies.flaws.flaws}).`;
  }
  if (freebies.spent > freebies.available) {
    return `Freebie points overspent: ${freebies.spent} of ${freebies.available}.`;
  }
  return null;
}

export function validateSpheres(spheres) {
  let t = 0;
  for (const [k] of MTA_SPHERES) {
    const v = parseInt(spheres[k], 10) || 0;
    if (v < 0 || v > 5) return `Sphere ${k} must be 0–5.`;
    t += v;
  }
  if (t !== 6) return `Allocate exactly 6 sphere dots at creation (currently ${t}).`;
  return null;
}

/** Pool remainder helpers for UI summaries (dots still to place from the creation budget). */
export function attributePoolRemainders(attrs, pools, { nosferatu = false } = {}) {
  const added = attributeAddedDots(attrs, { nosferatu });
  return {
    physical: pools.physical - added.physical,
    social: pools.social - added.social,
    mental: pools.mental - added.mental,
  };
}

export function abilityPoolRemainders(abilities, pools, custom) {
  const ab = abilityDotBreakdown(abilities, pools, custom);
  return {
    talents: ab.talents.remaining,
    skills: ab.skills.remaining,
    knowledges: ab.knowledges.remaining,
  };
}

export { sumCustomDots };
