import { normalizeInput, sendChatMessage } from '../sendFlow';

const campaign = { id: 3, created_by: 1 };
const ic = { id: 7, type: 'custom' };
const ooc = { id: 4, type: 'ooc' };
const player = { id: 2, username: 'p', role: 'player' };
const admin = { id: 1, username: 'a', role: 'admin' };

function fakeApi(routes) {
  const calls = [];
  const api = jest.fn(async (path, opts = {}) => {
    calls.push({ path, method: opts.method || 'GET', body: opts.body });
    const handler = routes[`${opts.method || 'GET'} ${path}`];
    return handler ? handler(opts.body, calls.length) : { ok: true, status: 200, data: {} };
  });
  return { api, calls };
}

function ctx(extra) {
  return {
    campaign,
    location: ic,
    user: player,
    speakAs: 'character',
    character: { id: 9, name: 'Yorika' },
    onOptimistic: jest.fn(),
    onSaved: jest.fn(),
    onAppend: jest.fn(),
    onError: jest.fn(),
    onAiPending: jest.fn(),
    onDiceMarker: jest.fn(),
    ...extra,
  };
}

test('a story line is saved as the character, then the Storyteller reply is saved as assistant', async () => {
  const { api, calls } = fakeApi({
    'POST /campaigns/3/locations/7': (body) => ({ ok: true, status: 201, data: { data: { id: body.role === 'assistant' ? 11 : 10, ...body } } }),
    'POST /ai/chat': () => ({ ok: true, status: 200, data: { response: 'The rain falls.' } }),
  });
  const c = ctx({ api });
  await expect(sendChatMessage(c, 'I wait.')).resolves.toBe(true);
  expect(calls.map((x) => `${x.method} ${x.path}`)).toEqual(['POST /campaigns/3/locations/7', 'POST /ai/chat', 'POST /campaigns/3/locations/7']);
  expect(calls[0].body).toMatchObject({ content: 'I wait.', message_type: 'ic', role: 'user', speak_as: 'character', character_id: 9 });
  expect(calls[2].body).toMatchObject({ content: 'The rain falls.', role: 'assistant', message_type: 'ic' });
  expect(c.onOptimistic).toHaveBeenCalledTimes(1);
  expect(c.onSaved).toHaveBeenCalledWith(expect.stringMatching(/^tmp-/), expect.objectContaining({ id: 10 }));
  expect(c.onAppend).toHaveBeenCalledWith([expect.objectContaining({ id: 11 })]);
  expect(c.onAiPending.mock.calls).toEqual([[true], [false]]);
});

test('OOC rooms post as ooc and skip the reply when the moderator stays silent', async () => {
  const { api, calls } = fakeApi({
    'POST /campaigns/3/locations/4': (body) => ({ ok: true, status: 201, data: { data: { id: 20, ...body } } }),
    'POST /ai/chat': () => ({ ok: true, status: 200, data: { response: null, ooc_no_reply: true } }),
  });
  await sendChatMessage(ctx({ api, location: ooc, speakAs: 'player' }), 'brb');
  expect(calls).toHaveLength(2);
  expect(calls[0].body).toMatchObject({ message_type: 'ooc', speak_as: 'player' });
  expect(calls[0].body.character_id).toBeUndefined();
});

test('players cannot run /ai commands (nothing is sent)', async () => {
  const { api } = fakeApi({});
  const c = ctx({ api });
  await expect(sendChatMessage(c, '/ai ping')).resolves.toBe(false);
  expect(api).not.toHaveBeenCalled();
  expect(c.onError).toHaveBeenCalled();
});

test('a failed save removes the optimistic line and reports the error', async () => {
  const { api } = fakeApi({ 'POST /campaigns/3/locations/7': () => ({ ok: false, status: 403, data: { error: 'Room closed' } }) });
  const c = ctx({ api });
  await expect(sendChatMessage(c, 'hello')).resolves.toBe(false);
  expect(c.onSaved).toHaveBeenCalledWith(expect.any(String), null);
  expect(c.onError).toHaveBeenCalledWith('Room closed');
});

test('/ai roll posts a dice marker and the result line', async () => {
  const { api, calls } = fakeApi({
    'POST /campaigns/3/locations/7': (body, n) => ({ ok: true, status: 201, data: { data: { id: 100 + n, ...body } } }),
    'POST /ai/slash': () => ({ ok: true, status: 200, data: { command: 'roll', display_markdown: 'rolled', roll: { rules_edition: 'classic', results: [3, 8], difficulty: 6, successes: 1 } } }),
  });
  const c = ctx({ api, user: admin });
  await sendChatMessage(c, '/ai roll 2@6');
  expect(calls[0].body.ai_message_kind).toBe('slash_user');
  const kinds = calls.slice(2).map((x) => x.body.ai_message_kind);
  expect(kinds[0]).toMatch(/^dice_animation:dice_/);
  expect(kinds[1]).toMatch(/^dice_roll:dice_/);
  expect(c.onDiceMarker).toHaveBeenCalledWith(expect.objectContaining({ dice_preview: [3, 8] }));
});

test('/me lines are saved as actions', async () => {
  const { api, calls } = fakeApi({ 'POST /campaigns/3/locations/7': (body) => ({ ok: true, status: 201, data: { data: { id: 5, ...body } } }) });
  await sendChatMessage(ctx({ api }), 'draws a blade', { messageType: 'action' });
  expect(calls[0].body.message_type).toBe('action');
});

test('normalizeInput: BOM stripped, bare /ai becomes /ai help for admins', () => {
  expect(normalizeInput('﻿ hi ', false)).toBe('hi');
  expect(normalizeInput('/ai', true)).toBe('/ai help');
  expect(normalizeInput('/ai', false)).toBe('/ai');
});
