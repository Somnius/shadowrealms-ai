import { isExplainCommand, normalizeInput, sendChatMessage } from '../sendFlow';

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

test('/ai commands are saved in the staff voice, never as the character', async () => {
  const { api, calls } = fakeApi({
    'POST /campaigns/3/locations/7': (body) => ({ ok: true, status: 201, data: { data: { id: 50, ...body } } }),
    'POST /ai/slash': () => ({ ok: true, status: 200, data: { command: 'help', display_markdown: 'help text' } }),
  });
  await sendChatMessage(ctx({ api, user: admin }), '/ai help');
  expect(calls[0].body).toMatchObject({ speak_as: 'staff', ai_message_kind: 'slash_user' });
  expect(calls[0].body).not.toHaveProperty('character_id');
});

test('a Storyteller outage gives one retryable failure (no toast); retry asks again without re-saving', async () => {
  let aiCalls = 0;
  const { api, calls } = fakeApi({
    'POST /campaigns/3/locations/7': (body) => ({ ok: true, status: 201, data: { data: { id: 60, ...body } } }),
    'POST /ai/chat': () => {
      aiCalls += 1;
      return aiCalls === 1
        ? { ok: false, status: 503, data: { error: 'The server is busy for a moment. Try again in a moment.' } }
        : { ok: true, status: 200, data: { response: 'At last.' } };
    },
  });
  const onAiFailed = jest.fn();
  const c = ctx({ api, onAiFailed });
  await sendChatMessage(c, 'Hello?');
  expect(c.onError).not.toHaveBeenCalled();
  expect(onAiFailed).toHaveBeenCalledWith(expect.objectContaining({ reason: 'The server is busy for a moment. Try again in a moment.' }));
  const saves = () => calls.filter((x) => x.path === '/campaigns/3/locations/7' && x.body.role === 'user');
  expect(saves()).toHaveLength(1);
  await onAiFailed.mock.calls[0][0].retry();
  expect(aiCalls).toBe(2);
  expect(saves()).toHaveLength(1);
  expect(calls.some((x) => x.body && x.body.role === 'assistant' && x.body.content === 'At last.')).toBe(true);
});

test('an OOC warning is shown as a translated notice, not the server markdown', async () => {
  const { api } = fakeApi({
    'POST /campaigns/3/locations/4': () => ({
      ok: true,
      status: 201,
      data: { data: { id: 10 }, ooc_warning: '⚠️ **OOC VIOLATION WARNING (1/3)**', ooc_warning_info: { count: 1, threshold: 3, banned: false } },
    }),
    'POST /ai/chat': () => ({ ok: true, status: 200, data: { response: null, ooc_no_reply: true } }),
  });
  const c = ctx({ api, location: ooc, speakAs: 'player', onNotice: jest.fn() });
  await sendChatMessage(c, '*hisses*');
  expect(c.onNotice).toHaveBeenCalledTimes(1);
  const n = c.onNotice.mock.calls[0][0];
  expect(n.tone).toBe('warn');
  expect(n.title).toBe('Out-of-character room: warning 1 of 3');
  expect(n.body).toContain('Warnings left before a temporary bar from this chronicle: 2.');
  expect(`${n.title} ${n.body}`).not.toMatch(/\*\*|⚠/);
  expect(c.onError).not.toHaveBeenCalled();
});

test('an OOC ban (403) shows the ban notice', async () => {
  const { api } = fakeApi({
    'POST /campaigns/3/locations/4': () => ({
      ok: false,
      status: 403,
      data: { error: 'OOC violation - temporarily banned', ooc_warning_info: { count: 3, threshold: 3, banned: true, ban_hours: 24, until: '2026-10-05T07:00:00' } },
    }),
  });
  const c = ctx({ api, location: ooc, speakAs: 'player', onNotice: jest.fn() });
  await expect(sendChatMessage(c, '*hisses*')).resolves.toBe(false);
  expect(c.onNotice.mock.calls[0][0]).toMatchObject({ tone: 'danger', title: 'Temporarily barred from this chronicle' });
  expect(c.onNotice.mock.calls[0][0].body).toContain('24 hours');
});

test('roll requests from /ai/chat ride along on the saved reply; the saved text is the API text', async () => {
  const text = 'Go. [[roll: Dexterity + Stealth | 4 dice | 2 hunger | difficulty 3]]';
  const reqs = [{ edition: 'v5', label: 'Dexterity + Stealth', pool: 4, hunger: 2, difficulty: 3, specialty: null, character_id: 9 }];
  const { api, calls } = fakeApi({
    'POST /campaigns/3/locations/7': (body) => ({ ok: true, status: 201, data: { data: { id: body.role === 'assistant' ? 31 : 30, ...body } } }),
    'POST /ai/chat': () => ({ ok: true, status: 200, data: { response: text, roll_requests: reqs } }),
  });
  const c = ctx({ api });
  await sendChatMessage(c, 'I sneak.');
  expect(calls[2].body).toEqual({ content: text, message_type: 'ic', role: 'assistant' });
  expect(c.onAppend).toHaveBeenCalledWith([expect.objectContaining({ id: 31, content: text, roll_requests: reqs })]);
});

