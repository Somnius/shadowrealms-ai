import React from 'react';
import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { DesignProvider, ToastProvider } from '../../../design';
import { setLanguage } from '../../../i18n';
import ShowcasePage from '../ShowcasePage';
import { CLASSIC_OUTCOMES, EXPECTED_KEY, V5_OUTCOMES } from '../diceDemo';

function mockMotion(reduce) {
  const original = window.matchMedia;
  window.matchMedia = (query) => ({
    matches: reduce && query.includes('reduce'),
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  });
  return () => {
    window.matchMedia = original;
  };
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/showcase']}>
      <DesignProvider>
        <ToastProvider>
          <ShowcasePage onBack={() => {}} />
        </ToastProvider>
      </DesignProvider>
    </MemoryRouter>
  );
}

beforeEach(() => {
  window.localStorage.clear();
  setLanguage('en', { remember: false, save: false });
});

afterAll(() => {
  setLanguage('en', { remember: false, save: false });
});

test('renders every section of the tour, signed out and without network', () => {
  const fetchSpy = jest.spyOn(global, 'fetch').mockImplementation(() => Promise.reject(new Error('no network in the showcase')));
  renderPage();
  ['hero', 'editions', 'glyphs', 'chat', 'components', 'tokens', 'cta'].forEach((id) => {
    expect(screen.getByTestId(`showcase-section-${id}`)).toBeInTheDocument();
  });
  expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('ShadowRealms');
  // chat preview uses the real chat list
  expect(within(screen.getByTestId('chat-preview')).getByRole('log')).toBeInTheDocument();
  // all 97 glyphs are listed
  expect(screen.getByTestId('glyph-count')).toHaveTextContent('Showing 97 of 97');
  // CTA goes back to login
  expect(screen.getByTestId('cta-login')).toHaveAttribute('href', '/login');
  expect(fetchSpy).not.toHaveBeenCalled();
  fetchSpy.mockRestore();
});

function rollForced(edition, outcome) {
  const card = screen.getByTestId(`edition-${edition}`);
  const picker = within(card).getByTestId(`outcome-picker-${edition}`);
  fireEvent.click(picker.querySelector(`input[value="${outcome}"]`));
  fireEvent.click(within(card).getByTestId(`roll-${edition}`));
  return within(card).getByTestId(`stage-${edition}`);
}

const MOOD = { botch: 'botch', exceptional: 'exceptional', bestial: 'bestial', messy: 'messy', critical: 'critical' };

describe.each([
  ['classic', CLASSIC_OUTCOMES],
  ['v5', V5_OUTCOMES],
])('%s outcome picker', (edition, outcomes) => {
  test.each(outcomes.filter((o) => o !== 'random'))('forcing "%s" shows that result and its effect', (outcome) => {
    renderPage();
    // a few rolls each, so random dice choices are exercised
    for (let i = 0; i < 5; i += 1) {
      const stage = rollForced(edition, outcome);
      const key = EXPECTED_KEY[edition][outcome];
      expect(stage).toHaveAttribute('data-outcome', key);
      expect(within(stage).getByTestId(`outcome-${key}`)).toBeInTheDocument();
      if (MOOD[outcome]) {
        expect(stage).toHaveAttribute('data-mood', MOOD[outcome]);
        expect(stage.querySelector(`.sr-rollfx--${MOOD[outcome]}`)).not.toBeNull();
      }
    }
  });
});

test('V5 effect labels: messy critical, bestial failure, total failure, critical win', () => {
  renderPage();
  expect(within(rollForced('v5', 'messy')).getByTestId('outcome-messy')).toHaveTextContent('Messy critical');
  expect(within(rollForced('v5', 'bestial')).getByTestId('outcome-bestial')).toHaveTextContent('Bestial failure');
  expect(within(rollForced('v5', 'total')).getByTestId('outcome-total')).toHaveTextContent('Total failure');
  expect(within(rollForced('v5', 'critical')).getByTestId('outcome-critical')).toHaveTextContent('Critical win');
  expect(within(rollForced('classic', 'botch')).getByTestId('outcome-botch')).toHaveTextContent('Botch');
  expect(within(rollForced('classic', 'exceptional')).getByTestId('outcome-exceptional')).toHaveTextContent('Exceptional success');
});

