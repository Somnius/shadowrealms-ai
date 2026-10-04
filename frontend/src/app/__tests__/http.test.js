import {
  apiFetch,
  authFetch,
  holdSession,
  setCurrentToken,
  setTokenRefreshedHandler,
  setTransientHandler,
  setUnauthorizedHandler,
} from '../http';

const res = (status, body, headers = {}) => ({
  ok: status >= 200 && status < 300,
  status,
  headers: { get: (k) => headers[k] ?? headers[k.toLowerCase()] ?? null },
  json: async () => body,
});

const bearer = (opts) => (opts && opts.headers ? opts.headers.Authorization : undefined);

let unauthorized;
let refreshed;
let transient;

beforeEach(() => {
  localStorage.clear();
  unauthorized = jest.fn();
  refreshed = jest.fn();
  transient = jest.fn();
  setUnauthorizedHandler(unauthorized);
  setTokenRefreshedHandler(refreshed);
  setTransientHandler(transient);
  setCurrentToken('old');
  localStorage.setItem('token', 'old');
});

afterEach(() => {
  setUnauthorizedHandler(null);
  setTokenRefreshedHandler(null);
  setTransientHandler(null);
  setCurrentToken(null);
});

test('401 TOKEN_EXPIRED: refreshes once (same-origin cookie, JSON body) and retries with the new token', async () => {
  global.fetch = jest.fn(async (url, opts = {}) => {
    if (url === '/api/auth/refresh') return res(200, { access_token: 'new', expires_in: 1800 });
    return bearer(opts) === 'Bearer new' ? res(200, { hello: 1 }) : res(401, { code: 'TOKEN_EXPIRED' });
  });
  const r = await apiFetch('old', '/campaigns/');
  expect(r).toEqual({ ok: true, status: 200, data: { hello: 1 } });
  const refreshCalls = global.fetch.mock.calls.filter(([u]) => u === '/api/auth/refresh');
  expect(refreshCalls).toHaveLength(1);
  expect(refreshCalls[0][1]).toMatchObject({
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: '{}',
  });
  expect(localStorage.getItem('token')).toBe('new');
  expect(refreshed).toHaveBeenCalledWith('new', null);
  expect(unauthorized).not.toHaveBeenCalled();
});

test('parallel 401s share one refresh (a second use of the refresh cookie would end the session)', async () => {
  let release;
  const gate = new Promise((r) => (release = r));
  global.fetch = jest.fn(async (url, opts = {}) => {
    if (url === '/api/auth/refresh') {
      await gate;
      return res(200, { access_token: 'new' });
    }
    return bearer(opts) === 'Bearer new' ? res(200, { url }) : res(401, { code: 'TOKEN_EXPIRED' });
  });
  const all = Promise.all([apiFetch('old', '/a'), apiFetch('old', '/b'), apiFetch('old', '/c')]);
  await new Promise((r) => setTimeout(r, 0));
  release();
  const out = await all;
  expect(out.map((r) => r.status)).toEqual([200, 200, 200]);
  expect(global.fetch.mock.calls.filter(([u]) => u === '/api/auth/refresh')).toHaveLength(1);
});

test('a request that comes back 401 after another one already refreshed reuses the new token', async () => {
  setCurrentToken('new'); // someone refreshed while this request (sent with "old") was in flight
  global.fetch = jest.fn(async (url, opts = {}) => (bearer(opts) === 'Bearer new' ? res(200, {}) : res(401, { code: 'TOKEN_EXPIRED' })));
  const r = await authFetch('/api/x', { headers: { Authorization: 'Bearer old' } });
  expect(r.status).toBe(200);
  expect(global.fetch.mock.calls.filter(([u]) => u === '/api/auth/refresh')).toHaveLength(0);
  expect(unauthorized).not.toHaveBeenCalled();
});

test('refresh refused (REFRESH_INVALID) ends the session', async () => {
  global.fetch = jest.fn(async (url) =>
    url === '/api/auth/refresh' ? res(401, { code: 'REFRESH_INVALID' }) : res(401, { code: 'TOKEN_EXPIRED' })
  );
  const r = await apiFetch('old', '/campaigns/');
  expect(r.status).toBe(401);
  expect(unauthorized).toHaveBeenCalledWith('expired');
});

