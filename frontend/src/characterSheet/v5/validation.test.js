import {
  V5_DISCIPLINES,
  V5_SECTION_IDS,
  V5_SKILL_DISTRIBUTIONS,
  generationBloodPotency,
} from './constants';
import {
  attributeSpreadStatus,
  buildV5Payload,
  deriveV5,
  disciplineRows,
  emptyV5Attributes,
  emptyV5Skills,
  finalDisciplines,
  finalSkills,
  predatorDisciplineOptions,
  validateV5Attributes,
  validateV5Disciplines,
  validateV5Sheet,
  validateV5Skills,
  validateV5Specialties,
  validateThinBloodMeritsFlaws,
} from './validation';

const goodAttrs = () => ({
  strength: 4,
  dexterity: 3,
  stamina: 3,
  charisma: 3,
  manipulation: 2,
  composure: 2,
  intelligence: 2,
  wits: 2,
  resolve: 1,
});

/** Balanced: three at 3, five at 2, seven at 1 */
const balancedSkills = () => {
  const s = emptyV5Skills();
  ['athletics', 'brawl', 'stealth'].forEach((k) => (s[k] = 3));
  ['drive', 'firearms', 'insight', 'persuasion', 'awareness'].forEach((k) => (s[k] = 2));
  ['melee', 'larceny', 'etiquette', 'streetwise', 'subterfuge', 'investigation', 'occult'].forEach(
    (k) => (s[k] = 1)
  );
  return s;
};

const goodSheet = () => ({
  name: 'Ada',
  clan: 'Brujah',
  age: 'neonate',
  generation: 13,
  attributes: goodAttrs(),
  skillDistribution: 'balanced',
  skills: balancedSkills(),
  specialties: [{ skill: 'brawl', name: 'Grappling' }],
  disciplines: [
    { name: 'Potence', level: 2, powers: ['Lethal Body', ''] },
    { name: 'Presence', level: 1, powers: [] },
  ],
  predatorType: 'Alleycat',
  predatorSpecialty: 0,
  predatorDiscipline: 'Celerity',
  advantages: [
    { name: 'Resources', dots: 3, kind: 'background' },
    { name: 'Haven', dots: 2, kind: 'background' },
  ],
  flaws: [{ name: 'Enemy', dots: 2 }],
  convictions: [{ conviction: 'Never harm a child', touchstone: 'Mia, my niece' }],
});

describe('V5 rule data matches docs/rules/v5.json', () => {
  it('has the three skill distributions', () => {
    expect(V5_SKILL_DISTRIBUTIONS.jack.counts).toEqual({ 3: 1, 2: 8, 1: 10 });
    expect(V5_SKILL_DISTRIBUTIONS.balanced.counts).toEqual({ 3: 3, 2: 5, 1: 7 });
    expect(V5_SKILL_DISTRIBUTIONS.specialist.counts).toEqual({ 4: 1, 3: 3, 2: 3, 1: 3 });
  });

  it('maps generation to blood potency', () => {
    expect(generationBloodPotency(13).starting_bp).toBe(1);
    expect(generationBloodPotency(11).starting_bp).toBe(2);
    expect(generationBloodPotency(15).thin_blood).toBe(true);
  });
});

describe('V5 attributes', () => {
  it('accepts 4/3/3/3/2/2/2/2/1', () => {
    expect(validateV5Attributes(goodAttrs())).toBeNull();
  });
  it('rejects the pre-errata spread (four at 3, three at 2)', () => {
    const a = { ...goodAttrs(), manipulation: 3, resolve: 2, composure: 1 };
    expect(validateV5Attributes(a)).not.toBeNull();
  });
  it('rejects a 5 at creation', () => {
    expect(validateV5Attributes({ ...goodAttrs(), strength: 5 })).not.toBeNull();
  });
  it('reports spread status', () => {
    const st = attributeSpreadStatus(emptyV5Attributes());
    expect(st.find((r) => r.rating === 1)).toEqual({ rating: 1, need: 1, have: 9 });
  });
});

