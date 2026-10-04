import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import DiceRollOverlay from '../DiceRollOverlay';

const classicOverlay = (patch = {}) => ({
  visible: true,
  settled: false,
  animationId: 'a1',
  rulesEdition: 'classic',
  difficulty: 6,
  diceFinal: [10, 4, 7],
  diceRolling: [3, 3, 3],
  hungerFlags: [false, false, false],
  extraDiceCount: 0,
  specialtyRerolls: [8],
  result: { rules_edition: 'classic', difficulty: 6, successes: 3, specialty: true },
  ...patch,
});

describe('DiceRollOverlay a11y', () => {
  it('closes on Escape', () => {
    const onDismiss = jest.fn();
    render(<DiceRollOverlay overlay={classicOverlay()} onDismiss={onDismiss} />);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it('never steals focus from what the user is typing in', () => {
    const input = document.createElement('input');
    document.body.appendChild(input);
    input.focus();
    const { rerender } = render(<DiceRollOverlay overlay={classicOverlay()} onDismiss={() => {}} />);
    expect(input).toHaveFocus();
    rerender(<DiceRollOverlay overlay={classicOverlay({ settled: true })} onDismiss={() => {}} />);
    expect(input).toHaveFocus();
    input.remove();
  });

  it('announces the settled outcome in a polite live region', () => {
    const { rerender } = render(<DiceRollOverlay overlay={classicOverlay()} onDismiss={() => {}} />);
    const live = screen.getByTestId('dice-overlay-live');
    expect(live).toHaveAttribute('aria-live', 'polite');
    expect(live).toHaveTextContent('');
    rerender(<DiceRollOverlay overlay={classicOverlay({ settled: true })} onDismiss={() => {}} />);
    expect(screen.getByTestId('dice-overlay-live')).toHaveTextContent(/Dice result: Success \(3 successes\)/);
  });

  it('shows classic specialty reroll dice, marked, once settled', () => {
    const { rerender } = render(<DiceRollOverlay overlay={classicOverlay()} onDismiss={() => {}} />);
    expect(screen.queryByTestId('specialty-rerolls')).toBeNull();
    rerender(<DiceRollOverlay overlay={classicOverlay({ settled: true })} onDismiss={() => {}} />);
    const group = screen.getByTestId('specialty-rerolls');
    expect(group).toHaveAttribute('aria-label', 'Specialty rerolls: 8');
    expect(screen.getByTitle('Specialty reroll: 8')).toBeInTheDocument();
  });
});
