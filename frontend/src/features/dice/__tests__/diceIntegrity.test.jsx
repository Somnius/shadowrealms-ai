import { act, renderHook } from '@testing-library/react';
import { clampMarkerTiming, MAX_CLOCK_SKEW_MS, MAX_DURATION_MS } from '../useDiceOverlay';
import { useDiceActions } from '../useDiceActions';

test('marker timing is clamped: duration at most 8 s, start within ±60 s of this clock', () => {
  const now = 1_000_000_000;
  expect(clampMarkerTiming({ duration_ms: 600000, started_at_ms: now }, now)).toEqual({ startedAtMs: now, durationMs: MAX_DURATION_MS });
  expect(clampMarkerTiming({ duration_ms: 3000, started_at_ms: now + 3600_000 }, now).startedAtMs).toBe(now + MAX_CLOCK_SKEW_MS);
  expect(clampMarkerTiming({ duration_ms: 3000, started_at_ms: now - 3600_000 }, now).startedAtMs).toBe(now - MAX_CLOCK_SKEW_MS);
  expect(clampMarkerTiming({ duration_ms: 'x', started_at_ms: 'y' }, now)).toEqual({ startedAtMs: now, durationMs: 3000 });
});

const campaign = { id: 3, rules_edition: 'v5' };
const location = { id: 7 };

function setup(api) {
  const appendMessages = jest.fn();
  const fetchRoom = jest.fn();
  const toast = jest.fn();
  const startFromMarker = jest.fn();
  const { result } = renderHook(() =>
    useDiceActions({ api, campaign, location, speakAs: 'player', character: null, startFromMarker, appendMessages, fetchRoom, toast })
  );
  return { result, appendMessages, fetchRoom, toast, startFromMarker };
}

const form = { pool: '5', v5Difficulty: 2, hunger: 1, hidden: false, reason: '' };

test('server_posted: the client posts nothing to the room and shows the saved rows once', async () => {
  const rows = [
    { id: 10, ai_message_kind: 'dice_animation:a1', content: '{}' },
    { id: 11, ai_message_kind: 'dice_roll:a1', content: 'rolled' },
  ];
  const api = jest.fn(async () => ({
    ok: true,
    status: 200,
    data: { roll_result: { rules_edition: 'v5' }, chat_message: 'rolled', server_posted: true, message_ids: [10, 11], messages: rows },
  }));
  const { result, appendMessages, startFromMarker } = setup(api);
  let ok;
  await act(async () => {
    ok = await result.current.roll(form);
  });
  expect(ok).toBe(true);
  expect(api).toHaveBeenCalledTimes(1);
  expect(api.mock.calls[0][0]).toBe('/campaigns/3/roll');
  const body = api.mock.calls[0][1].body;
  expect(body).toMatchObject({ location_id: 7, hidden: false, speak_as: 'player' });
  // No reason typed: nothing in the poster's UI language is saved; the server labels the roll.
  expect(body).not.toHaveProperty('action_description');
  expect(appendMessages).toHaveBeenCalledTimes(1);
  expect(appendMessages).toHaveBeenCalledWith(rows);
  expect(startFromMarker).not.toHaveBeenCalled();
});

test('server_posted without rows in the answer: refetch instead of posting', async () => {
  const api = jest.fn(async () => ({ ok: true, status: 200, data: { roll_result: {}, server_posted: true, message_ids: [10, 11] } }));
  const { result, fetchRoom, appendMessages } = setup(api);
  await act(async () => {
    await result.current.roll(form);
  });
  expect(api).toHaveBeenCalledTimes(1);
  expect(fetchRoom).toHaveBeenCalledTimes(1);
  expect(appendMessages).not.toHaveBeenCalled();
});

test('older backend (no server_posted): the client still posts marker + result', async () => {
  const api = jest.fn(async (path) =>
    path === '/campaigns/3/roll'
      ? { ok: true, status: 200, data: { roll_result: { rules_edition: 'v5' }, chat_message: 'rolled' } }
      : { ok: true, status: 201, data: { data: { id: Math.random() } } }
  );
  const { result, startFromMarker } = setup(api);
  await act(async () => {
    await result.current.roll({ ...form, reason: 'Sneak past' });
  });
  expect(api.mock.calls[0][1].body.action_description).toBe('Sneak past');
  const posts = api.mock.calls.filter(([p]) => p === '/campaigns/3/locations/7');
  expect(posts).toHaveLength(2);
  expect(startFromMarker).toHaveBeenCalledTimes(1);
});

test('rouse check with server_posted does not post the line again', async () => {
  const api = jest.fn(async () => ({
    ok: true,
    status: 200,
    data: { die: 7, success: true, hunger_before: 1, hunger_after: 1, server_posted: true, message_ids: [12], messages: [{ id: 12 }] },
  }));
  const { result, appendMessages } = setup(api);
  await act(async () => {
    await result.current.rouse(1);
  });
  expect(api).toHaveBeenCalledTimes(1);
  expect(appendMessages).toHaveBeenCalledWith([{ id: 12 }]);
});

test('reroll toast text shows the Willpower spent from the response', () => {
  const { willpowerSpentText } = require('../useDiceActions');
  expect(willpowerSpentText({ willpower_spent: false })).toBeUndefined();
  expect(willpowerSpentText({ willpower_spent: true, roll_result: { willpower_cost: 'superficial' } })).toBe('Willpower −1 (Superficial damage).');
  expect(willpowerSpentText({ willpower_spent: true, roll_result: { willpower_cost: 'aggravated' } })).toMatch(/^Willpower −1 \(Aggravated/);
});
