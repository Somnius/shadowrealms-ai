import React from 'react';
import { act, render, renderHook, screen, waitFor, within } from '@testing-library/react';
import setupUser from '../../../design/testing/setupUser';
import { DesignProvider } from '../../../design';
import MessageList from '../MessageList';
import Composer from '../Composer';
import { MessageActionsContext, ReplyQuote, deleteErrorText, jumpToMessage, useMessageActions } from '../MessageActions';
import { anchoredScrollTop, canDeleteMessage, copyTextOf, excerptOf, replyTargetOf } from '../messageActions';
import { mergeRefresh, useRoomMessages } from '../useRoomMessages';
import { optimisticMessage, sendChatMessage } from '../sendFlow';

const OWNER = { id: 1, username: 'st', role: 'player' };
const PLAYER = { id: 2, username: 'ann', role: 'player' };
const OTHER = { id: 3, username: 'bob', role: 'player' };
const ADMIN = { id: 9, username: 'root', role: 'admin' };
const HELPER = { id: 8, username: 'help', role: 'helper' };
const campaign = { id: 1, created_by: 1 };

const at = (min) => new Date(Date.UTC(2026, 9, 4, 20, min)).toISOString();
const ok = (data) => ({ ok: true, status: 200, data });

const own = { id: 10, user_id: 2, username: 'ann', role: 'user', speaker_mode: 'player', content: 'my line', created_at: at(0) };
const others = { id: 11, user_id: 3, username: 'bob', role: 'user', speaker_mode: 'player', content: 'his line', created_at: at(1) };
const ai = { id: 12, user_id: 2, username: 'ann', role: 'assistant', content: 'The night falls. Roll [[roll: Wits + Awareness | 5 dice | difficulty 6]].', created_at: at(2) };
const marker = { id: 13, user_id: 2, role: 'assistant', ai_message_kind: 'dice_animation:r1-a', content: '{}', created_at: at(3) };
const dice = { id: 14, user_id: 2, username: 'ann', role: 'user', speaker_mode: 'player', ai_message_kind: 'dice_roll:r1-a', message_type: 'action', content: 'ann rolls', created_at: at(3) };
const ROOM = [own, others, ai, marker, dice];

describe('who may delete (mirrors the server rules)', () => {
  test.each([
    ['player: own line', PLAYER, own, true],
    ['player: someone else’s line', PLAYER, others, false],
    ['player: own dice roll', PLAYER, dice, false],
    ['player: AI line they triggered', PLAYER, ai, false],
    ['player: Rouse line', PLAYER, { ...own, ai_message_kind: 'dice_rouse:4' }, false],
    ['storyteller: anything', OWNER, others, true],
    ['storyteller: dice', OWNER, dice, true],
    ['storyteller: AI', OWNER, ai, true],
    ['admin: anything', ADMIN, dice, true],
    ['admin: AI', ADMIN, ai, true],
    ['helper is not staff for deletes', HELPER, others, false],
    ['optimistic row: nothing yet', PLAYER, { ...own, id: null, temp: true }, false],
    ['signed out', null, own, false],
  ])('%s', (_label, user, msg, expected) => {
    expect(canDeleteMessage(msg, { user, campaign })).toBe(expected);
  });
});

test('copy text drops roll tags from AI lines; excerpt is one plain line', () => {
  expect(copyTextOf(ai)).toBe('The night falls. Roll **Wits + Awareness**.');
  expect(copyTextOf(own)).toBe('my line');
  expect(excerptOf('**Bold**\n\n_it_')).toBe('Bold it');
  expect(excerptOf('x'.repeat(300))).toHaveLength(140);
  expect(replyTargetOf(ai)).toEqual({ id: 12, author: '', excerpt: 'The night falls. Roll Wits + Awareness.', role: 'assistant' });
  expect(replyTargetOf(others)).toMatchObject({ id: 11, author: 'bob', excerpt: 'his line', role: 'user' });
});

test('delete errors are translated from the server codes', () => {
  expect(deleteErrorText({ data: { code: 'dice_message_staff_only', error: 'x' } })).toBe('Only the Storyteller or an admin can delete dice rolls.');
  expect(deleteErrorText({ data: { code: 'ai_message_staff_only' } })).toMatch(/Storyteller messages/);
  expect(deleteErrorText({ data: { code: 'message_not_yours' } })).toBe('You can only delete your own messages.');
  expect(deleteErrorText({ data: {} })).toBe('Could not delete the message.');
});

