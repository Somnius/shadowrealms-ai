/**
 * Phase 4 atmosphere layer: the per-user Atmosphere setting (full / subtle / off), and that
 * reduced motion renders the static fallbacks instead of animations.
 */
import { render, screen, act } from '@testing-library/react';
import { DesignProvider, useAtmosphere, useMotionPreference } from '../motion';
import { CandleHalo, ChronicleSigil, CrackOverlay, RollFx, RouteTransition, rollMood } from '../atmosphere/Ambience';
import { FogLayer } from '../atmosphere/Atmosphere';
import DiceRollOverlay from '../../components/dice/DiceRollOverlay';

function mockMatchMedia(reduce) {
  const original = window.matchMedia;
  window.matchMedia = (query) => ({
    matches: reduce && query.includes('reduce'),
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
  });
  return () => {
    window.matchMedia = original;
  };
}

let api;
function Grab() {
  api = { ...useAtmosphere(), motion: useMotionPreference() };
  return <span data-testid="level">{api.level}</span>;
}

beforeEach(() => {
  window.localStorage.clear();
  api = null;
});

describe('Atmosphere setting', () => {
  test('defaults to full and writes data-atmosphere on the root', () => {
    const { container } = render(
      <DesignProvider>
        <Grab />
      </DesignProvider>
    );
    expect(container.firstChild).toHaveAttribute('data-atmosphere', 'full');
    expect(container.firstChild).toHaveAttribute('data-motion', 'full');
    expect(screen.getByTestId('level')).toHaveTextContent('full');
  });

  test('subtle and off are stored and survive a reload', () => {
    const first = render(
      <DesignProvider>
        <Grab />
      </DesignProvider>
    );
    act(() => api.setLevel('subtle'));
    expect(first.container.firstChild).toHaveAttribute('data-atmosphere', 'subtle');
    expect(first.container.firstChild).toHaveAttribute('data-motion', 'full');
    expect(window.localStorage.getItem('sr_atmosphere')).toBe('subtle');
    first.unmount();

    const second = render(
      <DesignProvider>
        <Grab />
      </DesignProvider>
    );
    expect(second.container.firstChild).toHaveAttribute('data-atmosphere', 'subtle');
    act(() => api.setLevel('off'));
    expect(second.container.firstChild).toHaveAttribute('data-atmosphere', 'off');
    // Off = reduced motion, also for code that only knows the older motion preference.
    expect(second.container.firstChild).toHaveAttribute('data-motion', 'reduced');
    expect(api.motion.reduced).toBe(true);
    expect(window.localStorage.getItem('sr_atmosphere')).toBe('off');
    expect(window.localStorage.getItem('sr_motion')).toBe('reduced');
    second.unmount();

    const third = render(
      <DesignProvider>
        <Grab />
      </DesignProvider>
    );
    expect(third.container.firstChild).toHaveAttribute('data-motion', 'reduced');
    expect(screen.getByTestId('level')).toHaveTextContent('off');
  });

  test('an older "reduce motion" choice reads as atmosphere off', () => {
    window.localStorage.setItem('sr_motion', 'reduced');
    const { container } = render(
      <DesignProvider>
        <Grab />
      </DesignProvider>
    );
    expect(container.firstChild).toHaveAttribute('data-atmosphere', 'off');
    expect(api.choice).toBe('off');
  });

  test('the OS reduced-motion setting forces off whatever the stored choice', () => {
    window.localStorage.setItem('sr_atmosphere', 'full');
    const restore = mockMatchMedia(true);
    const { container } = render(
      <DesignProvider>
        <Grab />
      </DesignProvider>
    );
    expect(container.firstChild).toHaveAttribute('data-atmosphere', 'off');
    expect(api.choice).toBe('full');
    expect(api.systemReduced).toBe(true);
    restore();
  });
});

