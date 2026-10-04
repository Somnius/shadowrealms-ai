import { act, renderHook, waitFor } from '@testing-library/react';
import { readSeen, seenParam, useRoomMessages, writeSeen } from '../useRoomMessages';

const ok = (data) => ({ ok: true, status: 200, data });

test('fetchSince called while a fetch is running re-runs once it finishes (nothing is missed)', async () => {
  const gates = [];
  const api = jest.fn((path) => {
    if (path.includes('recent=1')) return Promise.resolve(ok([{ id: 1, content: 'a' }]));
    return new Promise((resolve) => gates.push(resolve));
  });
  const { result } = renderHook(() => useRoomMessages({ api, campaignId: 3, locationId: 7, userId: 1 }));
  await waitFor(() => expect(result.current.status).toBe('ready'));

  let first;
  act(() => {
    first = result.current.fetchSince();
  });
  // Two more events while the first fetch is still in flight: only one extra fetch afterwards.
  act(() => {
    result.current.fetchSince();
    result.current.fetchSince();
  });
  expect(gates).toHaveLength(1);
  expect(api.mock.calls[api.mock.calls.length - 1][0]).toContain('since_id=1');

  await act(async () => {
    gates[0](ok([{ id: 2, content: 'b' }]));
  });
  await waitFor(() => expect(gates).toHaveLength(2));
  // The re-run asks only for rows after what the first fetch brought.
  expect(api.mock.calls[api.mock.calls.length - 1][0]).toContain('since_id=2');
  await act(async () => {
    gates[1](ok([{ id: 3, content: 'c' }]));
    await first;
  });
  await waitFor(() => expect(result.current.messages.map((m) => m.id)).toEqual([1, 2, 3]));
  expect(gates).toHaveLength(2);
});

test('browser read state is kept per user', () => {
  localStorage.clear();
  writeSeen(1, 3, 7, 50);
  expect(readSeen(1, 3, 7)).toBe(50);
  expect(readSeen(2, 3, 7)).toBe(0);
  expect(localStorage.getItem('sr_seen_1_3_7')).toBe('50');
  expect(seenParam(2, 3, [{ id: 7 }])).toBe('7:0');
});
