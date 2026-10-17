/** "Previously on…" (0.27): the card after 12 hours away, closing remembered per absence, the
 * header's on-demand recap, jumping to a night (loading older history), the bottom sheet on phones,
 * and "Read it" through the voice queue (phone and server voices). */
import { act, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react';
import { DesignProvider, ToastProvider } from '../../../design';
import PreviouslyOn from '../PreviouslyOn';
import { hasRecap, jumpLoadingOlder, readClosed, recapParts, usePreviouslyOn } from '../previouslyOn';
import { serverEngine } from '../../voice/serverVoice';
import { createSpeechQueue } from '../../voice/speechQueue';

jest.mock('../../../app/http', () => ({
  API_URL: '/api',
  getCurrentToken: () => 'tok',
  authFetch: async () => ({ ok: true, blob: async () => 'audio-bytes' }),
  errorText: (d, f) => f,
}));

const RECAP = {
  location_id: 7,
  lang: 'en',
  since: '2026-10-15T20:00:00',
  recent: false,
  so_far: 'The coterie found the note under the basement.',
  nights: [
    { night: 2, title: 'The locksmith', summary: ['Maro names the locksmith.'], first_message_id: 21 },
    { night: 4, title: 'Under the stairs', summary: ['Something moves at the back.'], first_message_id: 40 },
  ],
};

function apiFor({ away = RECAP.since, recap = RECAP } = {}) {
  return jest.fn(async (path) => {
    if (path.endsWith('/recap/visit')) return { ok: true, data: { location_id: 7, away_since: away } };
    if (path.includes('/recap?')) return { ok: true, data: recap };
    return { ok: true, data: {} };
  });
}

const wrap = ({ children }) => (
  <DesignProvider>
    <ToastProvider>{children}</ToastProvider>
  </DesignProvider>
);

beforeEach(() => window.localStorage.clear());

test('opens after an absence, closing is remembered until the next one', async () => {
  const api = apiFor();
  const { result, unmount } = renderHook(() => usePreviouslyOn({ api, campaignId: 3, locationId: 7, userId: 1, enabled: true }));
  await waitFor(() => expect(result.current.open).toBe(true));
  expect(api).toHaveBeenCalledWith('/campaigns/3/chronicle/recap/visit', { method: 'POST', body: { location_id: 7 } });
  expect(api.mock.calls.some(([p]) => p.startsWith('/campaigns/3/chronicle/recap?location_id=7'))).toBe(true);
  act(() => result.current.close());
  expect(result.current.open).toBe(false);
  expect(readClosed(1, 3, 7)).toBe(RECAP.since);
  unmount();
  // the same absence: no card; a new absence: the card again
  const again = renderHook(() => usePreviouslyOn({ api, campaignId: 3, locationId: 7, userId: 1, enabled: true }));
  await act(async () => {
    await new Promise((r) => setTimeout(r, 0));
  });
  expect(again.result.current.open).toBe(false);
  again.unmount();
  const api2 = apiFor({ away: '2026-10-17T08:00:00' });
  const later = renderHook(() => usePreviouslyOn({ api: api2, campaignId: 3, locationId: 7, userId: 1, enabled: true }));
  await waitFor(() => expect(later.result.current.open).toBe(true));
});

test('nothing shows without an absence, a digest or nights', async () => {
  for (const api of [apiFor({ away: null }), apiFor({ recap: { ...RECAP, so_far: null } }), apiFor({ recap: { ...RECAP, nights: [] } })]) {
    const { result, unmount } = renderHook(() => usePreviouslyOn({ api, campaignId: 3, locationId: 7, userId: 1, enabled: true }));
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
    expect(result.current.open).toBe(false);
    unmount();
  }
  expect(hasRecap(null)).toBe(false);
});

test('the header button asks for the recent nights and says when there is nothing', async () => {
  const api = apiFor({ away: null });
  const { result } = renderHook(() => usePreviouslyOn({ api, campaignId: 3, locationId: 7, userId: 1, enabled: true }));
  let shown;
  await act(async () => {
    shown = await result.current.showNow();
  });
  expect(shown).toBe(true);
  expect(result.current.open).toBe(true);
  expect(api.mock.calls.some(([p]) => p.includes('recent=1'))).toBe(true);
  const api2 = apiFor({ away: null, recap: { ...RECAP, nights: [] } });
  const empty = renderHook(() => usePreviouslyOn({ api: api2, campaignId: 3, locationId: 7, userId: 1, enabled: true }));
  await act(async () => {
    shown = await empty.result.current.showNow();
  });
  expect(shown).toBe(false);
});

test('jump: loads older history until the night’s first message is there', async () => {
  let loaded = 0;
  const jump = jest.fn(() => loaded >= 2);
  const loadOlder = jest.fn(async () => {
    loaded += 1;
    return 50;
  });
  await expect(jumpLoadingOlder(21, { loadOlder, hasMore: () => true, jump, tick: async () => {} })).resolves.toBe(true);
  expect(loadOlder).toHaveBeenCalledTimes(2);
  // a load already in flight returns nothing: wait for it instead of giving up
  let busy = 3;
  let shown = false;
  const inflight = jest.fn(async () => 0);
  await expect(
    jumpLoadingOlder(21, {
      loadOlder: inflight,
      hasMore: () => true,
      isLoading: () => (busy > 0 ? ((busy -= 1), (shown = busy === 0), true) : false),
      jump: () => shown,
      tick: async () => {},
    }),
  ).resolves.toBe(true);
  expect(inflight).not.toHaveBeenCalled();
  // no more history once the load settles: not found
  let more = true;
  const last = jest.fn(async () => {
    more = false;
    return 0;
  });
  await expect(jumpLoadingOlder(21, { loadOlder: last, hasMore: () => more, jump: () => false, tick: async () => {} })).resolves.toBe(false);
  expect(last).toHaveBeenCalledTimes(1);
});

test('a new api identity (token refresh) doesn’t post the visit again', async () => {
  const api = apiFor({ away: null });
  const { rerender } = renderHook(({ a }) => usePreviouslyOn({ api: a, campaignId: 3, locationId: 7, userId: 1, enabled: true }), { initialProps: { a: api } });
  await act(async () => {
    await new Promise((r) => setTimeout(r, 0));
  });
  const api2 = apiFor({ away: null });
  rerender({ a: api2 });
  await act(async () => {
    await new Promise((r) => setTimeout(r, 0));
  });
  expect(api.mock.calls.filter(([p]) => p.endsWith('/visit'))).toHaveLength(1);
  expect(api2).not.toHaveBeenCalled();
});

test('coming back to a hidden tab sends a visit and opens the card for a new absence', async () => {
  let away = null;
  const api = jest.fn(async (path) => {
    if (path.endsWith('/recap/visit')) return { ok: true, data: { away_since: away } };
    return { ok: true, data: RECAP };
  });
  const { result } = renderHook(() => usePreviouslyOn({ api, campaignId: 3, locationId: 7, userId: 1, enabled: true }));
  await act(async () => {
    await new Promise((r) => setTimeout(r, 0));
  });
  expect(result.current.open).toBe(false);
  away = '2026-10-17T02:00:00';
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'visible' });
  await act(async () => {
    document.dispatchEvent(new Event('visibilitychange'));
    await new Promise((r) => setTimeout(r, 0));
  });
  await waitFor(() => expect(result.current.open).toBe(true));
  expect(api.mock.calls.filter(([p]) => p.endsWith('/visit'))).toHaveLength(2);
});

