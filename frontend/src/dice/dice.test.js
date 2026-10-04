import { classicOutcome, classifyClassicDie, resolveClassicDice } from './classicDiceDisplay';
import { classifyV5Die, resolveV5Dice, v5Badges, v5Outcome, v5SummaryLine } from './v5DiceDisplay';
import { buildDiceMarker, overlayFromMarker } from './diceMarker';

describe('classic dice (Revised)', () => {
  it('1s cancel successes', () => {
    const r = resolveClassicDice([7, 8, 1, 3], 6);
    expect(r.successes).toBe(1);
    expect(r.is_botch).toBe(false);
  });

  it('cancelled to zero is a plain failure, not a botch', () => {
    const r = resolveClassicDice([7, 1, 1], 6);
    expect(r.successes).toBe(0);
    expect(r.is_botch).toBe(false);
    expect(classicOutcome(r).key).toBe('failure');
  });

  it('botch only when no die succeeded and a 1 showed', () => {
    const r = resolveClassicDice([2, 1, 4], 6);
    expect(r.is_botch).toBe(true);
    expect(classicOutcome(r).label).toBe('Botch');
    expect(resolveClassicDice([2, 3, 4], 6).is_botch).toBe(false);
  });

  it('willpower adds an uncancellable success and prevents the botch', () => {
    const r = resolveClassicDice([2, 1, 1], 6, { willpower: true });
    expect(r.successes).toBe(1);
    expect(r.is_botch).toBe(false);
  });

  it('specialty rerolls add successes and their 1s do not cancel', () => {
    const r = resolveClassicDice([10, 5], 6, { specialtyRerolls: [10, 1] });
    // 10 counts (1) + reroll 10 (1); reroll 1 cancels nothing
    expect(r.successes).toBe(2);
  });

  it('5+ net successes is exceptional', () => {
    const r = resolveClassicDice([6, 7, 8, 9, 10], 6);
    expect(r.is_exceptional).toBe(true);
    expect(classicOutcome(r).key).toBe('exceptional');
  });

  it('classifies dice against the TN', () => {
    expect(classifyClassicDie(1, 6)).toBe('one');
    expect(classifyClassicDie(10, 6)).toBe('ten');
    expect(classifyClassicDie(7, 8)).toBe('fail');
    expect(classifyClassicDie(8, 8)).toBe('success');
  });
});

describe('V5 dice', () => {
  it('counts 6+ and pairs of 10s as 4', () => {
    const r = resolveV5Dice([10, 10, 6, 2], [], 3);
    expect(r.successes).toBe(5);
    expect(r.is_critical).toBe(true);
    expect(r.is_messy_critical).toBe(false);
    expect(v5Outcome(r).key).toBe('critical');
  });

  it('messy critical when a hunger die shows one of the 10s', () => {
    const r = resolveV5Dice([10, 3], [10], 2);
    expect(r.successes).toBe(4);
    expect(r.is_messy_critical).toBe(true);
    expect(v5Outcome(r).label).toBe('Messy critical');
  });

  it('a lone 10 is not a critical', () => {
    const r = resolveV5Dice([10, 3], [], 1);
    expect(r.successes).toBe(1);
    expect(r.is_critical).toBe(false);
  });

  it('bestial failure: fail with a hunger 1', () => {
    const r = resolveV5Dice([7, 2], [1], 3);
    expect(r.outcome).toBe('fail');
    expect(r.is_bestial_failure).toBe(true);
    expect(v5Outcome(r).key).toBe('bestial');
  });

  it('hunger 1 on a win is not bestial', () => {
    const r = resolveV5Dice([7, 8], [1], 2);
    expect(r.outcome).toBe('win');
    expect(r.is_bestial_failure).toBe(false);
  });

  it('total failure on zero successes, even at difficulty 0', () => {
    const r = resolveV5Dice([2, 3], [4], 0);
    expect(r.is_total_failure).toBe(true);
    expect(r.outcome).toBe('fail');
    expect(v5Badges(r)[0].key).toBe('total');
  });

  it('bestial + total failure shows both badges', () => {
    const r = resolveV5Dice([2], [1], 1);
    expect(v5Badges(r).map((b) => b.key)).toEqual(['bestial', 'total']);
  });

  it('classifies hunger dice distinctly', () => {
    expect(classifyV5Die(1, true)).toEqual({ kind: 'hunger', state: 'bestial' });
    expect(classifyV5Die(1, false)).toEqual({ kind: 'normal', state: 'fail' });
    expect(classifyV5Die(10, true).state).toBe('ten');
    expect(classifyV5Die(6, false).state).toBe('success');
  });

  it('summarises', () => {
    expect(v5SummaryLine({ successes: 3, difficulty: 2, hunger_dice: [1, 2] })).toBe(
      '3 successes vs 2 · margin +1 · Hunger 2'
    );
    expect(v5SummaryLine({ successes: 1, difficulty: 0, hunger_dice: [] })).toBe('1 success · Hunger 0');
  });
});

