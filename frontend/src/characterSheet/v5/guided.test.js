import {
  DEFAULT_THRESHOLDS,
  NONE_OF_THESE,
  attributePrefill,
  distributionVote,
  eligibleClans,
  guidedQuestions,
  guidedResult,
  guidedThresholds,
  noneCount,
  predatorFits,
  scoreAnswers,
  skillPrefill,
} from './guided';
import { V5_ATTRIBUTE_KEYS, V5_ATTRIBUTE_SPREAD, V5_FREE_SPECIALTY_SKILLS, V5_SKILL_DISTRIBUTIONS, V5_SKILL_KEYS } from './constants';
import { normalizeCreationSettings } from './creationSettings';
import { applyV5Catalog, getV5Rules } from './rulesData';
import { validateV5Attributes, validateV5Skills } from './validation';

// The rules registry starts on src/rules/v5.json: 9 clans (Brujah … Caitiff, Thin-blood) and the
// corebook's 10 predator types (Bagger and Farmer forbidden to Ventrue, Farmer capped at BP 2).

const ANY = normalizeCreationSettings({});

/** A question with one option per weights object: options a, b, c… */
const q = (id, ...weights) => ({
  id,
  text: { en: id, el: id },
  options: weights.map((w, i) => ({ id: String.fromCharCode(97 + i), text: { en: `${id}${i}`, el: `${id}${i}` }, weights: w })),
});

const set = (questions, thresholds = { min_score_share: 0.3, min_lead: 2 }) => ({ version: 1, thresholds, questions });

const sorted = (values) => [...values].sort((a, b) => b - a);

describe('scoring', () => {
  const s = set([
    q('q1', { clan: { Brujah: 3, Gangrel: 1 }, skills: { brawl: 2 } }, { clan: { Toreador: 3 } }),
    q('q2', { clan: { Brujah: 2 }, predator: { Alleycat: 2 }, attributes: { physical: 1 } }, { clan: { Ventrue: 1 } }),
    q('q3', { clan: { Brujah: 'lots', Gangrel: -4, Toreador: 0 } }, { distribution: { jack: 1 } }),
  ]);

  test('sums the chosen options per weight group, in question order', () => {
    const out = scoreAnswers(s, { q1: 'a', q2: 'a', q3: 'b' });
    expect({ ...out.clan }).toEqual({ Brujah: 5, Gangrel: 1 });
    expect({ ...out.predator }).toEqual({ Alleycat: 2 });
    expect({ ...out.attributes }).toEqual({ physical: 1 });
    expect({ ...out.skills }).toEqual({ brawl: 2 });
    expect({ ...out.distribution }).toEqual({ jack: 1 });
    expect(out.picks.map((p) => `${p.question.id}:${p.option.id}`)).toEqual(['q1:a', 'q2:a', 'q3:b']);
  });

  test('"none of these", unknown options and weights that are not positive numbers count nothing', () => {
    const out = scoreAnswers(s, { q1: NONE_OF_THESE, q2: 'zz', q3: 'a' });
    expect({ ...out.clan }).toEqual({});
    expect(out.picks).toHaveLength(1);
    expect(noneCount(s, { q1: NONE_OF_THESE, q2: NONE_OF_THESE, q9: NONE_OF_THESE })).toBe(2);
  });

  test('a key from the file cannot reach Object.prototype', () => {
    const evil = set([JSON.parse('{"id":"q1","options":[{"id":"a","weights":{"clan":{"__proto__":3}}},{"id":"b"}]}')]);
    const out = scoreAnswers(evil, { q1: 'a' });
    // an own key of a prototype-less map, not a new prototype
    expect(Object.getPrototypeOf(out.clan)).toBeNull();
    expect(Object.getOwnPropertyDescriptor(out.clan, '__proto__').value).toBe(3);
  });

  test('questions without an id or two usable options are skipped', () => {
    const odd = { questions: [{ options: [] }, { id: 'one', options: [{ id: 'a' }] }, { id: 'two', options: [{ id: 'a' }, null, { id: 'b' }] }] };
    expect(guidedQuestions(odd).map((x) => [x.id, x.options.length])).toEqual([['two', 2]]);
    expect(guidedQuestions(null)).toEqual([]);
  });

  test('thresholds fall back to the defaults when missing or out of range', () => {
    expect(guidedThresholds({})).toEqual(DEFAULT_THRESHOLDS);
    expect(guidedThresholds({ thresholds: { min_score_share: 1.5, min_lead: -1 } })).toEqual(DEFAULT_THRESHOLDS);
    expect(guidedThresholds({ thresholds: { min_score_share: '0.5', min_lead: null } })).toEqual(DEFAULT_THRESHOLDS);
    expect(guidedThresholds({ thresholds: { min_score_share: 0.5, min_lead: 0 } })).toEqual({ min_score_share: 0.5, min_lead: 0 });
  });
});