test('an impossible outcome adjusts the pool and says so', () => {
  renderPage();
  const card = screen.getByTestId('edition-v5');
  // Hunger to 0: a messy critical needs at least one Hunger die
  fireEvent.keyDown(within(card).getByRole('slider', { name: /Hunger/ }), { key: 'Home' });
  const stage = rollForced('v5', 'messy');
  expect(stage).toHaveAttribute('data-outcome', 'messy');
  expect(stage).toHaveTextContent('Hunger set to 1');
});

test('reduced motion: everything renders in its final, static state', () => {
  const restore = mockMotion(true);
  try {
    const { container } = renderPage();
    const root = container.querySelector('.sr-app');
    expect(root).toHaveAttribute('data-motion', 'reduced');
    expect(root).toHaveAttribute('data-atmosphere', 'off');
    expect(screen.getByTestId('showcase-section-hero')).toHaveClass('is-static');
    // the atmosphere control explains why it is locked
    const atmo = screen.getByTestId('atmosphere-control');
    within(atmo)
      .getAllByRole('radio')
      .forEach((r) => expect(r).toBeDisabled());
    expect(screen.getByText(/reduced motion/i)).toBeInTheDocument();
    // a botch shows its end state (crack + dried drips), no animation
    const stage = rollForced('classic', 'botch');
    expect(stage.querySelector('.sr-rollfx')).toHaveClass('is-static');
    expect(stage.querySelector('.sr-rollfx__static-drips')).not.toBeNull();
    // sections are visible without waiting for a scroll reveal
    expect(screen.getByTestId('showcase-section-editions')).toHaveClass('is-in');
  } finally {
    restore();
  }
});

test('atmosphere control switches the level for the whole app', () => {
  const restore = mockMotion(false);
  try {
    const { container } = renderPage();
    const root = container.querySelector('.sr-app');
    expect(root).toHaveAttribute('data-atmosphere', 'full');
    fireEvent.click(within(screen.getByTestId('atmosphere-control')).getByRole('radio', { name: 'Subtle' }));
    expect(root).toHaveAttribute('data-atmosphere', 'subtle');
    expect(screen.getByTestId('showcase-section-hero')).toHaveClass('is-static');
    fireEvent.click(within(screen.getByTestId('atmosphere-control')).getByRole('radio', { name: 'Off' }));
    expect(root).toHaveAttribute('data-motion', 'reduced');
  } finally {
    restore();
  }
});

test('glyph search filters the gallery', () => {
  renderPage();
  fireEvent.change(screen.getByTestId('glyph-search'), { target: { value: 'moon' } });
  expect(screen.getByTestId('glyph-count')).toHaveTextContent('Showing 5 of 97');
  fireEvent.change(screen.getByTestId('glyph-search'), { target: { value: 'zzzz' } });
  expect(screen.getByText(/Nothing in the dark matches/)).toBeInTheDocument();
});

test('the chat scene continues and reads in Greek', () => {
  renderPage();
  const chat = screen.getByTestId('chat-preview');
  expect(within(chat).getByText(/herald is watching the door/)).toBeInTheDocument();
  fireEvent.click(screen.getByTestId('chat-next'));
  fireEvent.click(screen.getByTestId('chat-next'));
  expect(within(chat).getByTestId('outcome-bestial')).toBeInTheDocument();
  act(() => {
    setLanguage('el', { remember: false, save: false });
  });
  expect(within(screen.getByTestId('chat-preview')).getByText(/κήρυκας του Prince/)).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'Ρίξε τα κόκαλα' })).toBeInTheDocument();
});