/** A room as PlayPage wires it: messages hook + actions + list + composer + dialog. */
function Room({ api, user, toast = jest.fn(), onSend = jest.fn().mockResolvedValue(true) }) {
  const room = useRoomMessages({ api, campaignId: 1, locationId: 2, userId: user.id });
  const actions = useMessageActions({ api, user, campaign, room, toast });
  return (
    <DesignProvider>
      <MessageActionsContext.Provider value={actions.value}>
        <MessageList
          roomKey="1:2"
          roomName="Haven"
          messages={room.messages}
          status={room.status}
          userId={user.id}
          hasMore={room.hasMore}
          loadingOlder={room.loadingOlder}
          onLoadOlder={room.loadOlder}
        />
      </MessageActionsContext.Provider>
      <Composer roomName="Haven" speakAs="player" voices={[]} onSpeakAsChange={() => {}} onSend={onSend} replyTo={actions.replyTo} onCancelReply={actions.clearReply} draftKey="t" />
      {actions.dialog}
    </DesignProvider>
  );
}

function roomApi(overrides = {}) {
  return jest.fn((path, opts = {}) => {
    if (opts.method === 'DELETE' && overrides.delete) return Promise.resolve(overrides.delete(path));
    if (path.includes('before_id') && overrides.older) return Promise.resolve(overrides.older(path));
    if (path.includes('recent=1')) return Promise.resolve(ok(overrides.rows || ROOM));
    return Promise.resolve(ok([]));
  });
}

const row = (id) => document.getElementById(`msg-${id}`);
const deleteIn = (id) => within(row(id)).queryByRole('button', { name: 'Delete message' });

async function renderRoom(props) {
  const utils = render(<Room {...props} />);
  await waitFor(() => expect(row(10)).not.toBeNull());
  return utils;
}

beforeEach(() => sessionStorage.clear());

describe('actions shown per role', () => {
  test('player: copy + reply everywhere, delete only on their own plain line', async () => {
    await renderRoom({ api: roomApi(), user: PLAYER });
    for (const id of [10, 11, 12, 14]) {
      expect(within(row(id)).getByRole('button', { name: 'Copy text' })).toBeInTheDocument();
      expect(within(row(id)).getByRole('button', { name: 'Reply' })).toBeInTheDocument();
    }
    expect(deleteIn(10)).not.toBeNull();
    expect(deleteIn(11)).toBeNull();
    expect(deleteIn(12)).toBeNull(); // AI
    expect(deleteIn(14)).toBeNull(); // dice
    expect(row(13)).toBeNull(); // markers are never shown
  });

  test.each([['storyteller', OWNER], ['admin', ADMIN]])('%s: delete on every message', async (_l, user) => {
    await renderRoom({ api: roomApi(), user });
    for (const id of [10, 11, 12, 14]) expect(deleteIn(id)).not.toBeNull();
  });

  test('the toolbar is a labelled toolbar; the touch "…" button toggles it', async () => {
    const u = setupUser();
    await renderRoom({ api: roomApi(), user: PLAYER });
    expect(within(row(10)).getByRole('toolbar', { name: 'Message actions' })).toBeInTheDocument();
    const more = within(row(10)).getByRole('button', { name: 'More actions' });
    expect(more).toHaveAttribute('aria-expanded', 'false');
    await u.click(more);
    expect(more).toHaveAttribute('aria-expanded', 'true');
    expect(row(10).querySelector('.sr-msg-actions')).toHaveClass('is-open');
    await u.keyboard('{Escape}');
    expect(more).toHaveAttribute('aria-expanded', 'false');
  });

  test('copy writes the text and says so', async () => {
    const toast = jest.fn();
    const u = setupUser();
    // after setupUser: user-event installs its own clipboard stub
    const writeText = jest.fn().mockResolvedValue();
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
    await renderRoom({ api: roomApi(), user: PLAYER, toast });
    await u.click(within(row(12)).getByRole('button', { name: 'Copy text' }));
    await waitFor(() => expect(toast).toHaveBeenCalledWith({ tone: 'ok', title: 'Copied to the clipboard.' }));
    expect(writeText).toHaveBeenCalledWith('The night falls. Roll **Wits + Awareness**.');
  });
});