describe('clan and predator type', () => {
  test('a clear answer suggests its clan and predator type, with the answers behind them', () => {
    const s = set([
      q('q1', { clan: { Brujah: 3, Gangrel: 1 }, predator: { Alleycat: 2 } }, { clan: { Toreador: 3 } }),
      q('q2', { clan: { Brujah: 2 }, predator: { Siren: 1 } }, { clan: { Ventrue: 3 } }),
      q('q3', { clan: { Brujah: 3 }, predator: { Alleycat: 1 } }, {}),
    ]);
    const r = guidedResult(s, { q1: 'a', q2: 'a', q3: 'a' }, ANY);
    expect(r.offPath).toBe(false);
    expect(r).toMatchObject({ clan: 'Brujah', predator: 'Alleycat', age: 'neonate' });
    expect(r.share).toBeCloseTo(8 / 9);
    expect(r.lead).toBe(7);
    expect(r.why.clan.map((w) => [w.question, w.option, w.points])).toEqual([
      ['q1', 'a', 3],
      ['q3', 'a', 3],
      ['q2', 'a', 2],
    ]);
    expect(r.why.clan[0].text).toEqual({ en: 'q10', el: 'q10' });
    expect(r.why.predator.map((w) => w.question)).toEqual(['q1', 'q3']);
    expect(r.prefill).toMatchObject({ clan: 'Brujah', predatorType: 'Alleycat', age: 'neonate', skillDistribution: 'balanced' });
  });

  test('a tie at the top has no lead: off the path, unless min_lead is 0 (then catalog order)', () => {
    const s = (th) => set([q('q1', { clan: { Toreador: 3, Brujah: 3 } }, {}), q('q2', { clan: { Brujah: 1, Toreador: 1 } }, {})], th);
    const answers = { q1: 'a', q2: 'a' };
    expect(guidedResult(s(), answers, ANY)).toMatchObject({ offPath: true, reason: 'unclear', lead: 0 });
    // Brujah comes before Toreador in the rules, so it wins the tie
    expect(guidedResult(s({ min_score_share: 0.3, min_lead: 0 }), answers, ANY)).toMatchObject({ offPath: false, clan: 'Brujah' });
  });

  test('predator types with the same points go in catalog order; none with points means none suggested', () => {
    const s = set([
      q('q1', { clan: { Gangrel: 3 }, predator: { Siren: 2, Cleaver: 2 } }, {}),
      q('q2', { clan: { Gangrel: 3 } }, {}),
    ]);
    expect(guidedResult(s, { q1: 'a', q2: 'a' }, ANY).predator).toBe('Cleaver'); // Cleaver is listed before Siren
    const noPred = guidedResult(s, { q1: 'b', q2: 'a' }, ANY);
    expect(noPred).toMatchObject({ offPath: false, clan: 'Gangrel', predator: null });
    expect(noPred.why.predator).toEqual([]);
    expect(noPred.prefill.predatorType).toBe('');
  });

  test('a clan the Storyteller left out is skipped; the next allowed clan is suggested when it stands out', () => {
    const s = set([
      q('q1', { clan: { Nosferatu: 3, Malkavian: 2 } }, {}),
      q('q2', { clan: { Malkavian: 3 } }, {}),
      q('q3', { clan: { Nosferatu: 1, Malkavian: 1 } }, {}),
    ]);
    const answers = { q1: 'a', q2: 'a', q3: 'a' };
    expect(guidedResult(s, answers, ANY).clan).toBe('Malkavian'); // 6 against 4
    const noMalk = normalizeCreationSettings({ allowed_clans: ['Nosferatu', 'Brujah'] });
    expect(eligibleClans(noMalk)).toEqual(['Brujah', 'Nosferatu']);
    // Nosferatu has 4 of 10 points (0.4) and leads Brujah by 4
    expect(guidedResult(s, answers, noMalk)).toMatchObject({ offPath: false, clan: 'Nosferatu' });
  });

  test('when the answers point at a clan this chronicle does not offer, the path ends', () => {
    const s = set([q('q1', { clan: { Tremere: 3, Ventrue: 1 } }, {}), q('q2', { clan: { Tremere: 3 } }, {})]);
    const onlyVentrue = normalizeCreationSettings({ allowed_clans: ['Ventrue', 'Brujah'] });
    // Ventrue would lead by 1 with a share of 1/7: both below the thresholds
    expect(guidedResult(s, { q1: 'a', q2: 'a' }, onlyVentrue)).toMatchObject({ offPath: true, reason: 'not_allowed' });
    expect(guidedResult(s, { q1: 'b', q2: 'b' }, onlyVentrue)).toMatchObject({ offPath: true, reason: 'unclear' });
  });

  test('Thin-blood needs childer allowed: thin-bloods are always childer', () => {
    const neonatesOnly = normalizeCreationSettings({ allowed_ages: ['neonate'] });
    expect(eligibleClans(neonatesOnly)).not.toContain('Thin-blood');
    expect(eligibleClans(ANY)).toContain('Thin-blood');
    const s = set([q('q1', { clan: { 'Thin-blood': 3 }, predator: { Cleaver: 1 } }, {}), q('q2', { clan: { 'Thin-blood': 3 } }, {})]);
    expect(guidedResult(s, { q1: 'a', q2: 'a' }, ANY)).toMatchObject({ clan: 'Thin-blood', age: 'childer', predator: 'Cleaver' });
    expect(guidedResult(s, { q1: 'a', q2: 'a' }, neonatesOnly)).toMatchObject({ offPath: true, reason: 'not_allowed' });
  });

  test('a predator type the clan is forbidden is skipped for the next one', () => {
    const s = set([
      q('q1', { clan: { Ventrue: 3 }, predator: { Farmer: 3, Bagger: 2, Consensualist: 1 } }, {}),
      q('q2', { clan: { Ventrue: 3 } }, {}),
    ]);
    expect(guidedResult(s, { q1: 'a', q2: 'a' }, ANY)).toMatchObject({ clan: 'Ventrue', predator: 'Consensualist' });
    const farmer = getV5Rules().predators.find((p) => p.name === 'Farmer');
    expect(predatorFits(ANY, 'Ventrue', farmer)).toBe(false);
    expect(predatorFits(ANY, 'Gangrel', farmer)).toBe(true);
  });

  test('a predator type the Storyteller left out is skipped', () => {
    const s = set([q('q1', { clan: { Toreador: 3 }, predator: { Siren: 3, 'Scene Queen': 1 } }, {}), q('q2', { clan: { Toreador: 3 } }, {})]);
    const noSirens = normalizeCreationSettings({ allowed_predators: ['Scene Queen', 'Alleycat'] });
    expect(guidedResult(s, { q1: 'a', q2: 'a' }, noSirens).predator).toBe('Scene Queen');
  });

  test("Farmer's Blood Potency cap: not for a chronicle of ancillae (they start at Blood Potency 3)", () => {
    const farmer = getV5Rules().predators.find((p) => p.name === 'Farmer');
    expect(predatorFits(normalizeCreationSettings({ allowed_ages: ['ancilla'] }), 'Gangrel', farmer)).toBe(false);
    expect(predatorFits(normalizeCreationSettings({ allowed_ages: ['childer', 'ancilla'] }), 'Gangrel', farmer)).toBe(true);
  });

  test('none of these twice leaves the path, however clear the rest; once is fine', () => {
    const s = set([
      q('q1', { clan: { Brujah: 3 } }, {}),
      q('q2', { clan: { Brujah: 3 } }, {}),
      q('q3', { clan: { Brujah: 3 } }, {}),
      q('q4', { clan: { Brujah: 3 } }, {}),
    ]);
    expect(guidedResult(s, { q1: 'a', q2: 'a', q3: NONE_OF_THESE, q4: 'a' }, ANY)).toMatchObject({ offPath: false, clan: 'Brujah' });
    expect(guidedResult(s, { q1: 'a', q2: NONE_OF_THESE, q3: NONE_OF_THESE, q4: 'a' }, ANY)).toEqual({
      offPath: true,
      reason: 'none',
      share: 0,
      lead: 0,
    });
  });

  test('no answers at all, or answers without clan points, are off the path', () => {
    const s = set([q('q1', { skills: { brawl: 3 } }, {}), q('q2', {}, {})]);
    expect(guidedResult(s, {}, ANY)).toMatchObject({ offPath: true, reason: 'unclear' });
    expect(guidedResult(s, { q1: 'a', q2: 'a' }, ANY)).toMatchObject({ offPath: true, reason: 'unclear' });
  });
});

