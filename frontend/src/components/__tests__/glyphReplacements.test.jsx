/**
 * Phase 4: emoji / Font Awesome icons were replaced with original design glyphs. The replacements
 * must keep accessible names (or be hidden when the text already says it), and no icon-font
 * markup may remain in these components.
 */
import React from 'react';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import setupUser from '../../design/testing/setupUser';
import { DesignProvider } from '../../design/motion';
import DiceRollOverlay from '../dice/DiceRollOverlay';
import DiceFace from '../dice/DiceFace';
import OutcomeBadges from '../dice/OutcomeBadges';
import V5RerollPanel from '../dice/V5RerollPanel';
import RollEditionFields from '../dice/RollEditionFields';
import Footer from '../Footer';
import { GothicBox } from '../GothicDecorations';
import UserMenu from '../../app/UserMenu';

jest.mock('../../app/AuthContext', () => ({
  useAuth: () => ({ user: { id: 1, username: 'lef', role: 'player' }, isAdmin: false, logout: () => {} }),
}));

const noIconFont = (container) => {
  expect(container.querySelector('i.fas, i.fa, [class*="fa-"]')).toBeNull();
};

beforeEach(() => window.localStorage.clear());

test('dice overlay: d10 glyphs, accessible dialog name, no icon font', () => {
  const { container } = render(
    <DiceRollOverlay
      overlay={{
        visible: true,
        settled: true,
        animationId: 'x',
        rulesEdition: 'v5',
        difficulty: 2,
        diceFinal: [10, 6, 1],
        diceRolling: [10, 6, 1],
        hungerFlags: [false, false, true],
        extraDiceCount: 0,
        result: { rules_edition: 'v5', difficulty: 2, successes: 2, outcome: 'win' },
      }}
      onDismiss={() => {}}
    />
  );
  expect(screen.getByRole('dialog', { name: 'Dice roll result (Escape to close)' })).toBeInTheDocument();
  expect(container.querySelectorAll('svg.sr-die')).toHaveLength(3);
  // the Hunger 1 is marked bestial with a (decorative) skull, and the die keeps its name
  expect(screen.getByTitle('Hunger die: 1')).toBeInTheDocument();
  expect(container.querySelector('.sr-ldie__mark--bestial svg[data-glyph="skull"]')).toHaveAttribute('aria-hidden', 'true');
  noIconFont(container);
});

test('a selectable die is a toggle button named by its title', async () => {
  const user = setupUser();
  const onClick = jest.fn();
  render(<DiceFace value={4} edition="v5" onClick={onClick} title="Normal die 4" />);
  const btn = screen.getByRole('button', { name: 'Normal die 4' });
  expect(btn).toHaveAttribute('aria-pressed', 'false');
  await user.click(btn);
  expect(onClick).toHaveBeenCalled();
});

test('outcome badges carry a glyph and the outcome text', () => {
  render(<OutcomeBadges result={{ rules_edition: 'classic', successes: 0, is_botch: true }} />);
  const badge = screen.getByTestId('outcome-botch');
  expect(badge).toHaveTextContent('Botch');
  expect(badge.querySelector('svg[data-glyph="d10-botch"]')).not.toBeNull();
});

test('V5 reroll panel uses named design buttons', () => {
  const { container } = render(
    <V5RerollPanel
      roll={{ roll_id: 1, normal_dice: [3, 8], hunger_dice: [1], difficulty: 2, successes: 1, outcome: 'fail', is_bestial_failure: true }}
      onReroll={() => {}}
      onDismiss={() => {}}
    />
  );
  const panel = screen.getByRole('region', { name: 'Willpower reroll' });
  expect(within(panel).getByRole('button', { name: 'Close' })).toBeInTheDocument();
  expect(within(panel).getByRole('button', { name: /Reroll with Willpower/ })).toBeDisabled();
  noIconFont(container);
});

test('roll fields: labelled selects and a named Rouse check button', () => {
  render(
    <RollEditionFields
      edition="v5"
      v5Difficulty={1}
      setV5Difficulty={() => {}}
      hunger={2}
      setHunger={() => {}}
      onRouse={() => {}}
    />
  );
  expect(screen.getByLabelText('Difficulty (successes needed)')).toHaveValue('1');
  expect(screen.getByRole('button', { name: 'Rouse check' })).toBeInTheDocument();
});

test('footer: the heart is a named glyph, no emoji left', () => {
  const { container } = render(<Footer />);
  expect(screen.getByRole('img', { name: 'love' })).toBeInTheDocument();
  expect(container.textContent).not.toMatch(/[♥\u{1F916}]/u);
});

test('GothicBox renders an ornate card without icon font hands', () => {
  const { container } = render(
    <GothicBox theme="vampire">
      <p>inside</p>
    </GothicBox>
  );
  expect(container.querySelector('.sr-card--ornate')).not.toBeNull();
  noIconFont(container);
});

test('user menu: the Atmosphere setting is a radio group that persists', async () => {
  const user = setupUser();
  const { container } = render(
    <DesignProvider>
      <MemoryRouter>
        <UserMenu />
      </MemoryRouter>
    </DesignProvider>
  );
  await user.click(screen.getByRole('button', { name: 'Account menu for lef' }));
  const full = screen.getByRole('menuitemradio', { name: /Full/ });
  expect(full).toHaveAttribute('aria-checked', 'true');
  await user.click(screen.getByRole('menuitemradio', { name: /Subtle/ }));
  expect(window.localStorage.getItem('sr_atmosphere')).toBe('subtle');
  expect(container.firstChild).toHaveAttribute('data-atmosphere', 'subtle');
  await user.click(screen.getByRole('button', { name: 'Account menu for lef' }));
  expect(screen.getByRole('menuitemradio', { name: /Subtle/ })).toHaveAttribute('aria-checked', 'true');
  await user.click(screen.getByRole('menuitemradio', { name: /Off/ }));
  expect(container.firstChild).toHaveAttribute('data-motion', 'reduced');
});
