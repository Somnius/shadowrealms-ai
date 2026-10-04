import React from 'react';
import { render, screen } from '@testing-library/react';
import { analyzeV5, analyzeClassic } from '../atmosphere/diceAnalysis';
import DiceRollViz from '../atmosphere/DiceRollViz';
import SigilReveal, { buildSigilPaths } from '../atmosphere/SigilReveal';
import { FogLayer, CandleGlow, BloodDrip } from '../atmosphere/Atmosphere';
import { DesignProvider } from '../motion';

describe('V5 analysis (mirrors backend resolve_v5)', () => {
  test('pairs of 10s add two successes; hunger 10 in a critical is messy', () => {
    const r = analyzeV5({ normal: [10, 7, 3, 6], hunger: [10, 2], difficulty: 3 });
    expect(r.successes).toBe(6); // 10,7,6,10 = 4 + pair bonus 2
    expect(r.pairs).toHaveLength(1);
    expect(r.isCritical).toBe(true);
    expect(r.isMessyCritical).toBe(true);
    expect(r.outcome).toBe('messy-critical');
  });
  test('three 10s = 5 successes, four 10s = 8', () => {
    expect(analyzeV5({ normal: [10, 10, 10] }).successes).toBe(5);
    expect(analyzeV5({ normal: [10, 10, 10, 10] }).successes).toBe(8);
  });
  test('fail with a hunger 1 is bestial; zero successes is a total failure even at difficulty 0', () => {
    const b = analyzeV5({ normal: [4, 3, 5], hunger: [1, 2], difficulty: 2 });
    expect(b.outcome).toBe('bestial-failure');
    const t = analyzeV5({ normal: [2, 3], hunger: [], difficulty: 0 });
    expect(t.win).toBe(false);
    expect(t.outcome).toBe('total-failure');
  });
  test('server flags win over local computation', () => {
    const r = analyzeV5({ normal: [6], hunger: [], difficulty: 1, flags: { successes: 3, outcome: 'win', is_critical: true } });
    expect(r.successes).toBe(3);
    expect(r.outcome).toBe('critical');
  });
});

describe('classic analysis (docs/dice-old-wod.md)', () => {
  test('1s cancel; botch only when nothing succeeded', () => {
    expect(analyzeClassic({ dice: [9, 1, 1, 8, 1], difficulty: 8 }).outcome).toBe('failure');
    expect(analyzeClassic({ dice: [1, 3, 4], difficulty: 6 }).outcome).toBe('botch');
    expect(analyzeClassic({ dice: [1, 3, 4], difficulty: 6, willpower: true }).successes).toBe(1);
  });
  test('5+ net successes is exceptional; specialty rerolls only add', () => {
    const r = analyzeClassic({ dice: [8, 9, 10, 7, 6, 1], difficulty: 6, rerolls: [7] });
    expect(r.successes).toBe(5);
    expect(r.outcome).toBe('exceptional');
  });
});

describe('DiceRollViz', () => {
  test('renders a figure described in words with every die listed', () => {
    render(<DiceRollViz edition="v5" normal={[10, 7, 3]} hunger={[10]} difficulty={2} />);
    const fig = screen.getByRole('figure');
    expect(fig).toHaveAccessibleName(/Messy critical\. 4 dice, 1 Hunger; 5 successes of 2 needed; 1 critical pair\./);
    expect(fig).toHaveTextContent('Dice: 10, 7, 3, 10 (Hunger)');
    expect(fig.querySelectorAll('.sr-die')).toHaveLength(4);
    expect(fig.querySelector('.sr-dice-viz__pair')).not.toBeNull();
  });

  test('accepts an API roll_result and shows the drip on a botch (static under reduced motion)', () => {
    const onDone = jest.fn();
    const { container } = render(
      <DesignProvider motion="reduced">
        <DiceRollViz result={{ rules_edition: 'classic', results: [1, 2, 3], difficulty: 6, is_botch: true, successes: 0 }} />
        <BloodDrip onDone={onDone} />
      </DesignProvider>
    );
    expect(screen.getByRole('figure')).toHaveAttribute('data-outcome', 'botch');
    expect(container.querySelector('.sr-dice-viz .sr-blood-drip')).not.toBeNull();
    expect(onDone).toHaveBeenCalled();
  });
});

describe('atmosphere', () => {
  test('sigil paths come from d3-shape and the reveal is an image with a name', () => {
    const p = buildSigilPaths();
    expect(p.thornRing).toMatch(/^M/);
    expect(p.thornRing).not.toMatch(/NaN/);
    render(<SigilReveal title="ShadowRealms" />);
    expect(screen.getByRole('img', { name: 'ShadowRealms' })).toBeInTheDocument();
  });

  test('ambient layers are decorative and static under reduced motion', () => {
    const { container } = render(
      <DesignProvider motion="reduced">
        <FogLayer />
        <CandleGlow />
      </DesignProvider>
    );
    const fog = container.querySelector('.sr-fog');
    expect(fog).toHaveAttribute('aria-hidden', 'true');
    expect(fog).toHaveClass('is-static');
    expect(container.querySelector('.sr-candle-glow')).toHaveClass('is-static');
  });
});