describe('reply', () => {
  test('Reply shows "Replying to" in the composer; Esc and the close button cancel it', async () => {
    const u = setupUser();
    await renderRoom({ api: roomApi(), user: PLAYER });
    await u.click(within(row(11)).getByRole('button', { name: 'Reply' }));
    expect(screen.getByText('Replying to bob')).toBeInTheDocument();
    expect(screen.getByText('his line', { selector: '.sr-replybar__excerpt' })).toBeInTheDocument();
    await u.click(screen.getByRole('button', { name: 'Cancel reply' }));
    expect(screen.queryByText('Replying to bob')).toBeNull();

    await u.click(within(row(12)).getByRole('button', { name: 'Reply' }));
    expect(screen.getByText('Replying to Storyteller')).toBeInTheDocument();
    const input = screen.getByRole('combobox', { name: /message haven/i });
    input.focus();
    await u.keyboard('{Escape}');
    expect(screen.queryByText('Replying to Storyteller')).toBeNull();
  });

  test('the sent line carries reply_to_id and its optimistic row shows the quote', async () => {
    const calls = [];
    const api = jest.fn((path, opts) => {
      calls.push([path, opts]);
      if (path === '/campaigns/1/locations/2') return Promise.resolve({ ok: true, status: 201, data: { data: { id: 50 } } });
      return Promise.resolve(ok({ ooc_no_reply: true }));
    });
    const onOptimistic = jest.fn();
    const replyTo = replyTargetOf(others);
    await sendChatMessage(
      { api, campaign, location: { id: 2, type: 'ooc' }, user: PLAYER, speakAs: 'player', onOptimistic },
      'yes, that',
      { replyTo }
    );
    expect(calls[0][1].body.reply_to_id).toBe(11);
    expect(onOptimistic.mock.calls[0][0].reply_to).toEqual({ id: 11, author: 'bob', excerpt: 'his line', role: 'user' });
    expect(optimisticMessage({ text: 'x', user: PLAYER, campaign, location: { id: 2 }, speakAs: 'player' }).reply_to).toBeNull();
  });

  test('a deleted reply target: translated error, reply cleared by the caller', async () => {
    const api = jest.fn(() => Promise.resolve({ ok: false, status: 400, data: { code: 'reply_target_not_found', error: 'x' } }));
    const onError = jest.fn();
    const onReplyGone = jest.fn();
    const sent = await sendChatMessage(
      { api, campaign, location: { id: 2, type: 'ooc' }, user: PLAYER, speakAs: 'player', onError, onReplyGone },
      'hello',
      { replyTo: { id: 99 } }
    );
    expect(sent).toBe(false);
    expect(onReplyGone).toHaveBeenCalled();
    expect(onError).toHaveBeenCalledWith('The message you replied to is gone. Your text is still in the box.');
  });

  test('a reply renders a compact quote; clicking it jumps to the original when loaded', async () => {
    const u = setupUser();
    const reply = { ...own, id: 20, created_at: at(5), reply_to: { id: 11, author: 'bob', excerpt: 'his line', role: 'user' } };
    await renderRoom({ api: roomApi({ rows: [...ROOM, reply] }), user: PLAYER });
    const target = row(11);
    target.scrollIntoView = jest.fn();
    await u.click(within(row(20)).getByRole('button', { name: /Replying to bob: his line/ }));
    expect(target.scrollIntoView).toHaveBeenCalled();
    expect(target).toHaveClass('is-flash');
    expect(document.activeElement).toBe(target);
  });

  test('quote of a message that is not loaded: tells you where it is', async () => {
    const onJump = jest.fn();
    render(
      <MessageActionsContext.Provider value={{ onJump }}>
        <ReplyQuote reply={{ id: 3, author: 'bob', excerpt: 'old', role: 'user' }} />
      </MessageActionsContext.Provider>
    );
    screen.getByRole('button').click();
    expect(onJump).toHaveBeenCalledWith(3);
    expect(jumpToMessage(3)).toBe(false);
  });

  test('a quoted hidden roll shows no text and is not a link', () => {
    render(
      <MessageActionsContext.Provider value={{ onJump: jest.fn() }}>
        <ReplyQuote reply={{ id: 3, author: '', excerpt: '', hidden: true }} />
      </MessageActionsContext.Provider>
    );
    expect(screen.getByText('Hidden roll')).toBeInTheDocument();
    expect(screen.queryByRole('button')).toBeNull();
  });
});

