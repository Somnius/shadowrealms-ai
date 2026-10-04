/**
 * Classic (Revised) creation rules — docs/rules/CLASSIC_REVISED.md.
 * Manual QA: create one VtM / WtA / MtA character locally; confirm POST payload includes
 * attributes, skills (optional custom.*), merits_flaws.entries + notes, and wod_meta
 * (disciplines; rage/gnosis/gifts_notes; spheres).
 */
import { DISCIPLINE_PRESETS, MTA_SPHERES } from './constants';
import {
  abilityDotBreakdown,
  abilityPools,
  attributePools,
  computeClassicFreebies,
  deriveClassicMorality,
  finalVirtues,
  emptyAbilityMap,
  emptyAttrMap,
  emptySphereMap,
  validateAbilitySpread,
  validateAttributeSpread,
  validateFreebies,
  validateSpheres,
  validateVirtues,
} from './validation';
import { CLASSIC_DISCIPLINES, FREEBIE_COSTS } from '../rules/classicRules';

/** Physical 7 / Social 5 / Mental 3 added on top of the free dot: totals 10 / 8 / 6. */
const goodAttrs = () => {
  const a = emptyAttrMap();
  Object.assign(a, {
    strength: 4,
    dexterity: 3,
    stamina: 3, // physical 10 (7 added)
    charisma: 3,
    manipulation: 3,
    appearance: 2, // social 8 (5 added)
    perception: 2,
    intelligence: 2,
    wits: 2, // mental 6 (3 added)
  });
  return a;
};

/** Talents 13 / Skills 9 / Knowledges 5, nothing above 3. */
const goodAbilities = () => {
  const ab = emptyAbilityMap();
  Object.assign(ab, {
    alertness: 3,
    athletics: 3,
    brawl: 3,
    dodge: 3,
    empathy: 1, // 13
    drive: 3,
    firearms: 3,
    stealth: 3, // 9
    academics: 2,
    occult: 3, // 5
  });
  return ab;
};

describe('creation budgets', () => {
  it('uses Revised 7/5/3 and 13/9/5', () => {
    expect(attributePools('physical')).toEqual({ physical: 7, social: 5, mental: 3 });
    expect(attributePools('mental')).toEqual({ physical: 3, social: 5, mental: 7 });
    expect(abilityPools('talents')).toEqual({ talents: 13, skills: 9, knowledges: 5 });
    expect(abilityPools('knowledges')).toEqual({ talents: 5, skills: 9, knowledges: 13 });
  });

  it('includes every core discipline in the presets', () => {
    CLASSIC_DISCIPLINES.forEach((d) => expect(DISCIPLINE_PRESETS).toContain(d));
    ['Obtenebration', 'Thanatosis', 'Visceratika'].forEach((d) =>
      expect(DISCIPLINE_PRESETS).toContain(d)
    );
  });
});

describe('validateAttributeSpread', () => {
  const pools = attributePools('physical');

  it('accepts 7/5/3 added on top of the free dot', () => {
    expect(validateAttributeSpread(goodAttrs(), pools)).toBeNull();
  });

  it('rejects the old reading (7/5/3 as category totals)', () => {
    const attrs = emptyAttrMap();
    Object.assign(attrs, { strength: 5, charisma: 3 }); // physical total 7, social 5, mental 3
    expect(validateAttributeSpread(attrs, pools)).not.toBeNull();
  });

  it('rejects unspent dots', () => {
    expect(validateAttributeSpread(emptyAttrMap(), pools)).not.toBeNull();
  });

  it('allows extra dots only with freebies', () => {
    const a = { ...goodAttrs(), perception: 3 };
    expect(validateAttributeSpread(a, pools)).not.toBeNull();
    expect(validateAttributeSpread(a, pools, { allowFreebies: true })).toBeNull();
  });

  it('Nosferatu: Appearance 0, the social dots go elsewhere', () => {
    const a = { ...goodAttrs(), appearance: 0, charisma: 4 };
    expect(validateAttributeSpread(a, pools, { nosferatu: true })).toBeNull();
    // Appearance 0 is rejected for anyone else ...
    expect(validateAttributeSpread(a, pools)).not.toBeNull();
    // ... and Nosferatu can't raise it, even with freebies.
    const raised = { ...a, appearance: 1, charisma: 3 };
    expect(
      validateAttributeSpread(raised, pools, { nosferatu: true, allowFreebies: true })
    ).toMatch(/Nosferatu/);
  });
});

