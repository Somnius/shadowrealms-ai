import { guessLang, plainText, readoutKind, shouldRead, spokenText } from '../readout';

const ALL = { storyteller: true, ic: true, ooc: true, dice: true, actions: true };
const ai = { id: 1, role: 'assistant', content: 'The **door** creaks.' };
const ic = { id: 2, user_id: 5, username: 'lef', character_id: 7, character_name: 'Ioannis', speaker_mode: 'character', content: 'I look around.' };
const ooc = { id: 3, user_id: 5, username: 'lef', speaker_mode: 'player', content: 'brb' };
const st = { id: 4, user_id: 2, username: 'maria', speaker_mode: 'staff', staff_kind: 'storyteller', content: 'Night falls.' };
const dice = { id: 5, user_id: 5, username: 'lef', character_id: 7, character_name: 'Ioannis', ai_message_kind: 'dice_roll:abc', content: '🎲 rolls 5 dice: **3 successes**\nmore' };
const marker = { id: 6, ai_message_kind: 'dice_animation:abc', content: '{}' };
const sys = { id: 7, message_type: 'system', content: 'Room closed' };
const act = { id: 8, user_id: 5, message_type: 'action', content: 'Ioannis kneels.' };

test.each([
  [ai, ALL, 9, true],
  [ai, { ...ALL, storyteller: false }, 9, false],
  [st, { ...ALL, storyteller: false }, 9, false],
  [ic, ALL, 9, true],
  [ic, { ...ALL, ic: false }, 9, false],
  [ic, ALL, 5, false], // own line skipped
  [ooc, { ...ALL, ooc: false }, 9, false],
  [ooc, ALL, 9, true],
  [dice, { ...ALL, dice: false }, 9, false],
  [dice, ALL, 9, true],
  [act, { ...ALL, actions: false }, 9, false],
  [marker, ALL, 9, false],
  [sys, ALL, 9, false],
  [{ ...ic, content: '  ' }, ALL, 9, false],
])('shouldRead %#', (msg, rules, me, want) => {
  expect(shouldRead(msg, rules, me)).toBe(want);
});

test('kinds, plain text, dice as one sentence, language guess', () => {
  expect(readoutKind(st)).toBe('storyteller');
  expect(plainText('**Hi** [there](http://x) 🎲')).toBe('Hi there');
  expect(spokenText(dice)).toBe('Ioannis: rolls 5 dice: 3 successes');
  expect(spokenText(ic)).toBe('Ioannis: I look around.');
  expect(spokenText(ai)).toBe('The door creaks.');
  expect(guessLang('Σηκώνομαι αργά')).toBe('el');
  expect(guessLang('I get up')).toBe('en');
});