describe('V5 skills', () => {
  it('accepts a balanced spread', () => {
    expect(validateV5Skills(balancedSkills(), 'balanced')).toBeNull();
  });
  it('rejects the wrong distribution', () => {
    expect(validateV5Skills(balancedSkills(), 'jack')).not.toBeNull();
  });
  it('accepts jack of all trades', () => {
    const s = emptyV5Skills();
    const keys = Object.keys(s);
    s[keys[0]] = 3;
    keys.slice(1, 9).forEach((k) => (s[k] = 2));
    keys.slice(9, 19).forEach((k) => (s[k] = 1));
    expect(validateV5Skills(s, 'jack')).toBeNull();
  });
  it('rejects a 4 outside specialist', () => {
    const s = balancedSkills();
    s.athletics = 4;
    expect(validateV5Skills(s, 'balanced')).not.toBeNull();
  });
  it('requires the free specialty for rated Academics/Craft/Performance/Science', () => {
    const s = balancedSkills();
    s.occult = 0;
    s.academics = 1;
    expect(validateV5Specialties([{ skill: 'brawl', name: 'x' }], s)).toMatch(/Academics/);
    expect(
      validateV5Specialties(
        [
          { skill: 'brawl', name: 'x' },
          { skill: 'academics', name: 'History' },
        ],
        s
      )
    ).toBeNull();
  });
  it('limits specialties and needs a dot in the skill', () => {
    const s = balancedSkills();
    expect(
      validateV5Specialties(
        [
          { skill: 'brawl', name: 'x' },
          { skill: 'stealth', name: 'y' },
        ],
        s
      )
    ).not.toBeNull();
    expect(validateV5Specialties([{ skill: 'science', name: 'x' }], s)).not.toBeNull();
  });
});

describe('V5 disciplines', () => {
  it('needs two clan disciplines at 2 and 1', () => {
    expect(validateV5Disciplines(goodSheet().disciplines, 'Brujah', V5_DISCIPLINES)).toBeNull();
    expect(
      validateV5Disciplines(
        [
          { name: 'Potence', level: 2 },
          { name: 'Auspex', level: 1 },
        ],
        'Brujah',
        V5_DISCIPLINES
      )
    ).toMatch(/clan/);
    expect(
      validateV5Disciplines(
        [
          { name: 'Potence', level: 2 },
          { name: 'Presence', level: 2 },
        ],
        'Brujah',
        V5_DISCIPLINES
      )
    ).not.toBeNull();
  });
  it('lets Caitiff pick any two', () => {
    expect(
      validateV5Disciplines(
        [
          { name: 'Auspex', level: 2 },
          { name: 'Protean', level: 1 },
        ],
        'Caitiff',
        V5_DISCIPLINES
      )
    ).toBeNull();
  });
  it('gives thin-bloods none', () => {
    expect(validateV5Disciplines([], 'Thin-blood', V5_DISCIPLINES)).toBeNull();
  });
  it('drops Tremere-only predator disciplines for other clans', () => {
    expect(predatorDisciplineOptions('Bagger', 'Brujah')).toEqual(['Obfuscate']);
    expect(predatorDisciplineOptions('Bagger', 'Tremere')).toEqual(['Blood Sorcery', 'Obfuscate']);
  });
  it('adds the predator dot', () => {
    const s = { ...goodSheet(), predatorDiscipline: 'Potence' };
    expect(finalDisciplines(s).find((d) => d.name === 'Potence').level).toBe(3);
    expect(finalDisciplines(goodSheet()).map((d) => [d.name, d.level])).toEqual([
      ['Potence', 2],
      ['Presence', 1],
      ['Celerity', 1],
    ]);
  });
});

describe('V5 derived traits', () => {
  it('derives health, willpower, humanity, hunger, BP', () => {
    const d = deriveV5(goodSheet());
    expect(d.health).toBe(6); // Stamina 3 + 3
    expect(d.willpower).toBe(3); // Composure 2 + Resolve 1
    expect(d.humanity).toBe(6); // 7, Alleycat -1
    expect(d.hunger).toBe(1);
    expect(d.blood_potency).toBe(1); // 13th gen
  });
  it('applies ancilla and blood leech bonuses', () => {
    const d = deriveV5({ ...goodSheet(), age: 'ancilla', generation: 11, predatorType: 'Blood Leech' });
    expect(d.blood_potency).toBe(4); // 2 + 1 (ancilla) + 1 (blood leech), max 4
    expect(d.humanity).toBe(5); // 7 - 1 - 1
    expect(d.advantage_dots).toBe(9);
    expect(d.flaw_min_dots).toBe(4);
  });
});

