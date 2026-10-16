/**
 * Classic ghoul test fixtures: Theodore Doukas (character 21, a Classic Ventrue of the 12th
 * generation) as GET /api/characters/ lists him, and Marta Ionescu, his vassal, as the Classic ghoul
 * forge's sheet (characterSheet/classicGhoul.js): legal by Ghouls: Fatal Addiction (6/4/3, 11/7/4,
 * Potence 1 + Dominate 1, Backgrounds 5, Virtues 1 + 7, a Blood Pool of 6).
 * backend/tests/unit/test_ghoul_routes.py has a sheet like hers as a payload.
 */
import { emptyAbilityMap } from '../validation';

export const THEO = {
  id: 21,
  name: 'Theodore Doukas',
  user_id: 3,
  rules_edition: 'classic',
  system_type: 'vampire',
  campaign_id: 12,
  wod_meta: {
    clan: 'Ventrue',
    generation: '12',
    disciplines: [
      { name: 'Dominate', dots: 2 },
      { name: 'Fortitude', dots: 1 },
      { name: 'Presence', dots: 1 },
    ],
  },
};

/** A legal sheet: 6/4/3, 11/7/4, Potence 1 + Dominate 1, Backgrounds 5, Virtues 1 + 7. */
export function martaSheet(extra = {}) {
  return {
    name: 'Marta Ionescu',
    concept: 'Driver',
    kind: 'vassal',
    nature: 'Caregiver',
    demeanor: 'Conformist',
    duties: 'Drives, keeps the house',
    ghouledSince: '1998',
    age: '51',
    apparentAge: '38',
    attrPriority: 'physical',
    attributes: { strength: 3, dexterity: 3, stamina: 3, charisma: 2, manipulation: 3, appearance: 2, perception: 2, intelligence: 2, wits: 2 },
    abilityPriority: 'talents',
    abilities: { ...emptyAbilityMap(), alertness: 3, brawl: 3, subterfuge: 3, dodge: 2, drive: 3, etiquette: 2, firearms: 2, finance: 2, law: 2 },
    customAbilities: { talents: [], skills: [], knowledges: [] },
    disciplines: [
      { name: 'Potence', dots: 1 },
      { name: 'Dominate', dots: 1 },
    ],
    backgrounds: [
      { name: 'Domitor', dots: 1 },
      { name: 'Resources', dots: 2 },
      { name: 'Contacts', dots: 2 },
    ],
    virtues: { conscience: 3, self_control: 3, courage: 4 },
    virtueFreebies: { conscience: 0, self_control: 0, courage: 0 },
    humanityBonus: 0,
    willpowerBonus: 0,
    bloodPool: 6,
    bondStage: 3,
    bondNote: 'Third drink in 1998',
    feedingLast: '',
    feedingNote: 'A point each month',
    overdosing: '',
    meritRows: [],
    meritNotes: '',
    ...extra,
  };
}
