import { resolveClassicDice } from '../../../dice/classicDiceDisplay';
import { resolveV5Dice } from '../../../dice/v5DiceDisplay';
import { CLASSIC_OUTCOMES, EXPECTED_KEY, V5_OUTCOMES, rollClassic, rollV5, seededRandom } from '../diceDemo';
import { contrastRatio, wcagLevel } from '../contrast';

const forced = (list) => list.filter((o) => o !== 'random');

test('classic: every forced outcome holds for every pool and difficulty', () => {
  const rnd = seededRandom(42);
  forced(CLASSIC_OUTCOMES).forEach((outcome) => {
    for (let pool = 1; pool <= 10; pool += 1) {
      for (let difficulty = 3; difficulty <= 10; difficulty += 1) {
        const r = rollClassic({ pool, difficulty, outcome }, rnd);
        expect(r.outcomeKey).toBe(EXPECTED_KEY.classic[outcome]);
        // the dice really resolve to it with the app's resolver
        expect(resolveClassicDice(r.result.results, r.result.difficulty)).toEqual(r.result);
        expect(r.result.results).toHaveLength(r.params.pool);
        if (r.adjusted.length === 0) expect(r.params).toEqual({ pool, difficulty });
      }
    }
  });
});

test('V5: every forced outcome holds for every pool, Hunger and difficulty', () => {
  const rnd = seededRandom(7);
  forced(V5_OUTCOMES).forEach((outcome) => {
    for (let pool = 1; pool <= 10; pool += 1) {
      for (let hunger = 0; hunger <= Math.min(5, pool); hunger += 1) {
        for (let difficulty = 1; difficulty <= 8; difficulty += 1) {
          const r = rollV5({ pool, hunger, difficulty, outcome }, rnd);
          expect(r.outcomeKey).toBe(EXPECTED_KEY.v5[outcome]);
          expect(resolveV5Dice(r.result.normal_dice, r.result.hunger_dice, r.result.difficulty)).toEqual(r.result);
          expect(r.result.normal_dice.length + r.result.hunger_dice.length).toBe(r.params.pool);
          expect(r.result.hunger_dice).toHaveLength(r.params.hunger);
          if (r.adjusted.length === 0) expect(r.params).toEqual({ pool, hunger, difficulty });
        }
      }
    }
  });
});

test('random rolls stay inside the chosen numbers', () => {
  const rnd = seededRandom(3);
  for (let i = 0; i < 200; i += 1) {
    const c = rollClassic({ pool: 4, difficulty: 7 }, rnd);
    expect(c.adjusted).toEqual([]);
    expect(c.result.results.every((v) => v >= 1 && v <= 10)).toBe(true);
    const v = rollV5({ pool: 5, hunger: 3, difficulty: 2 }, rnd);
    expect(v.result.hunger_dice).toHaveLength(3);
    expect(v.result.normal_dice).toHaveLength(2);
  }
});

test('contrast maths matches the WCAG reference values in the design README', () => {
  expect(contrastRatio('#ffffff', '#000000')).toBeCloseTo(21, 5);
  expect(contrastRatio('#ffffff', '#c2334d')).toBeCloseTo(5.42, 1); // white on blood-600
  expect(wcagLevel(7.1)).toBe('AAA');
  expect(wcagLevel(4.6)).toBe('AA');
  expect(wcagLevel(3.2)).toBe('AA large');
  expect(wcagLevel(1.2)).toBe('decor');
});

test('glyph search folds Greek accents, case and final sigma', () => {
  const { foldSearch } = require('../GlyphGallery');
  expect(foldSearch('Κερί')).toBe(foldSearch('κερι'));
  expect(foldSearch('ΤΡΑΠΟΥΛΆΣ')).toBe('τραπουλασ');
  expect(foldSearch('τράπουλας').includes(foldSearch('ΤΡΑΠΟΥΛΑΣ'))).toBe(true);
});

test('contrast ratios are rounded down for display', () => {
  const { formatRatio } = require('../contrast');
  expect(formatRatio(4.499)).toBe('4.49');
  expect(formatRatio(4.5)).toBe('4.50');
  expect(formatRatio(7.0)).toBe('7.00');
  expect(formatRatio(0)).toBe('–');
});