describe('V5 whole sheet', () => {
  it('accepts a complete sheet', () => {
    expect(validateV5Sheet(goodSheet(), V5_DISCIPLINES)).toEqual({});
  });
  it('flags too many advantage dots and too few flaws', () => {
    const s = {
      ...goodSheet(),
      advantages: [{ name: 'Resources', dots: 5 }, { name: 'Haven', dots: 3 }],
      flaws: [],
    };
    const err = validateV5Sheet(s, V5_DISCIPLINES);
    expect(Object.values(err).join(' ')).toMatch(/at most 7/);
  });
  it('counts predator flaws toward the minimum', () => {
    const s = { ...goodSheet(), predatorType: 'Bagger', predatorDiscipline: 'Obfuscate', flaws: [] };
    expect(validateV5Sheet(s, V5_DISCIPLINES)).toEqual({});
  });
  it('forbids Ventrue farmers', () => {
    const s = {
      ...goodSheet(),
      clan: 'Ventrue',
      disciplines: [
        { name: 'Dominate', level: 2 },
        { name: 'Fortitude', level: 1 },
      ],
      predatorType: 'Farmer',
      predatorDiscipline: 'Animalism',
    };
    expect(Object.values(validateV5Sheet(s, V5_DISCIPLINES)).join(' ')).toMatch(/Ventrue cannot/);
  });
  it('needs 1-3 convictions with touchstones', () => {
    const s = { ...goodSheet(), convictions: [{ conviction: 'x', touchstone: '' }] };
    expect(Object.values(validateV5Sheet(s, V5_DISCIPLINES)).join(' ')).toMatch(/Touchstone/);
  });

  it('builds the storage payload', () => {
    const p = buildV5Payload({ ...goodSheet(), predatorSpecialty: 1 }); // Brawl (Grappling)
    expect(p.attributes.strength).toBe(4);
    expect(p.skills.physical.brawl).toBe(3);
    expect(p.skills.distribution).toBe('balanced');
    expect(p.skills.specialties).toEqual([
      { skill: 'brawl', name: 'Grappling' },
      { skill: 'brawl', name: 'Grappling', source: 'predator' },
    ]);
    expect(p.wod_meta.edition).toBe('v5');
    expect(p.wod_meta.generation).toBe(13);
    expect(p.wod_meta.health).toEqual({ max: 6, superficial: 0, aggravated: 0 });
    expect(p.wod_meta.willpower.max).toBe(3);
    expect(p.wod_meta.hunger).toBe(1);
    expect(p.wod_meta.advantages).toContainEqual({ name: 'Contacts (criminal)', dots: 3, kind: 'predator' });
    expect(p.wod_meta.touchstones).toEqual([{ name: 'Mia, my niece', conviction: 'Never harm a child' }]);
    expect(p.wod_meta.disciplines[0].powers).toEqual(['Lethal Body']);
    expect(p.merits_flaws.entries).toContainEqual({ name: 'Enemy', points: -2, note: 'flaw' });
  });

  it('turns a predator specialty in a 0-dot skill into a dot', () => {
    // Alleycat specialty 0 = Intimidation (Stickups); intimidation is 0 in balancedSkills
    const out = finalSkills(goodSheet());
    expect(out.skills.intimidation).toBe(1);
    expect(out.specialties.some((x) => x.source === 'predator')).toBe(false);
  });
});

describe('V5 fledgling Humanity option (V5.md §2.6 / §4 step 9)', () => {
  it('defaults to 7 and lets childer start at 8', () => {
    const base = { ...goodSheet(), predatorType: '', age: 'childer' };
    expect(deriveV5(base).humanity).toBe(7);
    expect(deriveV5({ ...base, fledglingHumanity: true }).humanity).toBe(8);
    // predator type still adjusts it (Alleycat -1)
    expect(deriveV5({ ...goodSheet(), age: 'childer', fledglingHumanity: true }).humanity).toBe(7);
  });
  it('does not apply to neonates or ancillae', () => {
    expect(deriveV5({ ...goodSheet(), predatorType: '', fledglingHumanity: true }).humanity).toBe(7);
  });
});

