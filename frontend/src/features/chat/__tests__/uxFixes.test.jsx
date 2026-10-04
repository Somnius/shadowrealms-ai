import React from 'react';
import { act, render, screen } from '@testing-library/react';
import { setLanguage } from '../../../i18n';
import { DesignProvider } from '../../../design';
import { DiceCard, rollReasonFrom } from '../Messages';
import { localizeRoom } from '../../play/ChannelList';
import { initials } from '../../../app/ChronicleRail';
import { translateSheetError } from '../../../characterSheet/i18nErrors';

test('dice card is built from the marker: reason + translated summary, not the English text block', () => {
  const marker = {
    animation_id: 'r1-a', rules_edition: 'v5', difficulty: 3, successes: 4, margin: 1, outcome: 'win',
    dice_preview: [7, 9, 2, 6], hunger_flags: [false, false, true, true], extra_dice_count: 0, pool_size: 4, roll_kind: 'manual',
  };
  const message = {
    id: 5, user_id: 1, username: 'lef', ai_message_kind: 'dice_roll:r1-a', created_at: new Date().toISOString(),
    content: '🎲 **Yorika** rolls (V5) for **Brawl**\nDice: [✓7] [✓9] | Hunger: [🩸2] [🩸✓6]\n✅ **Win** (4 successes vs difficulty 3)',
  };
  const { container } = render(<DesignProvider><DiceCard message={message} marker={marker} now={Date.now()} /></DesignProvider>);
  expect(screen.getByText('Brawl')).toBeInTheDocument();
  expect(screen.getByText('4 successes vs difficulty 3 · margin +1')).toBeInTheDocument();
  expect(container.textContent).not.toContain('✅');
  expect(container.textContent).not.toContain('rolls (V5)');
});

test('roll reason: server default label and Willpower reroll suffix are recognised', () => {
  expect(rollReasonFrom('🎲 **A** rolls (V5) for **Dice roll**\nDice')).toEqual({ reason: '', reroll: false });
  expect(rollReasonFrom('🎲 **A** rolls (V5) for **Dice roll (Willpower reroll)**')).toEqual({ reason: '', reroll: true });
  expect(rollReasonFrom('🎲 **A** rolls for **Sneak**')).toEqual({ reason: 'Sneak', reroll: false });
});

test('the server default OOC lobby is shown translated; renamed rooms stay as written', () => {
  const lobby = { id: 1, type: 'ooc', name: 'Out of Character Lobby', description: 'A place for players to discuss the campaign, ask questions, and chat as themselves (not as characters). This is the default meeting place before entering the game world.' };
  expect(localizeRoom(lobby).name).toBe('Out of Character Lobby');
  expect(localizeRoom({ ...lobby, name: 'Η ταβέρνα' }).name).toBe('Η ταβέρνα');
});

test('rail initials drop Greek accents (no "ΥΈ")', () => {
  expect(initials('Υπόγεια Έπαυλη')).toBe('ΥΕ');
  expect(initials('Άθως')).toBe('ΑΘ');
  expect(initials('Night Court')).toBe('NC');
});

test('in Greek: V5 discipline errors and the default OOC lobby are translated', async () => {
  await act(async () => {
    await setLanguage('el', { remember: false, save: false });
  });
  try {
    expect(translateSheetError('Pick two clan Disciplines: one at 2 dots and one at 1 dot.')).toBe('Διάλεξε δύο Disciplines του clan: μία με 2 τελείες και μία με 1.');
    expect(translateSheetError('Thin-bloods start with no Disciplines.')).toBe('Οι thin-bloods ξεκινούν χωρίς Disciplines.');
    expect(localizeRoom({ id: 1, type: 'ooc', name: 'Out of Character Lobby' }).name).toBe('Χώρος εκτός ρόλου');
  } finally {
    await act(async () => {
      await setLanguage('en', { remember: false, save: false });
    });
  }
});
