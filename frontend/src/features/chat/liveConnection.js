/**
 * Live updates for one open chronicle: Server-Sent Events, "notify then fetch".
 *
 * Flow: POST /api/campaigns/<id>/events/ticket → { ticket } (60 s, signed, single purpose; EventSource can't
 * send an Authorization header and the long-lived JWT must not end up in URLs / nginx logs), then
 * GET /api/campaigns/<id>/events?ticket=… . The server sends:
 *   event: hello    data: { locations: { "<lid>": lastId } }
 *   event: changed  data: { location_id, last_id }
 *   event: bye      (server closes the stream after ~55 s; we reconnect with a fresh ticket)
 *
 * Fallback: after `maxFailures` consecutive failed connections we switch to polling (`onPoll` every
 * `pollMs`, default 5 s) and try SSE again every `retryMs`. Everything time- or network-related is
 * injected so the state machine is unit-testable.
 */

export const DEFAULTS = {
  maxFailures: 3,
  pollMs: 5000,
  retryMs: 60000,
  backoffMs: [1000, 3000, 8000],
};

export class LiveConnection {
  constructor({
    getTicket, // async () => ticket string | null
    makeUrl, // (ticket) => url
    onChanged, // ({ location_id, last_id }) => void
    onHello, // ({ locations }) => void
    onPoll, // () => void  (fallback tick)
    onModeChange, // ('connecting' | 'live' | 'polling' | 'closed') => void
    EventSourceImpl = typeof window !== 'undefined' ? window.EventSource : undefined,
    // Wrapped: calling window.setTimeout as a method of another object throws "Illegal invocation".
    timers = {
      setTimeout: (fn, ms) => setTimeout(fn, ms),
      clearTimeout: (h) => clearTimeout(h),
      setInterval: (fn, ms) => setInterval(fn, ms),
      clearInterval: (h) => clearInterval(h),
    },
    options = {},
  }) {
    this.getTicket = getTicket;
    this.makeUrl = makeUrl;
    this.onChanged = onChanged || (() => {});
    this.onHello = onHello || (() => {});
    this.onPoll = onPoll || (() => {});
    this.onModeChange = onModeChange || (() => {});
    this.ES = EventSourceImpl;
    this.timers = timers;
    this.opts = { ...DEFAULTS, ...options };
    this.failures = 0;
    this.mode = 'idle';
    this.es = null;
    this.pollHandle = null;
    this.retryHandle = null;
    this.stopped = false;
    this.gotEvent = false;
  }

  setMode(mode) {
    if (this.mode === mode) return;
    this.mode = mode;
    this.onModeChange(mode);
  }

  start() {
    this.stopped = false;
    if (!this.ES) {
      this.startPolling();
      return;
    }
    this.connect();
  }

  stop() {
    this.stopped = true;
    this.closeStream();
    this.stopPolling();
    if (this.retryHandle) this.timers.clearTimeout(this.retryHandle);
    this.retryHandle = null;
    this.setMode('closed');
  }

  closeStream() {
    if (this.es) {
      try {
        this.es.close();
      } catch (e) {
        /* ignore */
      }
    }
    this.es = null;
  }

  async connect() {
    if (this.stopped) return;
    if (this.mode !== 'polling') this.setMode('connecting');
    let ticket = null;
    try {
      ticket = await this.getTicket();
    } catch (e) {
      ticket = null;
    }
    if (this.stopped) return;
    if (!ticket) {
      this.fail();
      return;
    }
    this.closeStream();
    this.gotEvent = false;
    const es = new this.ES(this.makeUrl(ticket));
    this.es = es;
    const parse = (ev) => {
      try {
        return JSON.parse(ev.data || '{}');
      } catch (e) {
        return {};
      }
    };
    es.addEventListener('hello', (ev) => {
      if (this.es !== es) return;
      this.gotEvent = true;
      this.failures = 0;
      this.stopPolling();
      if (this.retryHandle) this.timers.clearTimeout(this.retryHandle);
      this.retryHandle = null;
      this.setMode('live');
      this.onHello(parse(ev));
    });
    es.addEventListener('changed', (ev) => {
      if (this.es !== es) return;
      this.gotEvent = true;
      this.onChanged(parse(ev));
    });
    es.addEventListener('bye', () => {
      if (this.es !== es) return;
      // Normal end of a bounded stream: reconnect straight away with a new ticket.
      this.closeStream();
      this.connect();
    });
    es.onerror = () => {
      if (this.es !== es) return;
      this.closeStream();
      if (this.gotEvent) {
        // The stream worked and then dropped (server reload, network blip): reconnect, not a failure yet.
        this.gotEvent = false;
        this.scheduleReconnect(this.opts.backoffMs[0]);
      } else {
        this.fail();
      }
    };
  }

  scheduleReconnect(ms) {
    if (this.stopped) return;
    if (this.retryHandle) this.timers.clearTimeout(this.retryHandle);
    this.retryHandle = this.timers.setTimeout(() => {
      this.retryHandle = null;
      this.connect();
    }, ms);
  }

  fail() {
    if (this.stopped) return;
    this.failures += 1;
    if (this.failures >= this.opts.maxFailures) {
      this.startPolling();
      this.scheduleReconnect(this.opts.retryMs);
      return;
    }
    const b = this.opts.backoffMs;
    this.scheduleReconnect(b[Math.min(this.failures - 1, b.length - 1)]);
  }

  startPolling() {
    if (this.pollHandle || this.stopped) return;
    this.setMode('polling');
    this.pollHandle = this.timers.setInterval(() => this.onPoll(), this.opts.pollMs);
  }

  stopPolling() {
    if (this.pollHandle) this.timers.clearInterval(this.pollHandle);
    this.pollHandle = null;
  }
}