describe('dice markers', () => {
  it('builds a classic marker from a manual roll result', () => {
    const m = buildDiceMarker(
      { rules_edition: 'classic', results: [1, 6, 7], difficulty: 6, successes: 1, is_botch: false, willpower: true },
      { animationId: 'a', startedAtMs: 1, durationMs: 3000 }
    );
    expect(m.rules_edition).toBe('classic');
    expect(m.dice_preview).toEqual([1, 6, 7]);
    expect(m.willpower).toBe(true);
    const o = overlayFromMarker(m);
    expect(o.rulesEdition).toBe('classic');
    expect(o.result.willpower).toBe(true);
  });

  it('builds a classic marker from a slash roll payload', () => {
    const m = buildDiceMarker({ rules_edition: 'classic', dice: [2, 1], difficulty: 6, net_successes: 0, botch: true });
    expect(m.is_botch).toBe(true);
    expect(m.dice_preview).toEqual([2, 1]);
  });

  it('keeps every hunger die in a large V5 preview', () => {
    const normal = Array.from({ length: 12 }, () => 5);
    const m = buildDiceMarker({
      rules_edition: 'v5',
      normal_dice: normal,
      hunger_dice: [1, 10, 10],
      difficulty: 2,
      successes: 4,
      outcome: 'win',
      is_critical: true,
      is_messy_critical: true,
    });
    expect(m.dice_preview).toHaveLength(10);
    expect(m.hunger_flags.filter(Boolean)).toHaveLength(3);
    expect(m.extra_dice_count).toBe(5);
    expect(m.pool_size).toBe(15);
    const o = overlayFromMarker(m);
    expect(o.rulesEdition).toBe('v5');
    expect(o.hungerFlags.slice(-3)).toEqual([true, true, true]);
    expect(o.result.is_messy_critical).toBe(true);
  });

  it('reads old markers without an edition as classic', () => {
    const o = overlayFromMarker({ dice_preview: [3, 9], difficulty: 7, successes: 1 });
    expect(o.rulesEdition).toBe('classic');
    expect(o.hungerFlags).toEqual([false, false]);
  });
});

describe('classic specialty rerolls in markers', () => {
  it('carries the reroll dice through the marker into the overlay', () => {
    const m = buildDiceMarker({
      rules_edition: 'classic',
      results: [10, 4, 7],
      specialty_rerolls: [8],
      difficulty: 6,
      successes: 3,
      specialty: true,
    });
    expect(m.specialty_rerolls).toEqual([8]);
    const o = overlayFromMarker(m);
    expect(o.specialtyRerolls).toEqual([8]);
    expect(o.diceFinal).toEqual([10, 4, 7]);
  });
  it('has no rerolls for V5 or old markers', () => {
    expect(overlayFromMarker({ dice_preview: [3, 9] }).specialtyRerolls).toEqual([]);
    expect(
      overlayFromMarker({ rules_edition: 'v5', dice_preview: [3], specialty_rerolls: [9] }).specialtyRerolls
    ).toEqual([]);
  });
});
