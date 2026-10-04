/**
 * Classic (VtM Revised) rule constants.
 *
 * Source: ./classic.json is a verbatim copy of docs/rules/classic.json
 * (spec: docs/rules/CLASSIC_REVISED.md). Keep them in sync:
 * `cp docs/rules/classic.json frontend/src/rules/classic.json`.
 */
import CLASSIC_RULES from './classic.json';

export default CLASSIC_RULES;

export const CLASSIC_CREATION = CLASSIC_RULES.creation;

/** Revised creation budgets (dots ADDED on top of the free base dots). */
export const ATTRIBUTE_PRIORITIES = CLASSIC_CREATION.attributes.priorities; // [7,5,3]
export const ABILITY_PRIORITIES = CLASSIC_CREATION.abilities.priorities; // [13,9,5]
export const ABILITY_MAX_BEFORE_FREEBIES = CLASSIC_CREATION.abilities.max_before_freebies; // 3
export const DISCIPLINE_DOTS = CLASSIC_CREATION.disciplines.dots; // 3
export const BACKGROUND_DOTS = CLASSIC_CREATION.backgrounds.dots; // 5
export const VIRTUE_DOTS = CLASSIC_CREATION.virtues.dots; // 7 (plus 1 free in each)
export const FREEBIE_POINTS = CLASSIC_CREATION.freebies; // 15
/** Nosferatu Appearance at creation (and forever). */
export const NOSFERATU_APPEARANCE = CLASSIC_CREATION.attributes.nosferatu_appearance; // 0
export const FLAWS_MAX_POINTS = CLASSIC_CREATION.flaws_max_points; // 7

/** Freebie cost per dot, keyed by trait type. */
export const FREEBIE_COSTS = Object.fromEntries(
  Object.entries(CLASSIC_CREATION.freebie_costs).map(([k, v]) => [k, v.cost])
);

export const CLASSIC_DISCIPLINES = CLASSIC_RULES.disciplines;
export const CLASSIC_DIFFICULTY_DEFAULT = CLASSIC_RULES.dice.difficulty_default;