describe('validateAbilitySpread', () => {
  const pools = abilityPools('talents');

  it('accepts 13/9/5 with nothing above 3', () => {
    expect(validateAbilitySpread(goodAbilities(), pools)).toBeNull();
  });

  it('rejects when totals do not match pools', () => {
    expect(validateAbilitySpread(emptyAbilityMap(), pools)).not.toBeNull();
  });

  it('rejects an ability above 3 before freebies', () => {
    const ab = { ...goodAbilities(), alertness: 4, empathy: 0 }; // still 13 talents
    expect(validateAbilitySpread(ab, pools)).toMatch(/above 3/);
  });

  it('counts dots above 3 as freebie dots', () => {
    const ab = { ...goodAbilities(), alertness: 4 }; // 14 talents: 13 creation + 1 freebie
    expect(validateAbilitySpread(ab, pools, null, { allowFreebies: true })).toBeNull();
    expect(abilityDotBreakdown(ab, pools).talents.freebieDots).toBe(1);
    // A 4 cannot stand in for creation dots
    const short = { ...goodAbilities(), alertness: 4, empathy: 0 };
    expect(validateAbilitySpread(short, pools, null, { allowFreebies: true })).not.toBeNull();
  });

  it('counts custom rows toward the column', () => {
    const ab = { ...goodAbilities(), empathy: 0 };
    const custom = { talents: [{ dots: 1 }] };
    expect(validateAbilitySpread(ab, pools, custom)).toBeNull();
  });
});

describe('validateVirtues', () => {
  it('accepts 1 free each + 7 (total 10)', () => {
    expect(validateVirtues({ conscience: '4', self_control: '3', courage: '3' })).toBeNull();
  });

  it('rejects the old 7-total reading', () => {
    expect(validateVirtues({ conscience: '3', self_control: '3', courage: '1' })).not.toBeNull();
  });

  it('allows more only with freebies', () => {
    const v = { conscience: 4, self_control: 3, courage: 4 };
    expect(validateVirtues(v)).not.toBeNull();
    expect(validateVirtues(v, { allowFreebies: true })).toBeNull();
  });
});

describe('deriveClassicMorality', () => {
  it('Humanity = Conscience + Self-Control, Willpower = Courage', () => {
    expect(deriveClassicMorality({ conscience: 4, self_control: 3, courage: 3 })).toEqual({
      humanityBase: 7,
      willpowerBase: 3,
      virtueFreebieDots: 0,
    });
  });

  it('3/3/4 gives Humanity 6, Willpower 4', () => {
    const m = deriveClassicMorality({ conscience: 3, self_control: 3, courage: 4 });
    expect(m.humanityBase).toBe(6);
    expect(m.willpowerBase).toBe(4);
  });

  it('a freebie Conscience dot keeps Humanity 6 / Willpower 4', () => {
    const creation = { conscience: 3, self_control: 3, courage: 4 };
    const bought = { conscience: 1, self_control: 0, courage: 0 };
    expect(deriveClassicMorality(creation, bought)).toEqual({
      humanityBase: 6,
      willpowerBase: 4,
      virtueFreebieDots: 1,
    });
    expect(finalVirtues(creation, bought)).toEqual({ conscience: 4, self_control: 3, courage: 4 });
  });

  it('freebie Courage or Self-Control dots never move the derived traits either', () => {
    const creation = { conscience: 3, self_control: 3, courage: 4 };
    const m = deriveClassicMorality(creation, { conscience: 0, self_control: 2, courage: 1 });
    expect(m).toEqual({ humanityBase: 6, willpowerBase: 4, virtueFreebieDots: 3 });
  });
});