test('/ai explain is open to players: player voice, the reply target goes to /ai/slash, the answer is saved', async () => {
  const { api, calls } = fakeApi({
    'POST /campaigns/3/locations/4': (body) => ({ ok: true, status: 201, data: { data: { id: body.role === 'assistant' ? 31 : 30, ...body } } }),
    'POST /ai/slash': () => ({ ok: true, status: 200, data: { command: 'explain', display_markdown: '**Roll explained** — V5' } }),
  });
  const c = ctx({ api, location: ooc, speakAs: 'character' });
  const replyTo = { id: 278, author: 'p', excerpt: 'Dice Roll (V5)', role: 'user' };
  await expect(sendChatMessage(c, '/ai explain this roll', { replyTo })).resolves.toBe(true);
  expect(calls.map((x) => `${x.method} ${x.path}`)).toEqual(['POST /campaigns/3/locations/4', 'POST /ai/slash', 'POST /campaigns/3/locations/4']);
  expect(calls[0].body).toMatchObject({ content: '/ai explain this roll', speak_as: 'player', ai_message_kind: 'slash_user', reply_to_id: 278 });
  expect(calls[0].body.character_id).toBeUndefined();
  expect(calls[1].body).toEqual({ line: '/ai explain this roll', campaign_id: 3, location_id: 4, reply_to_id: 278 });
  expect(calls[2].body).toMatchObject({ content: '**Roll explained** — V5', role: 'assistant', ai_message_kind: 'slash_assistant' });
  expect(c.onError).not.toHaveBeenCalled();
});

test('the chronicle owner explains in the staff voice; the Greek alias is recognised', async () => {
  const { api, calls } = fakeApi({
    'POST /ai/slash': () => ({ ok: true, status: 200, data: { command: 'explain', display_markdown: 'x' } }),
  });
  const owner = { id: 1, username: 'o', role: 'player' };
  await sendChatMessage(ctx({ api, user: owner, location: ooc }), '/ai εξήγησε');
  expect(calls[0].body).toMatchObject({ speak_as: 'staff' });
  expect(calls[1].body).toEqual({ line: '/ai εξήγησε', campaign_id: 3, location_id: 4 });
  expect(isExplainCommand('/ai explain')).toBe(true);
  expect(isExplainCommand('/AI Explain this roll')).toBe(true);
  expect(isExplainCommand('/ai εξηγησε')).toBe(true);
  expect(isExplainCommand('/ai explainer')).toBe(false);
  expect(isExplainCommand('/ai respond explain this roll')).toBe(false);
});

test('a reply to the Storyteller carries reply_to_id to /ai/chat', async () => {
  const { api, calls } = fakeApi({
    'POST /campaigns/3/locations/7': (body) => ({ ok: true, status: 201, data: { data: { id: 40, ...body } } }),
    'POST /ai/chat': () => ({ ok: true, status: 200, data: { response: 'The Beast stirs.' } }),
  });
  await sendChatMessage(ctx({ api }), 'What does that mean for me?', { replyTo: { id: 278 } });
  expect(calls[1].path).toBe('/ai/chat');
  expect(calls[1].body).toMatchObject({ message: 'What does that mean for me?', reply_to_id: 278 });
  const plain = fakeApi({});
  await sendChatMessage(ctx({ api: plain.api }), 'no reply here');
  expect(plain.calls[1].body.reply_to_id).toBeUndefined();
});

test('a hidden-roll explanation is shown to the requester only, never saved', async () => {
  const { api, calls } = fakeApi({
    'POST /ai/slash': () => ({ ok: true, status: 200, data: { command: 'explain', private_markdown: '**Roll explained** — secret' } }),
  });
  const onPrivateNotice = jest.fn();
  const c = ctx({ api, user: admin, location: ooc, onPrivateNotice });
  await expect(sendChatMessage(c, '/ai explain', { replyTo: { id: 41 } })).resolves.toBe(true);
  expect(calls.map((x) => `${x.method} ${x.path}`)).toEqual(['POST /campaigns/3/locations/4', 'POST /ai/slash']);
  expect(onPrivateNotice).toHaveBeenCalledWith({ title: expect.any(String), markdown: '**Roll explained** — secret' });
  expect(c.onAppend).not.toHaveBeenCalled();
});