test('refresh that hits a rate limit or outage keeps the session', async () => {
  global.fetch = jest.fn(async (url) =>
    url === '/api/auth/refresh' ? res(503, { code: 'UNAVAILABLE' }) : res(401, { code: 'TOKEN_EXPIRED' })
  );
  await apiFetch('old', '/campaigns/');
  expect(unauthorized).not.toHaveBeenCalled();
  expect(transient).toHaveBeenCalledWith(expect.objectContaining({ status: 503 }));
});

test('other 401 codes (revoked) end the session without a refresh', async () => {
  global.fetch = jest.fn(async () => res(401, { code: 'TOKEN_REVOKED' }));
  await apiFetch('old', '/campaigns/');
  expect(unauthorized).toHaveBeenCalledWith('revoked');
  expect(global.fetch.mock.calls.filter(([u]) => u === '/api/auth/refresh')).toHaveLength(0);
});

test('422 from a token the server cannot read ends the session; other 422s do not', async () => {
  global.fetch = jest.fn(async () => res(422, { msg: 'Not enough segments' }));
  await apiFetch('old', '/x');
  expect(unauthorized).toHaveBeenCalledTimes(1);
  setCurrentToken('other');
  global.fetch = jest.fn(async () => res(422, { error: 'pool_size must be a number' }));
  await apiFetch('other', '/x');
  expect(unauthorized).toHaveBeenCalledTimes(1);
});

test('429 on a background read: a notice, never a logout', async () => {
  global.fetch = jest.fn(async () => res(429, { code: 'RATE_LIMITED', retry_after: 40 }));
  await apiFetch('old', '/campaigns/');
  expect(transient).toHaveBeenCalledWith(expect.objectContaining({ status: 429, code: 'RATE_LIMITED', retryAfter: 40 }));
  expect(unauthorized).not.toHaveBeenCalled();
});

test('429 on an action is not a logout: friendly translated error with the wait time (no second toast)', async () => {
  global.fetch = jest.fn(async () => res(429, { error: 'Too many requests.', code: 'RATE_LIMITED', retry_after: 40 }, { 'Retry-After': '40' }));
  const r = await apiFetch('old', '/campaigns/3/roll', { method: 'POST', body: {} });
  expect(r.ok).toBe(false);
  expect(r.data.error).toBe('You are going a little fast. Try again in 40 seconds.');
  expect(r.data.retry_after).toBe(40);
  expect(unauthorized).not.toHaveBeenCalled();
  expect(transient).not.toHaveBeenCalled();
});

test('login lockout shows minutes (no token: the session handlers stay out of it)', async () => {
  global.fetch = jest.fn(async () => res(429, { code: 'LOGIN_LOCKED', retry_after: 300 }));
  const r = await apiFetch(null, '/auth/login', { method: 'POST', body: {} });
  expect(r.data.error).toBe('Too many failed sign-in attempts. Try again in 5 minutes.');
  expect(transient).not.toHaveBeenCalled();
  expect(unauthorized).not.toHaveBeenCalled();
});

test('during a password change, 401s from requests still using the old token wait and retry', async () => {
  let finish;
  const change = new Promise((r) => (finish = r));
  holdSession(change);
  global.fetch = jest.fn(async (url, opts = {}) => (bearer(opts) === 'Bearer fresh' ? res(200, {}) : res(401, { code: 'TOKEN_REVOKED' })));
  const pending = apiFetch('old', '/campaigns/');
  await new Promise((r) => setTimeout(r, 0));
  setCurrentToken('fresh');
  finish();
  const r = await pending;
  expect(r.status).toBe(200);
  expect(unauthorized).not.toHaveBeenCalled();
});

test('legacy authFetch keeps the response body readable for the caller', async () => {
  global.fetch = jest.fn(async () => ({ ...res(200, { list: [1] }), clone() { return res(200, { list: [1] }); } }));
  const r = await authFetch('/api/admin/users', { headers: { Authorization: 'Bearer old' } });
  expect(await r.json()).toEqual({ list: [1] });
});