describe('freebie points', () => {
  const base = {
    systemType: 'vampire',
    attrs: goodAttrs(),
    attrPools: attributePools('physical'),
    abilities: goodAbilities(),
    abilityPoolsSel: abilityPools('talents'),
    customAbilities: {},
    disciplines: [{ dots: 2 }, { dots: 1 }],
    backgrounds: [{ dots: 5 }],
    virtues: { conscience: 4, self_control: 3, courage: 3 },
    humanityBonus: 0,
    willpowerBonus: 0,
    meritRows: [],
  };

  it('a sheet within the creation budgets spends nothing', () => {
    const f = computeClassicFreebies(base);
    expect(f.spent).toBe(0);
    expect(f.available).toBe(15);
    expect(validateFreebies(f)).toBeNull();
  });

  it('prices each trait with the classic.json costs', () => {
    const f = computeClassicFreebies({
      ...base,
      attrs: { ...goodAttrs(), wits: 3 }, // +1 attribute = 5
      abilities: { ...goodAbilities(), alertness: 4 }, // +1 ability = 2
      disciplines: [{ dots: 2 }, { dots: 2 }], // +1 discipline = 7
      backgrounds: [{ dots: 5 }, { dots: 1 }], // +1 background = 1
      willpowerBonus: 1, // +1 willpower = 1
    });
    expect(f.spent).toBe(16);
    expect(validateFreebies(f)).toMatch(/overspent/);
  });

  it('flaws add up to 7 more points and merits cost points', () => {
    const f = computeClassicFreebies({
      ...base,
      humanityBonus: 1, // 2
      meritRows: [
        { name: 'Eat Food', points: 1 },
        { name: 'Nightmares', points: -1 },
        { name: 'Prey Exclusion', points: -1 },
      ],
    });
    expect(f.spent).toBe(3);
    expect(f.available).toBe(17);
    const tooMany = computeClassicFreebies({
      ...base,
      meritRows: [{ name: 'Flaws', points: -8 }],
    });
    expect(tooMany.available).toBe(22);
    expect(validateFreebies(tooMany)).toMatch(/at most 7/);
  });

  it('freebie virtue dots cost 2 each (classic.json) and leave Humanity/Willpower alone', () => {
    const creation = { conscience: 3, self_control: 3, courage: 4 };
    const bought = { conscience: 1, self_control: 0, courage: 0 };
    const f = computeClassicFreebies({ ...base, virtues: creation, virtueFreebies: bought });
    expect(FREEBIE_COSTS.virtue).toBe(2);
    expect(f.lines).toEqual([
      { key: 'virtues', label: 'Virtues', dots: 1, cost: FREEBIE_COSTS.virtue },
    ]);
    expect(f.spent).toBe(2);
    expect(f.remaining).toBe(13);
    // Humanity/Willpower bought with freebies add on top of the creation values.
    const g = computeClassicFreebies({
      ...base,
      virtues: creation,
      virtueFreebies: bought,
      humanityBonus: 1,
      willpowerBonus: 1,
    });
    expect(g.spent).toBe(2 + FREEBIE_COSTS.humanity_or_path + FREEBIE_COSTS.willpower);
    const m = deriveClassicMorality(creation, bought);
    expect(m.humanityBase + 1).toBe(7);
    expect(m.willpowerBase + 1).toBe(5);
  });

  it('Nosferatu Appearance 0 is not a missing social dot', () => {
    const attrs = { ...goodAttrs(), appearance: 0, charisma: goodAttrs().charisma + 1 };
    // physical primary: social pool 5; Appearance has no free dot to spend
    const f = computeClassicFreebies({ ...base, attrs, nosferatu: true });
    expect(f.lines.find((l) => l.key === 'attributes')).toBeUndefined();
  });

  it('only prices attributes/abilities/merits for non-vampire lines', () => {
    const f = computeClassicFreebies({ ...base, systemType: 'werewolf', willpowerBonus: 3 });
    expect(f.spent).toBe(0);
  });
});

describe('validateSpheres', () => {
  it('requires 6 dots', () => {
    const sp = emptySphereMap();
    MTA_SPHERES.forEach(([k], i) => {
      if (i < 6) sp[k] = 1;
    });
    expect(validateSpheres(sp)).toBeNull();
  });
});
