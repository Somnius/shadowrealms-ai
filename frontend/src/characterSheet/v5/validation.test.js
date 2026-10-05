import {
  V5_DISCIPLINES,
  V5_SECTION_IDS,
  V5_SKILL_DISTRIBUTIONS,
  generationBloodPotency,
} from './constants';
import {
  attributeSpreadStatus,
  buildV5Payload,
  bloodSorceryLevel,
  deriveV5,
  disciplineRows,
  disciplineXpMultiplier,
  duplicateSpecialtyError,
  emptyV5Attributes,
  experienceMeta,
  finalAttributes,
  emptyV5Skills,
  finalDisciplines,
  finalRituals,
  finalSkills,
  predatorDisciplineOptions,
  startingRitualAllowed,
  startingXp,
  validateV5Attributes,
  validateV5Experience,
  xpLedger,
  xpPreview,
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

describe('V5 starting ritual', () => {
  const tremere = (extra) => ({
    ...goodSheet(),
    clan: 'Tremere',
    disciplines: [
      { name: 'Auspex', level: 2, powers: [] },
      { name: 'Dominate', level: 1, powers: [] },
    ],
    predatorType: 'Bagger',
    predatorSpecialty: 0,
    predatorDiscipline: 'Obfuscate',
    ...extra,
  });

  it('needs at least one dot of Blood Sorcery, the predator dot counts', () => {
    expect(startingRitualAllowed(tremere())).toBe(false);
    expect(startingRitualAllowed(tremere({ predatorDiscipline: 'Blood Sorcery' }))).toBe(true);
    expect(bloodSorceryLevel(tremere({ predatorDiscipline: 'Blood Sorcery' }))).toBe(1);
    expect(
      startingRitualAllowed(tremere({ disciplines: [{ name: 'Blood Sorcery', level: 2 }, { name: 'Auspex', level: 1 }] }))
    ).toBe(true);
  });

  it('is saved as a Level 1 ritual only when allowed and named', () => {
    const withBs = tremere({ predatorDiscipline: 'Blood Sorcery', startingRitual: '  Ward against Ghouls ' });
    expect(finalRituals(withBs)).toEqual([{ name: 'Ward against Ghouls', level: 1, source: 'creation' }]);
    expect(buildV5Payload(withBs).wod_meta.rituals).toEqual([{ name: 'Ward against Ghouls', level: 1, source: 'creation' }]);
    expect(finalRituals(tremere({ startingRitual: 'Ward against Ghouls' }))).toEqual([]);
    expect(finalRituals(tremere({ predatorDiscipline: 'Blood Sorcery', startingRitual: '   ' }))).toEqual([]);
    expect(buildV5Payload(goodSheet()).wod_meta.rituals).toBeUndefined();
  });

  it('is dropped from the payload when a predator type change takes Blood Sorcery to 0', () => {
    const before = tremere({ predatorDiscipline: 'Blood Sorcery', startingRitual: 'Ward against Ghouls' });
    expect(buildV5Payload(before).wod_meta.rituals).toHaveLength(1);
    // The forge resets the predator Discipline when the type changes; the typed name stays in state.
    const after = { ...before, predatorType: 'Alleycat', predatorSpecialty: null, predatorDiscipline: '' };
    expect(bloodSorceryLevel(after)).toBe(0);
    expect(buildV5Payload(after).wod_meta.rituals).toBeUndefined();
  });
});

describe('V5 starting experience', () => {
  const buy = (extra, xpPurchases) => ({ ...goodSheet(), ...extra, xpPurchases });
  const xpErr = (s) => validateV5Sheet(s, V5_DISCIPLINES)[V5_SECTION_IDS.experience];

  it('gives neonates 15 XP, ancillae 35, childer and thin-bloods none', () => {
    expect(startingXp({ age: 'neonate' })).toBe(15);
    expect(startingXp({ age: 'ancilla' })).toBe(35);
    expect(startingXp({ age: 'childer' })).toBe(0);
    expect(startingXp({ age: 'neonate', clan: 'Thin-blood' })).toBe(0);
  });

  it('prices dots one at a time at the new rating (Resolve 2 → 3 is 15)', () => {
    const s = buy({ attributes: { ...goodAttrs(), resolve: 2, wits: 1 } }, [{ kind: 'attribute', trait: 'resolve' }]);
    expect(xpLedger(s).log).toEqual([{ kind: 'attribute', trait: 'resolve', what: 'Resolve', from: 2, to: 3, cost: 15, purchase: 0 }]);
    const two = xpLedger(buy({}, [{ kind: 'skill', trait: 'finance' }, { kind: 'skill', trait: 'finance' }]));
    expect(two.log.map((e) => [e.from, e.to, e.cost])).toEqual([[0, 1, 3], [1, 2, 6]]);
    expect(two).toMatchObject({ total: 15, spent: 9, unspent: 6 });
  });

  it('prices Disciplines as clan 5, other 7, Caitiff 6, counting the predator dot', () => {
    expect(disciplineXpMultiplier({ clan: 'Brujah' }, 'Potence')).toBe(5);
    expect(disciplineXpMultiplier({ clan: 'Brujah' }, 'Auspex')).toBe(7);
    expect(disciplineXpMultiplier({ clan: 'Caitiff' }, 'Auspex')).toBe(6);
    // Brujah: Celerity 1 from Alleycat → 2 costs 2 × 5
    const l = xpLedger(buy({}, [{ kind: 'discipline', trait: 'Celerity' }]));
    expect(l.log[0]).toMatchObject({ from: 1, to: 2, cost: 10 });
    const out = xpLedger(buy({}, [{ kind: 'discipline', trait: 'Auspex' }]));
    expect(out.log[0]).toMatchObject({ from: 0, to: 1, cost: 7 });
    expect(finalDisciplines(buy({}, [{ kind: 'discipline', trait: 'Auspex' }])).find((d) => d.name === 'Auspex').level).toBe(1);
  });

  it('charges 3 per specialty, on a Skill with a dot (an XP dot counts)', () => {
    const s = buy({}, [{ kind: 'specialty', skill: 'brawl', trait: 'Biting' }]);
    expect(xpLedger(s).spent).toBe(3);
    expect(xpErr(s)).toBeUndefined();
    expect(validateV5Experience(buy({}, [{ kind: 'specialty', skill: 'finance', trait: 'Stocks' }]))).toBe(
      'Finance needs at least one dot for a specialty.'
    );
    expect(
      validateV5Experience(buy({}, [{ kind: 'skill', trait: 'finance' }, { kind: 'specialty', skill: 'finance', trait: 'Stocks' }]))
    ).toBeNull();
    expect(validateV5Experience(buy({}, [{ kind: 'specialty', skill: 'brawl', trait: ' ' }]))).toBe('Name the Brawl specialty.');
  });

  it('prices rituals at level × 3, up to the final Blood Sorcery rating', () => {
    const tremere = (xp) =>
      buy(
        {
          clan: 'Tremere',
          disciplines: [{ name: 'Blood Sorcery', level: 2, powers: [] }, { name: 'Auspex', level: 1, powers: [] }],
          predatorType: 'Bagger',
          predatorDiscipline: 'Obfuscate',
        },
        xp
      );
    expect(xpLedger(tremere([{ kind: 'ritual', trait: 'Blood Walk', level: 2 }])).log[0]).toMatchObject({ from: 0, to: 2, cost: 6 });
    expect(validateV5Experience(tremere([{ kind: 'ritual', trait: 'Deflection of Wooden Doom', level: 3 }]))).toBe(
      'A level 3 ritual needs Blood Sorcery 3 (you have 2).'
    );
    // Blood Sorcery 2 → 3 (15) then a level 3 ritual (9) is 24 > 15
    const both = tremere([{ kind: 'discipline', trait: 'Blood Sorcery' }, { kind: 'ritual', trait: 'Deflection of Wooden Doom', level: 3 }]);
    expect(validateV5Experience(both)).toBe('Starting experience overspent: 24 of 15 XP.');
    expect(validateV5Experience({ ...both, age: 'ancilla', generation: 11 })).toBeNull();
    expect(validateV5Experience(tremere([{ kind: 'ritual', trait: '', level: 1 }]))).toBe('Name each ritual bought with XP.');
    expect(validateV5Experience(tremere([{ kind: 'ritual', trait: 'X', level: 0 }]))).toBe('Rituals are level 1 to 5.');
  });

  it('allows unspent XP, refuses overspending, dots above 5 and XP for childer', () => {
    expect(xpErr(buy({}, []))).toBeUndefined();
    expect(xpErr(buy({}, [{ kind: 'attribute', trait: 'resolve' }]))).toBeUndefined(); // 2 → costs 10
    const over = buy({}, [{ kind: 'attribute', trait: 'resolve' }, { kind: 'attribute', trait: 'resolve' }]); // 10 + 15
    expect(xpErr(over)).toBe('Starting experience overspent: 25 of 15 XP.');
    const five = buy({ age: 'ancilla', generation: 11 }, [{ kind: 'attribute', trait: 'strength' }, { kind: 'attribute', trait: 'strength' }]);
    expect(validateV5Experience(five)).toBe("Strength can't go above 5 dots.");
    expect(xpErr(buy({ age: 'childer' }, [{ kind: 'skill', trait: 'finance' }]))).toBe('This age has no starting experience to spend.');
    expect(validateV5Experience(buy({}, [{ kind: 'discipline', trait: 'Thin-Blood Alchemy' }]))).toBe(
      'One XP purchase is not something this step can buy.'
    );
  });

  it('previews the cost and the problem of one more purchase', () => {
    const s = buy({}, [{ kind: 'attribute', trait: 'resolve' }]);
    expect(xpPreview(s, { kind: 'skill', trait: 'finance' })).toEqual({ cost: 3, error: null });
    expect(xpPreview(s, { kind: 'attribute', trait: 'resolve' })).toEqual({
      cost: 15,
      error: 'Starting experience overspent: 25 of 15 XP.',
    });
  });

  it('puts XP dots in the payload and records wod_meta.experience', () => {
    const s = buy({ age: 'ancilla', generation: 11 }, [
      { kind: 'attribute', trait: 'resolve' },
      { kind: 'skill', trait: 'finance' },
      { kind: 'specialty', skill: 'finance', trait: ' Stocks ' },
      { kind: 'discipline', trait: 'Auspex' },
    ]);
    expect(finalAttributes(s).resolve).toBe(2);
    const p = buildV5Payload(s);
    expect(p.attributes.resolve).toBe(2);
    expect(p.wod_meta.willpower.max).toBe(4); // Composure 2 + Resolve 2
    expect(p.skills.mental.finance).toBe(1);
    expect(p.skills.specialties).toContainEqual({ skill: 'finance', name: 'Stocks', source: 'xp' });
    expect(p.wod_meta.disciplines.find((d) => d.name === 'Auspex')).toEqual({ name: 'Auspex', level: 1, powers: [] });
    expect(p.wod_meta.experience).toEqual({
      total: 35,
      spent: 23,
      unspent: 12,
      log: [
        { kind: 'attribute', trait: 'resolve', what: 'Resolve', from: 1, to: 2, cost: 10 },
        { kind: 'skill', trait: 'finance', what: 'Finance', from: 0, to: 1, cost: 3 },
        { kind: 'specialty', trait: 'Stocks', skill: 'finance', what: 'Finance specialty: Stocks', from: 0, to: 1, cost: 3 },
        { kind: 'discipline', trait: 'Auspex', what: 'Auspex', from: 0, to: 1, cost: 7 },
      ],
    });
    expect(experienceMeta(goodSheet())).toEqual({ total: 15, spent: 0, unspent: 15, log: [] });
    expect(buildV5Payload({ ...goodSheet(), age: 'childer' }).wod_meta.experience).toBeUndefined();
  });

  it('marks XP rituals with source xp', () => {
    const s = buy(
      {
        clan: 'Tremere',
        disciplines: [{ name: 'Blood Sorcery', level: 2, powers: [] }, { name: 'Auspex', level: 1, powers: [] }],
        predatorType: 'Bagger',
        predatorDiscipline: 'Obfuscate',
        startingRitual: 'Wake with Evening\'s Freshness',
      },
      [{ kind: 'ritual', trait: 'Blood Walk', level: 2 }]
    );
    expect(buildV5Payload(s).wod_meta.rituals).toEqual([
      { name: "Wake with Evening's Freshness", level: 1, source: 'creation' },
      { name: 'Blood Walk', level: 2, source: 'xp' },
    ]);
  });
});

describe('V5 starting experience: review fixes', () => {
  const buy = (extra, xpPurchases) => ({ ...goodSheet(), ...extra, xpPurchases });
  const tremere = (extra, xp) =>
    buy(
      {
        clan: 'Tremere',
        disciplines: [{ name: 'Blood Sorcery', level: 2, powers: [] }, { name: 'Auspex', level: 1, powers: [] }],
        predatorType: 'Bagger',
        predatorDiscipline: 'Obfuscate',
        ...extra,
      },
      xp
    );
  const ritual1 = (i) => ({ kind: 'ritual', trait: `Ritual ${i}`, level: 1 });

  it('caps rituals at 12, which an ancilla can just reach (free one + 11 on 35 XP)', () => {
    const eleven = Array.from({ length: 11 }, (_, i) => ritual1(i));
    const ok = tremere({ age: 'ancilla', generation: 11, startingRitual: 'Free one' }, eleven);
    expect(xpLedger(ok).spent).toBe(33);
    expect(validateV5Experience(ok)).toBeNull();
    expect(buildV5Payload(ok).wod_meta.rituals).toHaveLength(12);
    const thirteen = tremere({ age: 'ancilla', generation: 11, startingRitual: 'Free one' }, [...eleven, ritual1(11)]);
    expect(xpLedger(thirteen).errors).toContain('At most 12 rituals (you have 13).');
  });

  it('tags each log entry with its purchase index, even after an unknown purchase', () => {
    const l = xpLedger(buy({}, [{ kind: 'nonsense' }, { kind: 'skill', trait: 'finance' }]));
    expect(l.log).toHaveLength(1);
    expect(l.log[0].purchase).toBe(1);
    expect(experienceMeta(buy({}, [{ kind: 'skill', trait: 'finance' }])).log[0]).not.toHaveProperty('purchase');
  });

  it('previews a second copy of a problem that is already there', () => {
    const s = tremere({}, [{ kind: 'ritual', trait: 'Too high', level: 3 }]);
    expect(xpPreview(s, { kind: 'ritual', trait: 'Also too high', level: 3 }).error).toBe(
      'A level 3 ritual needs Blood Sorcery 3 (you have 2).'
    );
  });

  it('refuses duplicate specialties on a skill, case-insensitive, also against free and predator ones', () => {
    expect(duplicateSpecialtyError([{ skill: 'brawl', name: 'Grappling' }, { skill: 'brawl', name: ' grappling ' }])).toBe(
      'Brawl already has the grappling specialty.'
    );
    expect(duplicateSpecialtyError([{ skill: 'brawl', name: 'Grappling' }, { skill: 'melee', name: 'Grappling' }])).toBeNull();
    // free Brawl (Grappling) vs XP brawl GRAPPLING
    expect(validateV5Experience(buy({}, [{ kind: 'specialty', skill: 'brawl', trait: 'GRAPPLING' }]))).toBe(
      'Brawl already has the GRAPPLING specialty.'
    );
    // two identical XP ones
    const twice = buy({}, [
      { kind: 'specialty', skill: 'stealth', trait: 'Crowds' },
      { kind: 'specialty', skill: 'stealth', trait: 'crowds' },
    ]);
    expect(validateV5Experience(twice)).toBe('Stealth already has the crowds specialty.');
    // Alleycat's Brawl (Grappling) duplicates the free one
    expect(validateV5Sheet({ ...goodSheet(), predatorSpecialty: 1 }, V5_DISCIPLINES)[V5_SECTION_IDS.skills]).toBe(
      'Brawl already has the Grappling specialty.'
    );
  });

  it('a first XP dot in Academics, Craft, Performance or Science needs its free specialty', () => {
    const bare = buy({}, [{ kind: 'skill', trait: 'academics' }]);
    expect(validateV5Experience(bare)).toBe('Academics comes with a free specialty — name it.');
    const named = buy({}, [{ kind: 'skill', trait: 'academics', specialty: 'History' }]);
    expect(validateV5Experience(named)).toBeNull();
    expect(xpLedger(named).log[0]).toMatchObject({ from: 0, to: 1, cost: 3, specialty: 'History' });
    const p = buildV5Payload(named);
    expect(p.skills.mental.academics).toBe(1);
    expect(p.skills.specialties).toContainEqual({ skill: 'academics', name: 'History' });
    // not for a second dot, nor for other skills
    expect(validateV5Experience(buy({}, [{ kind: 'skill', trait: 'finance' }]))).toBeNull();
    expect(xpPreview(named, { kind: 'skill', trait: 'academics' })).toEqual({ cost: 6, error: null });
  });
});
