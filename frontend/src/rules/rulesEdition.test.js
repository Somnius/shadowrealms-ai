import {
  CLASSIC,
  V5,
  editionLabel,
  editionOf,
  isV5,
  isV5Allowed,
  normalizeEdition,
} from './rulesEdition';

describe('rulesEdition', () => {
  it('only allows V5 for vampire', () => {
    expect(isV5Allowed('vampire')).toBe(true);
    expect(isV5Allowed(' Vampire ')).toBe(true);
    expect(isV5Allowed('werewolf')).toBe(false);
    expect(isV5Allowed('mage')).toBe(false);
    expect(isV5Allowed('custom')).toBe(false);
    expect(isV5Allowed(undefined)).toBe(false);
  });

  it('defaults to classic', () => {
    expect(editionOf(undefined)).toBe(CLASSIC);
    expect(editionOf(null)).toBe(CLASSIC);
    expect(editionOf({})).toBe(CLASSIC);
    expect(editionOf({ rules_edition: 'nonsense' })).toBe(CLASSIC);
    expect(editionOf({ rules_edition: 'v5' })).toBe(V5);
    expect(editionOf('V5')).toBe(V5);
    expect(editionOf('revised')).toBe(CLASSIC);
  });

  it('normalizes aliases', () => {
    expect(normalizeEdition('5e')).toBe(V5);
    expect(normalizeEdition('owod')).toBe(CLASSIC);
    expect(normalizeEdition('')).toBeNull();
  });

  it('labels editions', () => {
    expect(editionLabel({ rules_edition: 'v5' })).toBe('V5');
    expect(editionLabel({})).toBe('Classic');
    expect(editionLabel('v5', { long: true })).toBe('V5 (5th Edition)');
    expect(isV5({ rules_edition: 'v5' })).toBe(true);
  });
});