describe('delete', () => {
  async function confirmDelete(u, id) {
    await u.click(deleteIn(id));
    const dialog = await screen.findByRole('dialog', { name: 'Delete this message?' });
    await u.click(within(dialog).getByRole('button', { name: 'Delete' }));
  }

  test('optimistic: the row goes at once; a roll’s marker row goes with it', async () => {
    let resolve;
    const api = roomApi({ delete: () => new Promise((r) => (resolve = r)) });
    api.mockImplementation((path, opts = {}) => {
      if (opts.method === 'DELETE') return new Promise((r) => (resolve = r));
      return Promise.resolve(ok(path.includes('recent=1') ? ROOM : []));
    });
    const u = setupUser();
    await renderRoom({ api, user: OWNER });
    await confirmDelete(u, 14);
    expect(row(14)).toBeNull(); // before the server answered
    expect(api).toHaveBeenCalledWith('/messages/14', { method: 'DELETE' });
    await act(async () => resolve(ok({ deleted_ids: [13, 14] })));
    expect(row(14)).toBeNull();
  });

  test('rollback: a refused delete puts the row back and says why', async () => {
    let resolve;
    const api = jest.fn((path, opts = {}) => {
      if (opts.method === 'DELETE') return new Promise((r) => (resolve = r));
      return Promise.resolve(ok(path.includes('recent=1') ? ROOM : []));
    });
    const toast = jest.fn();
    const u = setupUser();
    await renderRoom({ api, user: PLAYER, toast });
    await confirmDelete(u, 10);
    expect(row(10)).toBeNull();
    await act(async () => resolve({ ok: false, status: 403, data: { code: 'message_not_yours', error: 'x' } }));
    await waitFor(() => expect(row(10)).not.toBeNull());
    expect(toast).toHaveBeenCalledWith({ tone: 'danger', title: 'You can only delete your own messages.' });
  });

  test('cancel keeps the message', async () => {
    const api = roomApi();
    const u = setupUser();
    await renderRoom({ api, user: PLAYER });
    await u.click(deleteIn(10));
    const dialog = await screen.findByRole('dialog');
    await u.click(within(dialog).getByRole('button', { name: 'Keep it' }));
    expect(row(10)).not.toBeNull();
    expect(api.mock.calls.some(([, o]) => o && o.method === 'DELETE')).toBe(false);
  });
});

