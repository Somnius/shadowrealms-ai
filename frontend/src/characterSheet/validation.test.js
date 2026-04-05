/**
 * Manual QA: create one VtM / WtA / MtA character locally; confirm POST payload includes
 * attributes, skills (optional custom.*), merits_flaws.entries + notes, and wod_meta
 * (disciplines; rage/gnosis/gifts_notes; spheres).
 */
import { MTA_SPHERES } from './constants';
import {
  emptyAbilityMap,
  emptyAttrMap,
  emptySphereMap,
  validateAbilitySpread,
  validateAttributeSpread,
  validateSpheres,
  validateVirtues,
} from './validation';

describe('validateAttributeSpread', () => {
  const pools = { physical: 7, social: 5, mental: 3 };

  it('accepts a valid spread', () => {
    const attrs = emptyAttrMap();
    attrs.strength = 5;
    attrs.dexterity = 1;
    attrs.stamina = 1;
    attrs.charisma = 3;
    attrs.manipulation = 1;
    attrs.appearance = 1;
    attrs.perception = 1;
    attrs.intelligence = 1;
    attrs.wits = 1;
    expect(validateAttributeSpread(attrs, pools)).toBeNull();
  });

  it('rejects wrong physical total', () => {
    const attrs = emptyAttrMap();
    expect(validateAttributeSpread(attrs, pools)).not.toBeNull();
  });
});

describe('validateAbilitySpread', () => {
  const pools = { talents: 11, skills: 7, knowledges: 4 };

  it('rejects when totals do not match pools', () => {
    const ab = emptyAbilityMap();
    expect(validateAbilitySpread(ab, pools)).not.toBeNull();
  });
});

describe('validateVirtues', () => {
  it('accepts 3+3+1', () => {
    expect(
      validateVirtues({ conscience: '3', self_control: '3', courage: '1' })
    ).toBeNull();
  });

  it('rejects wrong total', () => {
    expect(validateVirtues({ conscience: '3', self_control: '3', courage: '2' })).not.toBeNull();
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
