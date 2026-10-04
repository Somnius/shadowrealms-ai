import { LiveConnection } from '../liveConnection';

/** Minimal EventSource double: tests drive it with emit()/fail(). */
class FakeES {
  static instances = [];
  constructor(url) {
    this.url = url;
    this.listeners = {};
    this.closed = false;
    FakeES.instances.push(this);
  }
  addEventListener(type, fn) {
    this.listeners[type] = fn;
  }
  emit(type, data) {
    this.listeners[type] && this.listeners[type]({ data: JSON.stringify(data || {}) });
  }
  fail() {
    this.onerror && this.onerror();
  }
  close() {
    this.closed = true;
  }
}

function make(overrides = {}) {
  FakeES.instances = [];
  const modes = [];
  const handlers = { onChanged: jest.fn(), onPoll: jest.fn(), onHello: jest.fn() };
  const conn = new LiveConnection({
    getTicket: overrides.getTicket || jest.fn().mockResolvedValue('t1'),
    makeUrl: (t) => `/api/campaigns/3/events?ticket=${t}`,
    ...handlers,
    onModeChange: (m) => modes.push(m),
    EventSourceImpl: overrides.ES === undefined ? FakeES : overrides.ES,
    timers: { setTimeout, clearTimeout, setInterval, clearInterval },
    options: { maxFailures: 3, pollMs: 5000, retryMs: 60000, backoffMs: [1000, 3000, 8000] },
  });
  return { conn, modes, ...handlers };
}

beforeEach(() => jest.useFakeTimers({ doNotFake: ['nextTick', 'setImmediate'] }));
afterEach(() => jest.useRealTimers());

async function tick(ms = 0) {
  jest.advanceTimersByTime(ms);
  for (let i = 0; i < 6; i += 1) await Promise.resolve();
}

test('connects with a ticket, goes live on hello and forwards changed events', async () => {
  const { conn, modes, onChanged, onHello } = make();
  conn.start();
  await tick();
  expect(FakeES.instances).toHaveLength(1);
  expect(FakeES.instances[0].url).toBe('/api/campaigns/3/events?ticket=t1');
  FakeES.instances[0].emit('hello', { locations: { 4: 10 } });
  expect(modes).toContain('live');
  expect(onHello).toHaveBeenCalledWith({ locations: { 4: 10 } });
  FakeES.instances[0].emit('changed', { location_id: 4, last_id: 11 });
  expect(onChanged).toHaveBeenCalledWith({ location_id: 4, last_id: 11 });
  conn.stop();
  expect(FakeES.instances[0].closed).toBe(true);
});

test('"bye" reconnects at once with a fresh ticket (bounded server streams)', async () => {
  const getTicket = jest.fn().mockResolvedValueOnce('t1').mockResolvedValueOnce('t2');
  const { conn } = make({ getTicket });
  conn.start();
  await tick();
  FakeES.instances[0].emit('hello', {});
  FakeES.instances[0].emit('bye');
  await tick();
  expect(FakeES.instances).toHaveLength(2);
  expect(FakeES.instances[1].url).toContain('ticket=t2');
  conn.stop();
});

test('after 3 failed connections it falls back to polling every 5 s, then retries SSE', async () => {
  const { conn, modes, onPoll } = make();
  conn.start();
  await tick();
  FakeES.instances[0].fail(); // failure 1 → retry in 1 s
  await tick(1000);
  FakeES.instances[1].fail(); // failure 2 → retry in 3 s
  await tick(3000);
  FakeES.instances[2].fail(); // failure 3 → polling
  expect(modes[modes.length - 1]).toBe('polling');
  await tick(5000);
  await tick(5000);
  expect(onPoll).toHaveBeenCalledTimes(2);
  // SSE is retried after retryMs and polling stops once it is live again
  await tick(50000);
  const latest = FakeES.instances[FakeES.instances.length - 1];
  expect(FakeES.instances.length).toBe(4);
  latest.emit('hello', {});
  expect(modes[modes.length - 1]).toBe('live');
  const polls = onPoll.mock.calls.length;
  await tick(20000);
  expect(onPoll.mock.calls.length).toBe(polls);
  conn.stop();
});

test('a stream that worked and then dropped reconnects without counting as a failure', async () => {
  const { conn, modes } = make();
  conn.start();
  await tick();
  FakeES.instances[0].emit('hello', {});
  FakeES.instances[0].fail();
  await tick(1000);
  expect(FakeES.instances).toHaveLength(2);
  expect(conn.failures).toBe(0);
  expect(modes).not.toContain('polling');
  conn.stop();
});

test('no ticket (e.g. 403) counts as a failure', async () => {
  const { conn } = make({ getTicket: jest.fn().mockResolvedValue(null) });
  conn.start();
  await tick();
  expect(conn.failures).toBe(1);
  expect(FakeES.instances).toHaveLength(0);
  conn.stop();
});

test('without EventSource it polls straight away', async () => {
  const { conn, modes, onPoll } = make({ ES: null });
  conn.start();
  expect(modes).toEqual(['polling']);
  await tick(5000);
  expect(onPoll).toHaveBeenCalledTimes(1);
  conn.stop();
});
