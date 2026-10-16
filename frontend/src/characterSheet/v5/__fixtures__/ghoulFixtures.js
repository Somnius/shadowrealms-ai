/**
 * Ghoul test fixtures: Darius Vale (character 17, a V5 Ventrue with no chronicle) as GET
 * /api/characters/ lists him, and Mira Tanis, his Gifted ghoul, as the ghoul forge's state
 * (characterSheet/v5/ghoul.js). The acceptance case: she passes both checks with no override
 * (backend/tests/unit/test_v5_ghoul_chargen.py has the same sheet as a payload).
 */
import { emptyV5Skills } from '../validation';

export const DARIUS = {
  id: 17,
  name: 'Darius Vale',
  user_id: 3,
  campaign_id: null,
  campaign_name: null,
  system_type: 'vampire',
  rules_edition: 'v5',
  sheet_kind: null,
  wod_meta: {
    edition: 'v5',
    clan: 'Ventrue',
    predator_type: 'Montero',
    disciplines: [
      { name: 'Dominate', level: 3, powers: ['Cloud Memory', 'Mesmerize', 'Submerged Directive'] },
      { name: 'Presence', level: 1, powers: ['Awe'] },
    ],
  },
};

/** Skills from {rating: [keys]}. */
export const skillsOf = (byRating) => {
  const s = emptyV5Skills();
  Object.entries(byRating).forEach(([r, keys]) => keys.forEach((k) => (s[k] = Number(r))));
  return s;
};

export const miraSheet = (over = {}) => ({
  name: 'Mira Tanis',
  concept: "Former television executive at rock bottom; now Darius's producer and operations manager",
  ambition: '',
  desire: '',
  template: 'gifted',
  retainerDots: 3,
  age: 55,
  apparentAge: 53,
  ghouledSince: "About two to three years ago, during Darius's independent year, before Kessler.",
  attributes: { strength: 1, dexterity: 1, stamina: 1, charisma: 2, manipulation: 4, composure: 1, intelligence: 3, wits: 3, resolve: 2 },
  skillDistribution: 'balanced',
  skills: skillsOf({
    4: ['persuasion', 'subterfuge'],
    3: ['leadership', 'insight', 'etiquette', 'finance'],
    2: ['academics', 'technology', 'politics', 'streetwise'],
    1: ['awareness', 'craft', 'drive', 'investigation'],
  }),
  specialties: [
    { skill: 'persuasion', name: 'Negotiation' },
    { skill: 'academics', name: 'Media studies' },
    { skill: 'craft', name: 'Video editing' },
  ],
  power: { discipline: 'Dominate', name: 'Cloud Memory' },
  advantages: [
    { id: 'merit:beautiful', name: 'Beautiful', dots: 2, kind: 'merit' },
    { id: 'background:contacts', name: 'Contacts', dots: 2, kind: 'background', note: 'television production coordinator' },
    { id: 'background:contacts', name: 'Contacts', dots: 3, kind: 'background', note: 'network acquisitions executive' },
    { id: 'background:fame', name: 'Fame', dots: 1, kind: 'background', note: 'television production industry' },
    { id: 'background:influence', name: 'Influence', dots: 1, kind: 'background', note: 'Istanbul television production' },
    { id: 'merit:linguistics', name: 'Linguistics', dots: 1, kind: 'merit', note: 'English' },
  ],
  flaws: [
    { id: 'flaw:two-masters', name: 'Two Masters', dots: 1 },
    { id: 'flaw:bondslave', name: 'Bondslave', dots: 2 },
    { id: 'flaw:addiction', name: 'Addiction', dots: 1, note: 'cocaine' },
  ],
  bonds: [{ strength: null, note: 'Full Bond from the first drink (Bondslave).' }],
  feeding: { last: '', note: "A Rouse Check's worth of Darius's Blood about once a month." },
  humanityTracked: true,
  convictions: [],
  ...over,
});