describe('thresholds', () => {
  // Brujah 3 + 3, Gangrel 3, Toreador 1 → share 6/10, lead 3
  const s = (th) =>
    set([q('q1', { clan: { Brujah: 3, Toreador: 1 } }, {}), q('q2', { clan: { Brujah: 3 } }, {}), q('q3', { clan: { Gangrel: 3 } }, {})], th);
  const answers = { q1: 'a', q2: 'a', q3: 'a' };

  test('a share under min_score_share is off the path, at it is on', () => {
    expect(guidedResult(s({ min_score_share: 0.65, min_lead: 2 }), answers, ANY)).toMatchObject({ offPath: true, reason: 'unclear' });
    expect(guidedResult(s({ min_score_share: 6 / 10, min_lead: 2 }), answers, ANY)).toMatchObject({ offPath: false, clan: 'Brujah' });
  });

  test('a lead under min_lead is off the path, at it is on', () => {
    expect(guidedResult(s({ min_score_share: 0.3, min_lead: 4 }), answers, ANY)).toMatchObject({ offPath: true, lead: 3 });
    expect(guidedResult(s({ min_score_share: 0.3, min_lead: 3 }), answers, ANY)).toMatchObject({ offPath: false, lead: 3 });
  });
});

describe('ancilla-only predator types (from the catalog)', () => {
  beforeAll(() =>
    applyV5Catalog({
      books: [],
      disciplines: [],
      clans: [
        { id: 'clan:brujah', name: 'Brujah', disciplines: [] },
        { id: 'clan:thin-blood', name: 'Thin-blood', disciplines: [] },
      ],
      predator_types: [
        { id: 'predator:tithe-collector', name: 'Tithe Collector', ancilla_only: true },
        { id: 'predator:alleycat', name: 'Alleycat' },
      ],
    })
  );
  afterAll(() => applyV5Catalog(null));

  const s = (clan) => set([q('q1', { clan: { [clan]: 3 }, predator: { 'Tithe Collector': 3, Alleycat: 1 } }, {}), q('q2', { clan: { [clan]: 3 } }, {})]);
  const answers = { q1: 'a', q2: 'a' };

  test('suggested only where ancillae are allowed, and the prefill starts as an ancilla', () => {
    const r = guidedResult(s('Brujah'), answers, ANY);
    expect(r).toMatchObject({ predator: 'Tithe Collector', age: 'ancilla' });
    expect(r.prefill.age).toBe('ancilla');
    const noAncillae = normalizeCreationSettings({ allowed_ages: ['childer', 'neonate'] });
    expect(guidedResult(s('Brujah'), answers, noAncillae)).toMatchObject({ predator: 'Alleycat', age: 'neonate' });
  });

  test('never for thin-bloods', () => {
    expect(guidedResult(s('Thin-blood'), answers, ANY)).toMatchObject({ clan: 'Thin-blood', predator: 'Alleycat', age: 'childer' });
  });
});