const stateOf = (over = {}) => ({ recap: RECAP, open: true, close: jest.fn(), hide: jest.fn(), startJob: jest.fn(), ...over });

test('the card: nights newest last, the story so far, 44 px controls, jump and close', () => {
  const state = stateOf();
  const onJump = jest.fn();
  render(<PreviouslyOn state={state} listen={null} isMobile={false} onJump={onJump} />, { wrapper: wrap });
  expect(screen.getByRole('heading', { name: 'Previously on…' })).toBeInTheDocument();
  const titles = screen.getAllByRole('heading', { level: 3 }).map((h) => h.textContent);
  expect(titles).toEqual(['Night 2: The locksmith', 'Night 4: Under the stairs', 'The story so far']);
  expect(screen.getByText(RECAP.so_far)).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Read it' })).toBeNull(); // no voices: no button
  fireEvent.click(screen.getAllByRole('button', { name: 'Jump to the start' })[1]);
  expect(onJump).toHaveBeenCalledWith(40);
  fireEvent.click(screen.getByRole('button', { name: 'Close the recap' }));
  expect(state.close).toHaveBeenCalled();
});

test('phones get a bottom sheet; jumping closes it', () => {
  const state = stateOf();
  const onJump = jest.fn();
  render(<PreviouslyOn state={state} listen={null} isMobile onJump={onJump} />, { wrapper: wrap });
  expect(document.querySelector('.sr-drawer--bottom')).not.toBeNull();
  fireEvent.click(screen.getAllByRole('button', { name: 'Jump to the start' })[0]);
  expect(state.hide).toHaveBeenCalled();
  expect(state.close).not.toHaveBeenCalled(); // not closed for this absence: the button brings it back
  expect(onJump).toHaveBeenCalledWith(21);
});