describe('reduced motion renders static fallbacks', () => {
  const botch = {
    visible: true,
    settled: true,
    animationId: 'b1',
    rulesEdition: 'classic',
    difficulty: 6,
    diceFinal: [1, 1, 3],
    diceRolling: [1, 1, 3],
    hungerFlags: [false, false, false],
    extraDiceCount: 0,
    specialtyRerolls: [],
    result: { rules_edition: 'classic', difficulty: 6, successes: 0, is_botch: true },
  };

  test('full: a botch plays the blood drip animation and the dice land', () => {
    const { container } = render(
      <DesignProvider>
        <DiceRollOverlay overlay={botch} onDismiss={() => {}} />
      </DesignProvider>
    );
    const fx = container.querySelector('.sr-rollfx');
    expect(fx).toHaveAttribute('data-mood', 'botch');
    expect(fx).not.toHaveClass('is-static');
    expect(container.querySelector('.sr-blood-drip')).not.toBeNull();
    expect(container.querySelectorAll('.sr-ldie.is-landed')).toHaveLength(3);
  });

  test('off: the same botch shows the static end state (no drip animation, no framer paths)', () => {
    window.localStorage.setItem('sr_atmosphere', 'off');
    const { container } = render(
      <DesignProvider>
        <DiceRollOverlay overlay={botch} onDismiss={() => {}} />
      </DesignProvider>
    );
    const fx = container.querySelector('.sr-rollfx');
    expect(fx).toHaveClass('is-static');
    expect(container.querySelector('.sr-blood-drip')).toBeNull();
    expect(container.querySelector('.sr-rollfx__static-drips')).not.toBeNull();
    const crack = container.querySelector('.sr-crack');
    expect(crack).toHaveAttribute('data-static', 'true');
    // framer would leave inline style (pathLength / opacity) on animated paths
    crack.querySelectorAll('path').forEach((p) => expect(p.getAttribute('style')).toBeNull());
  });

  test('off: rolling dice show still placeholders (no flickering numbers) and no effect yet', () => {
    window.localStorage.setItem('sr_atmosphere', 'off');
    const { container } = render(
      <DesignProvider>
        <DiceRollOverlay overlay={{ ...botch, settled: false }} onDismiss={() => {}} />
      </DesignProvider>
    );
    expect(container.firstChild).toHaveAttribute('data-motion', 'reduced');
    expect(container.querySelector('.sr-rollfx')).toBeNull();
    const faces = [...container.querySelectorAll('.sr-die__value')].map((n) => n.textContent);
    expect(faces).toEqual(['?', '?', '?']);
  });

  test('full: rolling dice tumble and flicker their values', () => {
    const { container } = render(
      <DesignProvider>
        <DiceRollOverlay overlay={{ ...botch, settled: false, diceRolling: [7, 2, 9] }} onDismiss={() => {}} />
      </DesignProvider>
    );
    expect(container.querySelectorAll('.sr-ldie.is-rolling')).toHaveLength(3);
    expect([...container.querySelectorAll('.sr-die__value')].map((n) => n.textContent)).toEqual(['7', '2', '9']);
  });

  test('ambient pieces are static under off and subtle, animated under full', () => {
    const tree = (
      <>
        <FogLayer />
        <CandleHalo lit>
          <span>ST</span>
        </CandleHalo>
        <ChronicleSigil line="vampire" edition="v5" />
      </>
    );
    window.localStorage.setItem('sr_atmosphere', 'full');
    const full = render(<DesignProvider>{tree}</DesignProvider>);
    expect(full.container.querySelector('.sr-fog')).not.toHaveClass('is-static');
    expect(full.container.querySelector('.sr-halo')).not.toHaveClass('is-static');
    expect(full.container.querySelector('.sr-csigil')).not.toHaveClass('is-static');
    full.unmount();

    window.localStorage.setItem('sr_atmosphere', 'subtle');
    const subtle = render(<DesignProvider>{tree}</DesignProvider>);
    expect(subtle.container.querySelector('.sr-fog')).toHaveClass('is-static');
    expect(subtle.container.querySelector('.sr-halo')).toHaveClass('is-static');
    subtle.unmount();

    window.localStorage.setItem('sr_atmosphere', 'off');
    const off = render(<DesignProvider>{tree}</DesignProvider>);
    expect(off.container.querySelector('.sr-fog')).toHaveClass('is-static');
    expect(off.container.querySelector('.sr-halo')).toHaveClass('is-static');
    const sigil = off.container.querySelector('.sr-csigil');
    expect(sigil).toHaveClass('is-static');
    expect(sigil).not.toHaveClass('is-drawn');
  });

  test('route transition starts visible (no opacity 0) under reduced motion', () => {
    window.localStorage.setItem('sr_atmosphere', 'off');
    const { container } = render(
      <DesignProvider>
        <RouteTransition routeKey="a">
          <p>page</p>
        </RouteTransition>
      </DesignProvider>
    );
    const route = container.querySelector('.sr-route');
    expect(route.style.opacity === '' || route.style.opacity === '1').toBe(true);
  });

  test('crack overlay animates with framer under full motion', () => {
    const { container } = render(
      <DesignProvider>
        <CrackOverlay />
      </DesignProvider>
    );
    const crack = container.querySelector('.sr-crack');
    expect(crack).not.toHaveAttribute('data-static');
  });

  test('history dice cards only keep a quiet static mark', () => {
    const { container } = render(
      <DesignProvider>
        <div style={{ position: 'relative' }}>
          <RollFx mood="bestial" play={false} />
        </div>
      </DesignProvider>
    );
    const fx = container.querySelector('.sr-rollfx');
    expect(fx).toHaveClass('is-history');
    expect(container.querySelector('.sr-crack')).toBeNull();
    expect(container.querySelector('.sr-blood-drip')).toBeNull();
  });
});

test('rollMood maps both editions', () => {
  expect(rollMood({ rules_edition: 'classic', is_botch: true })).toBe('botch');
  expect(rollMood({ rules_edition: 'classic', successes: 5, is_exceptional: true })).toBe('exceptional');
  expect(rollMood({ rules_edition: 'classic', successes: 0 })).toBe('fail');
  expect(rollMood({ rules_edition: 'v5', outcome: 'fail', is_bestial_failure: true })).toBe('bestial');
  expect(rollMood({ rules_edition: 'v5', outcome: 'win', is_critical: true, is_messy_critical: true })).toBe('messy');
  expect(rollMood({ rules_edition: 'v5', outcome: 'win', is_critical: true })).toBe('critical');
  expect(rollMood({ rules_edition: 'v5', outcome: 'win' })).toBe('win');
});