describe('prefill', () => {
  test('the strongest category takes 4, 3, 3, the next 3, 2, 2, the last 2, 2, 1', () => {
    const { attributes, categories } = attributePrefill({ social: 3, mental: 1, wits: 1, manipulation: 2 });
    expect(categories).toEqual(['social', 'mental', 'physical']);
    // manipulation has its own points, so it takes the 4; then sheet order
    expect(attributes).toMatchObject({ manipulation: 4, charisma: 3, composure: 3 });
    expect(attributes).toMatchObject({ wits: 3, intelligence: 2, resolve: 2 });
    expect(attributes).toMatchObject({ strength: 2, dexterity: 2, stamina: 1 });
  });

  test('no attribute points: physical, social, mental in sheet order', () => {
    const { attributes, categories } = attributePrefill({});
    expect(categories).toEqual(['physical', 'social', 'mental']);
    expect(V5_ATTRIBUTE_KEYS.map((k) => attributes[k])).toEqual([4, 3, 3, 3, 2, 2, 2, 2, 1]);
  });

  test("an Attribute's points count for its category too", () => {
    expect(attributePrefill({ physical: 2, intelligence: 1, wits: 1, resolve: 1 }).categories).toEqual(['mental', 'physical', 'social']);
  });

  test('distribution by vote, balanced without votes or on a tie', () => {
    expect(distributionVote({})).toBe('balanced');
    expect(distributionVote({ jack: 2, specialist: 2 })).toBe('balanced');
    expect(distributionVote({ jack: 1, specialist: 2 })).toBe('specialist');
    expect(distributionVote({ jack: 3, balanced: 1 })).toBe('jack');
  });

  test('the skills with the most points get the highest ratings', () => {
    // specialist: one 4, three 3s, three 2s, three 1s
    const skills = skillPrefill({ occult: 5, academics: 3, brawl: 1 }, 'specialist', ['mental', 'social', 'physical']);
    expect(skills.occult).toBe(4);
    expect(skills.academics).toBe(3);
    expect(skills.brawl).toBe(3); // any points beat none
    // the rest go to the first category's skills (mental here), in sheet order, then the next category's
    expect(skills.awareness).toBe(3);
    expect([skills.finance, skills.investigation, skills.medicine]).toEqual([2, 2, 2]);
    expect([skills.politics, skills.technology, skills.animal_ken]).toEqual([1, 1, 1]);
    expect(skills.science).toBe(0); // no points: it would ask for a free specialty, so it comes last
    expect(skills.athletics).toBe(0);
  });

  test('Academics, Craft, Performance and Science get dots only when the answers gave them points', () => {
    Object.keys(V5_SKILL_DISTRIBUTIONS).forEach((name) => {
      [['mental', 'social', 'physical'], ['physical', 'social', 'mental'], ['social', 'mental', 'physical']].forEach((cats) => {
        const skills = skillPrefill({}, name, cats);
        // jack of all trades rates 19 skills: the 23 others are always enough
        V5_FREE_SPECIALTY_SKILLS.forEach((k) => expect(skills[k]).toBe(0));
        expect(validateV5Skills(skills, name)).toBeNull();
      });
    });
    expect(skillPrefill({ academics: 1 }, 'balanced').academics).toBeGreaterThan(0);
    expect(skillPrefill({ performance: 2, brawl: 3 }, 'specialist').performance).toBe(3);
  });

  test('the ratings are exactly the distribution, for every distribution and many point mixes', () => {
    let seed = 7;
    const rnd = () => {
      seed = (seed * 1103515245 + 12345) % 2147483648;
      return seed / 2147483648;
    };
    Object.entries(V5_SKILL_DISTRIBUTIONS).forEach(([name, dist]) => {
      for (let i = 0; i < 40; i += 1) {
        const points = Object.fromEntries(V5_SKILL_KEYS.filter(() => rnd() < 0.4).map((k) => [k, Math.floor(rnd() * 4) + 1]));
        const skills = skillPrefill(points, name, ['social', 'physical', 'mental']);
        expect(validateV5Skills(skills, name)).toBeNull();
        V5_FREE_SPECIALTY_SKILLS.filter((k) => !points[k]).forEach((k) => expect(skills[k]).toBe(0));
        const want = Object.entries(dist.counts).flatMap(([r, n]) => Array(n).fill(Number(r)));
        expect(sorted(Object.values(skills).filter((v) => v > 0))).toEqual(sorted(want));
        expect(Object.keys(skills).sort()).toEqual([...V5_SKILL_KEYS].sort());
      }
    });
  });

  test('the attribute spread is exact for many point mixes', () => {
    let seed = 11;
    const rnd = () => {
      seed = (seed * 1103515245 + 12345) % 2147483648;
      return seed / 2147483648;
    };
    const keys = ['physical', 'social', 'mental', ...V5_ATTRIBUTE_KEYS];
    for (let i = 0; i < 60; i += 1) {
      const points = Object.fromEntries(keys.filter(() => rnd() < 0.5).map((k) => [k, Math.floor(rnd() * 3) + 1]));
      const { attributes } = attributePrefill(points);
      expect(validateV5Attributes(attributes)).toBeNull();
      expect(sorted(Object.values(attributes))).toEqual(sorted(V5_ATTRIBUTE_SPREAD));
    }
  });

  test('an unknown distribution name falls back to balanced', () => {
    expect(validateV5Skills(skillPrefill({}, 'nonsense'), 'balanced')).toBeNull();
  });

  test('the whole result carries a prefill the forge accepts', () => {
    const s = set([
      q('q1', { clan: { Tremere: 3 }, predator: { Bagger: 2 }, attributes: { mental: 2, intelligence: 1 }, skills: { occult: 3, academics: 1 }, distribution: { specialist: 1 } }, {}),
      q('q2', { clan: { Tremere: 3 }, skills: { investigation: 2 }, distribution: { specialist: 1 } }, {}),
    ]);
    const r = guidedResult(s, { q1: 'a', q2: 'a' }, ANY);
    expect(r).toMatchObject({ clan: 'Tremere', predator: 'Bagger', distribution: 'specialist', categories: ['mental', 'physical', 'social'] });
    expect(r.skillFocus).toEqual(['occult', 'investigation', 'academics']); // only skills the answers named, most points first
    expect(r.prefill.attributes.intelligence).toBe(4);
    expect(r.prefill.skills.occult).toBe(4);
    expect(validateV5Attributes(r.prefill.attributes)).toBeNull();
    expect(validateV5Skills(r.prefill.skills, r.prefill.skillDistribution)).toBeNull();
  });
});
