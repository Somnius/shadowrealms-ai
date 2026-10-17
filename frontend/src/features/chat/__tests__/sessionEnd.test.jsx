/**
 * "Session ended here" (0.26): the Storyteller and site admins mark a message from its menu; everyone
 * sees a thin "— end of session —" line under it. Helpers and players get no control.
 */
import { render, screen, waitFor, within } from '@testing-library/react';
import setupUser from '../../../design/testing/setupUser';
import { DesignProvider } from '../../../design';
import MessageList from '../MessageList';
import { MessageActionsContext, useMessageActions } from '../MessageActions';
import { useRoomMessages } from '../useRoomMessages';
import { buildTimeline } from '../grouping';

const OWNER = { id: 1, username: 'st', role: 'player' };
const PLAYER = { id: 2, username: 'ann', role: 'player' };
const ADMIN = { id: 9, username: 'root', role: 'admin' };
const HELPER = { id: 8, username: 'help', role: 'helper' };
const campaign = { id: 1, created_by: 1 };
const at = (min) => new Date(Date.UTC(2026, 9, 4, 20, min)).toISOString();
const ok = (data) => ({ ok: true, status: 200, data });
const line = (id, min, userId = 2) => ({ id, user_id: userId, username: 'ann', role: 'user', speaker_mode: 'player', content: `line ${id}`, created_at: at(min) });
const ROOM = [line(10, 0), line(11, 1), line(12, 2)];
const MARKS = '/campaigns/1/chronicle/session-marks';

function Room({ api, user, toast = jest.fn() }) {
  const room = useRoomMessages({ api, campaignId: 1, locationId: 2, userId: user.id });
  const actions = useMessageActions({ api, user, campaign, room, toast });
  return (
    <DesignProvider>
      <MessageActionsContext.Provider value={actions.value}>
        <MessageList roomKey="1:2" roomName="Haven" messages={room.messages} status={room.status} userId={user.id} sessionEnds={actions.sessionEnds} />
      </MessageActionsContext.Provider>
    </DesignProvider>
  );
}

function api({ marks = [], post = () => ok({ marked: true }), del = () => ok({ marked: false }) } = {}) {
  return jest.fn((path, opts = {}) => {
    if (path === MARKS && !opts.method) return Promise.resolve(ok({ message_ids: marks }));
    if (path === MARKS && opts.method === 'POST') return Promise.resolve(post(opts.body));
    if (path.startsWith(`${MARKS}/`) && opts.method === 'DELETE') return Promise.resolve(del(path));
    if (path.includes('recent=1')) return Promise.resolve(ok(ROOM));
    return Promise.resolve(ok([]));
  });
}

const row = (id) => document.getElementById(`msg-${id}`);
const markBtn = (id) => within(row(id)).queryByRole('button', { name: 'Session ended here' });
const unmarkBtn = (id) => within(row(id)).queryByRole('button', { name: 'Remove the end of session mark' });

test('the timeline puts the line under the marked message and starts a new group after it', () => {
  const rows = buildTimeline(ROOM, { sessionEnds: new Set(['11']) });
  const kinds = rows.map((r) => r.type);
  expect(kinds).toEqual(['day', 'group', 'session-end', 'group']);
  expect(rows[1].messages.map((m) => m.id)).toEqual([10, 11]);
  expect(rows[2]).toMatchObject({ id: 11 });
  expect(buildTimeline(ROOM).map((r) => r.type)).toEqual(['day', 'group']);
});

test('players see the line from the marks endpoint but get no control', async () => {
  const a = api({ marks: [11] });
  render(<Room api={a} user={PLAYER} />);
  expect(await screen.findByText('— end of session —')).toBeInTheDocument();
  expect(document.querySelector('[data-session-end="11"]')).not.toBeNull();
  expect(a).toHaveBeenCalledWith(MARKS);
  for (const id of [10, 11, 12]) expect(markBtn(id)).toBeNull();
  expect(unmarkBtn(11)).toBeNull();
});

test('helpers get no control', async () => {
  render(<Room api={api()} user={HELPER} />);
  await waitFor(() => expect(row(10)).not.toBeNull());
  expect(markBtn(10)).toBeNull();
});

test.each([['storyteller', OWNER], ['admin', ADMIN]])('%s marks and unmarks a message', async (_l, user) => {
  const u = setupUser();
  const toast = jest.fn();
  const a = api();
  render(<Room api={a} user={user} toast={toast} />);
  await waitFor(() => expect(row(10)).not.toBeNull());
  expect(screen.queryByText('— end of session —')).toBeNull();
  await u.click(markBtn(10));
  expect(a).toHaveBeenCalledWith(MARKS, { method: 'POST', body: { message_id: 10 } });
  expect(await screen.findByText('— end of session —')).toBeInTheDocument();
  expect(toast).toHaveBeenLastCalledWith(expect.objectContaining({ tone: 'ok' }));
  await u.click(unmarkBtn(10));
  expect(a).toHaveBeenCalledWith(`${MARKS}/10`, { method: 'DELETE' });
  await waitFor(() => expect(screen.queryByText('— end of session —')).toBeNull());
});

test('a refused mark is taken back and explained', async () => {
  const u = setupUser();
  const toast = jest.fn();
  render(<Room api={api({ post: () => ({ ok: false, status: 403, data: { error: 'forbidden' } }) })} user={OWNER} toast={toast} />);
  await waitFor(() => expect(row(10)).not.toBeNull());
  await u.click(markBtn(10));
  await waitFor(() => expect(toast).toHaveBeenLastCalledWith(expect.objectContaining({ tone: 'danger' })));
  expect(screen.queryByText('— end of session —')).toBeNull();
});

test('a mark on a row the viewer cannot see still shows the line where it would be', () => {
  const marker = { id: 20, role: 'assistant', ai_message_kind: 'dice_animation:r1-a', content: '{}', created_at: at(3) };
  const hidden = { ...line(21, 4), ai_message_kind: 'dice_roll_hidden:r1-a' };
  const after = line(22, 5);
  const viaMarker = buildTimeline([...ROOM, marker, after], { sessionEnds: new Set(['20']) });
  expect(viaMarker.map((r) => r.type)).toEqual(['day', 'group', 'session-end', 'group']);
  const viaHidden = buildTimeline([...ROOM, hidden, after], { sessionEnds: new Set(['21']), hiddenIds: new Set(['21']) });
  expect(viaHidden.map((r) => r.type)).toEqual(['day', 'group', 'session-end', 'group']);
  expect(viaHidden[1].messages.map((m) => m.id)).toEqual([10, 11, 12]);
});
