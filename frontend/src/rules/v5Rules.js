/**
 * V5 rule constants.
 *
 * Source: ./v5.json is a verbatim copy of docs/rules/v5.json (spec: docs/rules/V5.md).
 * Keep them in sync: `cp docs/rules/v5.json frontend/src/rules/v5.json`.
 */
import V5_RULES from './v5.json';

export default V5_RULES;

export const V5_SUCCESS_ON = V5_RULES.dice.success_on; // 6
export const V5_MAX_HUNGER = V5_RULES.hunger.max; // 5
export const V5_WILLPOWER_REROLL_MAX = V5_RULES.dice.willpower_reroll.max_dice; // 3
export const V5_DIFFICULTY_TABLE = V5_RULES.dice.difficulty_table;
export const V5_CREATION = V5_RULES.creation;
export const V5_CLANS = V5_RULES.clans;
export const V5_DISCIPLINES = V5_RULES.disciplines;
export const V5_PREDATOR_TYPES = V5_RULES.predator_types;
export const V5_BACKGROUNDS = V5_RULES.backgrounds;
export const V5_GENERATION_BP = V5_RULES.generation_blood_potency;
export const V5_SKILLS_WITH_FREE_SPECIALTY = V5_RULES.skills_with_free_specialty;
