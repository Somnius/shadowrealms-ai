import { describeRollRow } from './historyRow';

describe('describeRollRow', () => {
  it('describes classic rows', () => {
    const s = describeRollRow({
      roll_type: 'manual',
      dice_pool: 3,
      difficulty: 6,
      results: [2, 1, 4],
      successes: 0,
      is_botch: true,
      is_critical: false,
      modifiers: { rules_edition: 'classic', willpower: false },
    });
    expect(s).toBe('Pool 3, TN 6 → [2, 1, 4] → 0 successes · Botch');
  });

  it('treats rows without an edition as classic', () => {
    const s = describeRollRow({ dice_pool: 2, difficulty: 7, results: [8, 9], successes: 2, modifiers: { specialty: true } });
    expect(s).toMatch(/^Pool 2, TN 7, specialty/);
  });

  it('describes V5 rows with hunger dice and outcome', () => {
    const s = describeRollRow({
      roll_type: 'manual',
      dice_pool: 4,
      difficulty: 2,
      results: [10, 3, 10, 1],
      successes: 4,
      modifiers: { rules_edition: 'v5', normal_dice: [10, 3], hunger_dice: [10, 1], rerolled: true },
    });
    expect(s).toContain('Hunger 2');
    expect(s).toContain('hunger [10, 1]');
    expect(s).toContain('Messy critical');
    expect(s).toContain('Willpower reroll');
  });

  it('describes rouse checks', () => {
    const s = describeRollRow({
      roll_type: 'rouse',
      results: [3],
      successes: 0,
      modifiers: { rules_edition: 'v5', hunger_before: 2, hunger_after: 3 },
    });
    expect(s).toBe('V5 Rouse check → [3] → failed · Hunger 2 → 3');
  });
});
