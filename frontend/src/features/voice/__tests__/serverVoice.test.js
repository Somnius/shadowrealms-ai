import { awaitJob, preferredFormat, serverEngine, switchingEngine } from '../serverVoice';
import { createSpeechQueue } from '../speechQueue';

jest.mock('../../../app/http', () => ({
  API_URL: '/api',
  getCurrentToken: () => 'tok',
  authFetch: async () => ({ ok: true, blob: async () => 'audio-bytes' }),
}));

beforeEach(() => {
  let n = 0;
  global.URL.createObjectURL = () => `blob:${(n += 1)}`;
  global.URL.revokeObjectURL = () => {};
});

function fakeAudio(canOgg = true) {
  return {
    played: [],
    canPlayType: (t) => (canOgg && t.includes('ogg') ? 'probably' : ''),
    play() {
      this.played.push(this.src);
      return Promise.resolve();
    },
    pause: jest.fn(),
  };
}

const phone = () => {
  const p = { said: [], speak: jest.fn((item, done) => { p.said.push(item.id); done(); }), cancel: jest.fn() };
  return p;
};

test('format: Ogg where it plays, else the AAC copy (iOS)', () => {
  expect(preferredFormat(fakeAudio(true))).toBe('ogg');
  expect(preferredFormat(fakeAudio(false))).toBe('m4a');
});

test('awaitJob polls until done', async () => {
  const api = jest.fn()
    .mockResolvedValueOnce({ ok: true, data: { job_id: 'j1', state: 'queued' } })
    .mockResolvedValueOnce({ ok: true, data: { state: 'running' } })
    .mockResolvedValueOnce({ ok: true, data: { state: 'done', key: 'abc' } });
  const key = await awaitJob(api, api('/voice/tts/jobs'), { pollMs: 0 });
  expect(key).toBe('abc');
  expect(api).toHaveBeenLastCalledWith('/voice/tts/jobs/j1');
});

test('a busy server falls back to the phone voice and says so', async () => {
  const api = jest.fn(async () => ({ ok: false, status: 503, data: { error: 'queue_full' } }));
  const p = phone();
  const onFallback = jest.fn();
  const e = serverEngine({ api, getAudio: () => fakeAudio(), getSettings: () => ({}), fallback: p, onFallback });
  const done = jest.fn();
  e.speak({ id: 5, text: 'hi' }, done);
  await new Promise((r) => setTimeout(r, 0));
  await new Promise((r) => setTimeout(r, 0));
  expect(onFallback).toHaveBeenCalled();
  expect(p.said).toEqual([5]);
  expect(done).toHaveBeenCalled();
});

test('plays server audio with speed and volume, and prefetches the next line', async () => {
  const el = fakeAudio();
  const api = jest.fn(async (path, opts) => ({ ok: true, data: { job_id: `j${opts.body.message_id}`, state: 'done', key: `k${opts.body.message_id}` } }));
  const server = serverEngine({ api, getAudio: () => el, getSettings: () => ({ rate: 1.5, volume: 0.5 }), fallback: phone() });
  const q = createSpeechQueue(switchingEngine(() => ({ tts_source: 'server' }), server, phone()));
  q.enqueue([{ id: 1, text: 'a' }, { id: 2, text: 'b' }]);
  await new Promise((r) => setTimeout(r, 0));
  await new Promise((r) => setTimeout(r, 0));
  const posted = api.mock.calls.map((c) => c[1].body.message_id);
  expect(posted.sort()).toEqual([1, 2]); // line 2 asked for while 1 plays
  expect(el.played).toHaveLength(1);
  expect(el.playbackRate).toBe(1.5);
  expect(el.volume).toBe(0.5);
  el.onended();
  await new Promise((r) => setTimeout(r, 0));
  expect(el.played).toHaveLength(2);
  expect(api).toHaveBeenCalledTimes(2); // the prefetched line is not asked for twice
});

test('phone mode never calls the server', () => {
  const api = jest.fn();
  const p = phone();
  const server = serverEngine({ api, getAudio: () => fakeAudio(), getSettings: () => ({}), fallback: p });
  const q = createSpeechQueue(switchingEngine(() => ({ tts_source: 'phone' }), server, p));
  q.enqueue([{ id: 1, text: 'a' }]);
  expect(p.said).toEqual([1]);
  expect(api).not.toHaveBeenCalled();
});