describe('V5 thin-blood Merits and Flaws (V5.md §2.7 / §4 step 2)', () => {
  const thinSheet = (merits, flaws) => ({
    ...goodSheet(),
    clan: 'Thin-blood',
    age: 'childer',
    generation: 14,
    disciplines: [],
    predatorType: '',
    predatorSpecialty: null,
    predatorDiscipline: '',
    thinBloodMerits: merits.map((name) => ({ name })),
    thinBloodFlaws: flaws.map((name) => ({ name })),
  });
  const advErr = (s) => validateV5Sheet(s, V5_DISCIPLINES)[V5_SECTION_IDS.advantages];

  it('needs 1-3 thin-blood Merits', () => {
    expect(advErr(thinSheet([], []))).toMatch(/1–3 thin-blood Merits/);
    expect(advErr(thinSheet(['a', 'b', 'c', 'd'], ['w', 'x', 'y', 'z']))).toMatch(/1–3/);
  });
  it('needs as many thin-blood Flaws as Merits', () => {
    expect(advErr(thinSheet(['Day Drinker', 'Lifelike'], ['Baby Teeth']))).toMatch(/as many thin-blood Flaws/);
    expect(validateV5Sheet(thinSheet(['Day Drinker'], ['Baby Teeth']), V5_DISCIPLINES)).toEqual({});
  });
  it('ignores the rule for other clans', () => {
    expect(validateThinBloodMeritsFlaws(goodSheet())).toBeNull();
  });
  it('stores them without dot value', () => {
    const p = buildV5Payload(thinSheet(['Day Drinker'], ['Baby Teeth']));
    expect(p.wod_meta.thin_blood_merits).toEqual(['Day Drinker']);
    expect(p.wod_meta.thin_blood_flaws).toEqual(['Baby Teeth']);
    expect(p.merits_flaws.entries).toContainEqual({ name: 'Day Drinker', points: 0, note: 'thin-blood merit' });
  });
});

describe('V5 discipline rows (forge display)', () => {
  const tremere = (predatorDiscipline) => ({
    clan: 'Tremere',
    disciplines: [
      { name: 'Blood Sorcery', level: 2, powers: ['Corrosive Vitae', 'Extinguish Vitae', 'Shape of Blood'] },
      { name: 'Auspex', level: 1, powers: [] },
    ],
    predatorType: 'Bagger',
    predatorDiscipline,
    extraPowers: { Obfuscate: ['Cloak of Shadows'] },
  });

  it('puts the predator dot on the matching pick, one power slot per final dot', () => {
    const rows = disciplineRows(tremere('Blood Sorcery'));
    expect(rows[0]).toMatchObject({ name: 'Blood Sorcery', pick: 0, base: 2, predator: 1, xp: 0, level: 3 });
    expect(rows[0].powers).toHaveLength(3);
    expect(rows[1]).toMatchObject({ name: 'Auspex', base: 1, predator: 0, level: 1 });
    expect(rows).toHaveLength(2);
    expect(finalDisciplines(tremere('Blood Sorcery'))[0]).toEqual({
      name: 'Blood Sorcery',
      level: 3,
      powers: ['Corrosive Vitae', 'Extinguish Vitae', 'Shape of Blood'],
    });
  });

  it('gives a predator Discipline outside the picks its own row with extraPowers', () => {
    const rows = disciplineRows(tremere('Obfuscate'));
    expect(rows[2]).toMatchObject({ name: 'Obfuscate', pick: null, base: 0, predator: 1, level: 1 });
    expect(finalDisciplines(tremere('Obfuscate'))[0].powers).toEqual(['Corrosive Vitae', 'Extinguish Vitae']);
    expect(finalDisciplines(tremere('Obfuscate'))[2]).toEqual({ name: 'Obfuscate', level: 1, powers: ['Cloak of Shadows'] });
  });

  it('keeps empty picks for the forge but leaves them out of the payload', () => {
    const s = { clan: 'Tremere', disciplines: [{ name: '', level: 2 }, { name: '', level: 1 }], predatorDiscipline: '' };
    expect(disciplineRows(s)).toHaveLength(2);
    expect(finalDisciplines(s)).toEqual([]);
  });

  it('gives thin-bloods no rows and no predator dot', () => {
    expect(disciplineRows({ clan: 'Thin-blood', disciplines: [], predatorDiscipline: 'Celerity' })).toEqual([]);
  });
});