test('nothing renders when closed', () => {
  const { container } = render(<PreviouslyOn state={stateOf({ open: false })} listen={null} isMobile={false} onJump={() => {}} />, { wrapper: wrap });
  expect(container.querySelector('.sr-recap')).toBeNull();
});

test('"Read it" hands the card to the voice queue', () => {
  const state = stateOf();
  const listen = { available: true, readRecap: jest.fn() };
  render(<PreviouslyOn state={state} listen={listen} isMobile={false} onJump={() => {}} />, { wrapper: wrap });
  fireEvent.click(screen.getByRole('button', { name: 'Read it' }));
  const arg = listen.readRecap.mock.calls[0][0];
  expect(arg.startJob).toBe(state.startJob);
  expect(arg.parts[0]).toEqual({ text: 'Previously on…', lang: 'en' });
  expect(arg.parts.map((p) => p.text).join(' ')).toContain('Night 4: Under the stairs. Something moves at the back.');
  expect(arg.parts[arg.parts.length - 1].text).toContain('The story so far.');
});

test('recapParts speaks in the recap’s language', () => {
  const el = recapParts({ ...RECAP, lang: 'el' });
  expect(el.every((p) => p.lang === 'el')).toBe(true);
  expect(recapParts({ ...RECAP, nights: [] })).toEqual([]);
});

test('server voices: a recap item starts its own job, never a message job', async () => {
  global.URL.createObjectURL = () => 'blob:1';
  global.URL.revokeObjectURL = () => {};
  const el = { played: [], canPlayType: () => 'probably', play() { this.played.push(this.src); return Promise.resolve(); }, pause: jest.fn() };
  const api = jest.fn(async () => ({ ok: true, data: { state: 'done', key: 'k', chunks: 1, text: 'Previously on…' } }));
  const startJob = jest.fn(() => api('/campaigns/3/chronicle/recap/tts', { method: 'POST', body: { chunk: 0 } }));
  const server = serverEngine({ api, getAudio: () => el, getSettings: () => ({}), fallback: null });
  const q = createSpeechQueue(server);
  q.play([{ id: 'recap:7', parts: [{ text: 'Previously on…', lang: 'en' }], startJob }]);
  await new Promise((r) => setTimeout(r, 0));
  await new Promise((r) => setTimeout(r, 0));
  expect(startJob).toHaveBeenCalledWith(0);
  expect(api.mock.calls.every(([p]) => !p.startsWith('/voice/tts/jobs'))).toBe(true);
  expect(el.played).toHaveLength(1);
});

test('a recap that changed mid-read stops quietly', async () => {
  const el = { played: [], canPlayType: () => 'probably', play() { this.played.push(this.src); return Promise.resolve(); }, pause: jest.fn() };
  const api = jest.fn(async () => ({ ok: false, status: 409, data: { error: 'recap_changed' } }));
  const phone = { speak: jest.fn(), cancel: jest.fn() };
  const onFallback = jest.fn();
  const server = serverEngine({ api, getAudio: () => el, getSettings: () => ({}), fallback: phone, onFallback });
  const done = jest.fn();
  server.speak({ id: 'recap:7', parts: [{ text: 'x', lang: 'en' }], startJob: () => api('/x') }, done);
  await new Promise((r) => setTimeout(r, 0));
  await new Promise((r) => setTimeout(r, 0));
  expect(done).toHaveBeenCalled();
  expect(phone.speak).not.toHaveBeenCalled();
  expect(onFallback).not.toHaveBeenCalled();
});