describe('older history', () => {
  const page = (from, to) => {
    const out = [];
    for (let id = from; id <= to; id += 1) out.push({ id, user_id: 3, username: 'bob', role: 'user', speaker_mode: 'player', content: `m${id}`, created_at: at(id % 50) });
    return out;
  };

  test('loadOlder asks before the oldest row, prepends in order, stops when has_more is false', async () => {
    const api = jest.fn((path) => {
      if (path.includes('recent=1')) return Promise.resolve(ok(page(201, 350)));
      if (path.includes('before_id=201')) return Promise.resolve(ok({ messages: page(151, 200), has_more: true }));
      if (path.includes('before_id=151')) return Promise.resolve(ok({ messages: page(140, 150), has_more: false }));
      return Promise.resolve(ok([]));
    });
    const { result } = renderHook(() => useRoomMessages({ api, campaignId: 1, locationId: 2, userId: 2 }));
    await waitFor(() => expect(result.current.status).toBe('ready'));
    expect(result.current.hasMore).toBe(true); // a full first page
    let added;
    await act(async () => {
      added = await result.current.loadOlder();
    });
    expect(added).toBe(50);
    expect(api.mock.calls[api.mock.calls.length - 1][0]).toBe('/campaigns/1/locations/2?before_id=201&limit=50');
    expect(result.current.messages[0].id).toBe(151);
    expect(result.current.hasMore).toBe(true);
    await act(async () => {
      await result.current.loadOlder();
    });
    expect(result.current.messages.map((m) => m.id).slice(0, 3)).toEqual([140, 141, 142]);
    expect(result.current.messages).toHaveLength(211);
    expect(result.current.hasMore).toBe(false);
  });

  test('a short first page means the room starts there', async () => {
    const api = jest.fn(() => Promise.resolve(ok(page(1, 5))));
    const { result } = renderHook(() => useRoomMessages({ api, campaignId: 1, locationId: 2, userId: 2 }));
    await waitFor(() => expect(result.current.status).toBe('ready'));
    expect(result.current.hasMore).toBe(false);
  });

  test('a refresh after a delete keeps the older pages already loaded', () => {
    const prev = [...page(1, 10), { client_id: 't', temp: true }];
    const fresh = page(5, 10).filter((m) => m.id !== 7);
    // fresh shorter than the limit: the room starts at 5, nothing older survives
    expect(mergeRefresh(prev, fresh, 150).map((m) => m.id ?? m.client_id)).toEqual([5, 6, 8, 9, 10, 't']);
    // full window: rows older than it stay
    expect(mergeRefresh(prev, fresh, 5).map((m) => m.id ?? m.client_id)).toEqual([1, 2, 3, 4, 5, 6, 8, 9, 10, 't']);
  });

  test('scroll anchoring keeps the reader’s place', () => {
    expect(anchoredScrollTop(1000, 40, 1600)).toBe(640);
    expect(anchoredScrollTop(1000, 0, 1000)).toBe(0);
    expect(anchoredScrollTop(1000, 10, 900)).toBe(0);
  });

  test('the list: button at the top loads older rows without moving what you read; then the beginning marker', async () => {
    let resolveOlder;
    const api = jest.fn((path) => {
      if (path.includes('recent=1')) return Promise.resolve(ok(page(201, 350)));
      if (path.includes('before_id')) return new Promise((r) => (resolveOlder = r));
      return Promise.resolve(ok([]));
    });
    const u = setupUser();
    render(<Room api={api} user={PLAYER} />);
    const log = await screen.findByRole('log');
    await waitFor(() => expect(row(201)).not.toBeNull());
    // jsdom has no layout: drive scrollHeight from the number of rows
    Object.defineProperty(log, 'scrollHeight', { configurable: true, get: () => log.querySelectorAll('[data-message-id]').length * 20 });
    Object.defineProperty(log, 'clientHeight', { configurable: true, get: () => 400 });
    log.scrollTop = 30;
    await u.click(screen.getByRole('button', { name: 'Load older messages' }));
    expect(screen.getByRole('button', { name: 'Loading older messages…' })).toBeDisabled();
    await act(async () => resolveOlder(ok({ messages: page(191, 200), has_more: false })));
    await waitFor(() => expect(row(191)).not.toBeNull());
    // 10 rows of 20px were added above: the same message stays under the reader's eyes
    expect(log.scrollTop).toBe(30 + 10 * 20);
    expect(screen.getByRole('note')).toHaveTextContent('The beginning of Haven');
    expect(screen.queryByRole('button', { name: 'Load older messages' })).toBeNull();
  });

  test('scrolling near the top loads the older page by itself', async () => {
    const api = jest.fn((path) => {
      if (path.includes('recent=1')) return Promise.resolve(ok(page(201, 350)));
      if (path.includes('before_id')) return Promise.resolve(ok({ messages: page(191, 200), has_more: false }));
      return Promise.resolve(ok([]));
    });
    render(<Room api={api} user={PLAYER} />);
    const log = await screen.findByRole('log');
    await waitFor(() => expect(row(201)).not.toBeNull());
    Object.defineProperty(log, 'scrollHeight', { configurable: true, get: () => 3000 });
    Object.defineProperty(log, 'clientHeight', { configurable: true, get: () => 400 });
    log.scrollTop = 20;
    await act(async () => {
      log.dispatchEvent(new Event('scroll'));
    });
    await waitFor(() => expect(row(191)).not.toBeNull());
    expect(api.mock.calls.filter(([p]) => p.includes('before_id'))).toHaveLength(1);
  });
});
