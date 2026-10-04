import { act, fireEvent, render, screen } from '@testing-library/react';
import { DesignProvider } from '../../../design';
import { setLanguage } from '../../../i18n';
import { MessageGroup } from '../../chat/Messages';
import { RollDialog } from '../DiceDialogs';
import RollRequestChips, { RollRequestContext } from '../RollRequestChips';
import { parseRollRequests, parseRollTag, rollPrefill, rollRequestText, rollRequestsOf, stripRollTags } from '../rollRequests';

const V5_TEXT =
  'The guard turns away. [[roll: Dexterity + Stealth | 4 dice | 2 hunger | difficulty 3]]\n' +
  'Or talk: [[roll: Charisma + Persuasion | specialty Seduction | 8 dice | 2 hunger | difficulty 2]]';
const CLASSIC_TEXT = 'Quietly now. [[roll: Dexterity + Security | 2 dice | difficulty 7 | untrained Skill: +1 difficulty]]';

const aiMessage = (content, extra = {}) => ({
  id: 41, role: 'assistant', user_id: 5, username: 'eleni_player', content, created_at: new Date().toISOString(), ...extra,
});

function withRoller(ui, { userId = 5, onRoll = jest.fn() } = {}) {
  return render(
    <DesignProvider>
      <RollRequestContext.Provider value={{ userId, onRoll }}>{ui}</RollRequestContext.Provider>
    </DesignProvider>
  );
}

test('canonical tags parse per edition; unresolved or foreign brackets are ignored', () => {
  expect(parseRollRequests(V5_TEXT)).toEqual([
    { label: 'Dexterity + Stealth', pool: 4, hunger: 2, difficulty: 3, specialty: null, notes: [], edition: 'v5' },
    { label: 'Charisma + Persuasion', pool: 8, hunger: 2, difficulty: 2, specialty: 'Seduction', notes: [], edition: 'v5' },
  ]);
  expect(parseRollRequests(CLASSIC_TEXT)).toEqual([
    { label: 'Dexterity + Security', pool: 2, hunger: 0, difficulty: 7, specialty: null, notes: ['untrained Skill: +1 difficulty'], edition: 'classic' },
  ]);
  expect(parseRollTag('Dexterity + Stealth, difficulty 3')).toBeNull(); // the model's own tag, never resolved
  expect(parseRollRequests('No [[dice]] here, [a](https://x.y)')).toEqual([]);
});

test('tags become bold labels in the text', () => {
  expect(stripRollTags(CLASSIC_TEXT)).toBe('Quietly now. **Dexterity + Security**');
  expect(stripRollTags('Keep [[roll: Wits + Awareness]] as written')).toBe('Keep [[roll: Wits + Awareness]] as written');
});

test('structured roll_requests from the API win over the text; only Storyteller messages count', () => {
  const api = [{ edition: 'v5', label: 'Wits + Awareness', pool: 4, hunger: 2, difficulty: 2, specialty: null, character_id: 7 }];
  expect(rollRequestsOf(aiMessage(V5_TEXT, { roll_requests: api }))).toEqual(api);
  expect(rollRequestsOf(aiMessage(V5_TEXT))).toHaveLength(2);
  expect(rollRequestsOf({ ...aiMessage(V5_TEXT), role: 'user' })).toEqual([]);
});

test('chip text and dialog pre-fill', () => {
  const [stealth, charm] = parseRollRequests(V5_TEXT);
  expect(rollRequestText(stealth)).toBe('Dexterity + Stealth (4 dice, 2 Hunger, 3 needed)');
  expect(rollRequestText(charm)).toBe('Charisma + Persuasion, Seduction specialty (8 dice, 2 Hunger, 2 needed)');
  const [sec] = parseRollRequests(CLASSIC_TEXT);
  expect(rollRequestText(sec)).toBe('Dexterity + Security (2 dice, diff 7)');
  expect(rollRequestText({ ...sec, pool: 1, difficulty: null })).toBe('Dexterity + Security (1 die)');
  expect(rollPrefill(charm)).toEqual({ pool: '8', v5Difficulty: 2, hunger: 2, reason: 'Charisma + Persuasion (Seduction)' });
  expect(rollPrefill(sec)).toEqual({ pool: '2', difficulty: 7, specialty: false, reason: 'Dexterity + Security' });
});

