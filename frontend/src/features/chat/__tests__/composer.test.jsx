import { render, screen, waitFor } from '@testing-library/react';
import setupUser from '../../../design/testing/setupUser';
import { DesignProvider } from '../../../design';
import Composer, { voiceOptions } from '../Composer';

const user = { id: 1, username: 'lef' };
const character = { id: 7, name: 'Yorika' };

beforeEach(() => sessionStorage.clear());

function renderComposer(props = {}) {
  const onSend = props.onSend || jest.fn().mockResolvedValue(true);
  const onRoll = props.onRoll || jest.fn();
  const utils = render(
    <DesignProvider>
      <Composer
        roomName="Elysium"
        speakAs="character"
        voices={voiceOptions({ character, user, canStaff: false })}
        onSpeakAsChange={props.onSpeakAsChange || jest.fn()}
        character={character}
        onSend={onSend}
        onRoll={onRoll}
        isAdmin={!!props.isAdmin}
        draftKey={props.draftKey || "r1"}
      />
    </DesignProvider>
  );
  const input = screen.getByRole('combobox', { name: /message elysium/i });
  return { ...utils, input, onSend, onRoll };
}

test('Enter sends and clears; Shift+Enter inserts a newline', async () => {
  const u = setupUser();
  const { input, onSend } = renderComposer();
  await u.type(input, 'first line');
  await u.keyboard('{Shift>}{Enter}{/Shift}');
  await u.type(input, 'second line');
  expect(input.value).toBe('first line\nsecond line');
  expect(onSend).not.toHaveBeenCalled();
  await u.keyboard('{Enter}');
  expect(onSend).toHaveBeenCalledWith('first line\nsecond line', null);
  await waitFor(() => expect(input.value).toBe(''));
});

test('whitespace-only lines are not sent', async () => {
  const u = setupUser();
  const { input, onSend } = renderComposer();
  await u.type(input, '   {Enter}');
  expect(onSend).not.toHaveBeenCalled();
});

test('a failed send puts the text back so nothing is lost', async () => {
  const u = setupUser();
  const onSend = jest.fn().mockResolvedValue(false);
  const { input } = renderComposer({ onSend });
  await u.type(input, 'important words{Enter}');
  await waitFor(() => expect(input.value).toBe('important words'));
});

test('placeholder reflects the voice', () => {
  const { input } = renderComposer();
  expect(input).toHaveAttribute('placeholder', expect.stringMatching(/Speak as Yorika/));
});

test('typing / opens the command list; arrows + Tab complete, Esc closes', async () => {
  const u = setupUser();
  const { input } = renderComposer();
  await u.type(input, '/');
  const list = screen.getByRole('listbox', { name: /commands/i });
  expect(input).toHaveAttribute('aria-expanded', 'true');
  const options = screen.getAllByRole('option');
  expect(options[0]).toHaveAttribute('aria-selected', 'true');
  await u.keyboard('{ArrowDown}');
  expect(screen.getAllByRole('option')[1]).toHaveAttribute('aria-selected', 'true');
  expect(input.getAttribute('aria-activedescendant')).toBe(screen.getAllByRole('option')[1].id);
  await u.keyboard('{Tab}');
  expect(input.value).toBe('/me ');
  expect(list).toBeInTheDocument();
  await u.keyboard('{Escape}');
  expect(screen.queryByRole('listbox')).toBeNull();
  expect(input).toHaveAttribute('aria-expanded', 'false');
});

test('/roll + Enter opens the roller instead of sending text', async () => {
  const u = setupUser();
  const { input, onSend, onRoll } = renderComposer();
  await u.type(input, '/roll');
  await u.keyboard('{Enter}');
  expect(onRoll).toHaveBeenCalledTimes(1);
  expect(onSend).not.toHaveBeenCalled();
  expect(input.value).toBe('');
});

test('/me text is passed on as an action', async () => {
  const u = setupUser();
  const { input, onSend } = renderComposer();
  await u.type(input, '/me draws a blade{Enter}');
  expect(onSend).toHaveBeenCalledWith('/me draws a blade', { type: 'me', text: 'draws a blade' });
});

test('admins see /ai commands; players do not', async () => {
  const u = setupUser();
  const { input, unmount } = renderComposer({ isAdmin: true });
  await u.type(input, '/ai h');
  expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual(expect.arrayContaining([expect.stringContaining('/ai help')]));
  unmount();
  const p = renderComposer({ isAdmin: false });
  await u.type(p.input, '/ai');
  expect(screen.queryByRole('listbox')).toBeNull();
});

test('the speaking-as control switches voice from the menu', async () => {
  const u = setupUser();
  const onSpeakAsChange = jest.fn();
  renderComposer({ onSpeakAsChange });
  await u.click(screen.getByRole('button', { name: /speaking as yorika/i }));
  await u.click(screen.getByRole('menuitemradio', { name: /lef \(out of character\)/i }));
  expect(onSpeakAsChange).toHaveBeenCalledWith('player');
});

test('the unsent draft survives a remount (language switch) and is per room; sending clears it', async () => {
  const u = setupUser();
  const first = renderComposer({ draftKey: '1:3:7' });
  await u.type(first.input, 'half a thought');
  first.unmount();
  const second = renderComposer({ draftKey: '1:3:7' });
  expect(second.input.value).toBe('half a thought');
  second.unmount();
  const other = renderComposer({ draftKey: '1:3:8' });
  expect(other.input.value).toBe('');
  other.unmount();
  const again = renderComposer({ draftKey: '1:3:7' });
  await u.type(again.input, '{Enter}');
  await waitFor(() => expect(again.input.value).toBe(''));
  expect(sessionStorage.getItem('sr_draft_1:3:7')).toBeNull();
});