test('the player who asked gets a Roll button that hands the request over', () => {
  const onRoll = jest.fn();
  withRoller(<RollRequestChips message={aiMessage(V5_TEXT)} />, { onRoll });
  const buttons = screen.getAllByRole('button');
  expect(buttons).toHaveLength(2);
  expect(buttons[0]).toHaveTextContent('Roll: Dexterity + Stealth (4 dice, 2 Hunger, 3 needed)');
  fireEvent.click(buttons[1]);
  expect(onRoll).toHaveBeenCalledWith(expect.objectContaining({ label: 'Charisma + Persuasion', pool: 8, specialty: 'Seduction' }));
});

test('other players see the chip text only', () => {
  withRoller(<RollRequestChips message={aiMessage(V5_TEXT)} />, { userId: 99 });
  expect(screen.queryAllByRole('button')).toHaveLength(0);
  expect(screen.getByText('Roll: Dexterity + Stealth (4 dice, 2 Hunger, 3 needed)')).toBeInTheDocument();
  // no play view (no onRoll): text only as well
  render(<DesignProvider><RollRequestChips message={aiMessage(CLASSIC_TEXT)} /></DesignProvider>);
  expect(screen.queryAllByRole('button')).toHaveLength(0);
});

test('a Storyteller message shows its text without the raw tags, chips below', () => {
  const { container } = withRoller(<MessageGroup group={{ kind: 'ai', messages: [aiMessage(V5_TEXT)] }} now={Date.now()} />);
  expect(container.textContent).not.toContain('[[roll');
  expect(container.textContent).toContain('The guard turns away. Dexterity + Stealth');
  expect(screen.getAllByRole('button')).toHaveLength(2);
});

test('in Greek the chip is translated', async () => {
  await act(async () => {
    await setLanguage('el', { remember: false, save: false });
  });
  try {
    const [stealth] = parseRollRequests(V5_TEXT);
    expect(rollRequestText(stealth)).toBe('Dexterity + Stealth (4 ζάρια, 2 Hunger, χρειάζονται 3)');
    expect(rollRequestText(parseRollRequests(CLASSIC_TEXT)[0])).toBe('Dexterity + Security (2 ζάρια, δυσκολία 7)');
  } finally {
    await act(async () => {
      await setLanguage('en', { remember: false, save: false });
    });
  }
});

function renderDialog({ edition, prefill, character }) {
  const dice = { rolling: false, rousing: false, roll: jest.fn(async () => true), rouse: jest.fn() };
  render(
    <DesignProvider>
      <RollDialog
        open
        onClose={() => {}}
        campaign={{ id: 8, rules_edition: edition }}
        location={{ id: 16, name: 'Plaka Rooftops' }}
        character={character}
        speakAs="character"
        canHide={false}
        isAdmin={false}
        dice={dice}
        onOpenHistory={() => {}}
        prefill={prefill}
      />
    </DesignProvider>
  );
  return dice;
}

test('V5 roll dialog opens pre-filled; Hunger follows the sheet and the roll sends it', async () => {
  const [, charm] = parseRollRequests(V5_TEXT);
  const dice = renderDialog({ edition: 'v5', prefill: rollPrefill(charm), character: { id: 7, name: 'Eleni', wod_meta: { hunger: 3 } } });
  expect(screen.getByLabelText(/Dice pool/)).toHaveValue('8');
  expect(document.getElementById('roll-v5-difficulty')).toHaveValue('2');
  expect(document.getElementById('roll-v5-hunger')).toHaveValue('3'); // the sheet now, not the request's 2
  expect(screen.getByLabelText(/What are you rolling for/)).toHaveValue('Charisma + Persuasion (Seduction)');
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: /Roll & post/ }));
  });
  expect(dice.roll).toHaveBeenCalledWith(expect.objectContaining({ pool: '8', v5Difficulty: 2, hunger: 3, reason: 'Charisma + Persuasion (Seduction)' }));
});

test('classic roll dialog opens pre-filled with difficulty and specialty', () => {
  const req = { ...parseRollRequests(CLASSIC_TEXT)[0], specialty: 'Locks' };
  renderDialog({ edition: 'classic', prefill: rollPrefill(req), character: { id: 8, name: 'Theodore' } });
  expect(screen.getByLabelText(/Dice pool/)).toHaveValue('2');
  expect(document.getElementById('roll-classic-difficulty')).toHaveValue('7');
  expect(screen.getByLabelText(/Specialty/)).toBeChecked();
});
