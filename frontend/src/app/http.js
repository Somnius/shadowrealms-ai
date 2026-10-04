/**
 * JSON client for the shell (the older utils/api.js goes through authFetch below too).
 * apiFetch returns { ok, status, data } and never throws on HTTP errors; network errors resolve to
 * { ok: false, status: 0, data: { error } }.
 *
 * Session handling (docs/SECURITY_MODEL.md, "Frontend changes"):
 * - 401 TOKEN_EXPIRED → one POST /api/auth/refresh (HttpOnly cookie), store the new access token,
 *   retry the request once. One refresh at a time, shared by every caller (and across tabs through
 *   the Web Locks API): the server treats a second use of the same refresh cookie as theft.
 * - Refresh refused (401 REFRESH_INVALID) or any other 401 (TOKEN_REVOKED, TOKEN_INVALID…) → the
 *   session ends locally (onUnauthorized). So does a 422 "Signature verification failed" / "Not
 *   enough segments" from older backends.
 * - 429 (RATE_LIMITED, LOGIN_LOCKED) and 503 (UNAVAILABLE) never end the session: the response's
 *   `error` becomes a translated, friendly text with the wait time (callers of actions show it), and
 *   failing background reads (GET) reach the transient handler (one toast).
 */
import { t } from '../i18n';

export const API_URL = '/api';
const TOKEN_KEY = 'token';

let onUnauthorized = null;
let onTokenRefreshed = null;
let onTransient = null;
let currentToken = null;
let refreshing = null;
let transition = null;
let endedFor = null;

/** The auth provider registers a callback so a dead session anywhere logs the user out. fn(reason) */
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn;
}

/** fn(newAccessToken, user?) after a successful refresh (the provider updates its state). */
export function setTokenRefreshedHandler(fn) {
  onTokenRefreshed = fn;
}

/** fn({ status, code, retryAfter, message }) for 429 / 503 on signed-in requests. */
export function setTransientHandler(fn) {
  onTransient = fn;
}

/** The access token every request should use now (kept in sync by AuthProvider). */
export function setCurrentToken(token) {
  currentToken = token || null;
  if (token) endedFor = null;
}

export function getCurrentToken() {
  return currentToken;
}

/**
 * While `promise` runs (e.g. a password change, which revokes the current token and returns a new
 * one), 401s from requests that were already in flight wait for it instead of ending the session.
 */
export function holdSession(promise) {
  const p = Promise.resolve(promise).catch(() => null);
  transition = p;
  p.then(() => {
    if (transition === p) transition = null;
  });
  return promise;
}

function storedToken() {
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch (e) {
    return null;
  }
}

function headerValue(headers, name) {
  if (!headers) return null;
  if (typeof headers.get === 'function') return headers.get(name);
  const key = Object.keys(headers).find((k) => k.toLowerCase() === name.toLowerCase());
  return key ? headers[key] : null;
}

function bearerOf(init) {
  const v = headerValue(init && init.headers, 'Authorization');
  const m = v && /^Bearer\s+(.+)$/i.exec(String(v));
  return m ? m[1] : null;
}

function withBearer(init, token) {
  const h = {};
  const src = (init && init.headers) || {};
  if (typeof src.forEach === 'function' && typeof src.get === 'function') src.forEach((v, k) => (h[k] = v));
  else Object.assign(h, src);
  Object.keys(h).forEach((k) => k.toLowerCase() === 'authorization' && delete h[k]);
  h.Authorization = `Bearer ${token}`;
  return { ...init, headers: h };
}

async function peekJson(res) {
  try {
    const r = typeof res.clone === 'function' ? res.clone() : res;
    return await r.json();
  } catch (e) {
    return null;
  }
}

/** Seconds to wait from a 429 body / Retry-After header (null when unknown). */
export function retryAfterOf(res, data) {
  const fromBody = data && Number(data.retry_after);
  if (Number.isFinite(fromBody) && fromBody > 0) return Math.ceil(fromBody);
  const fromHeader = Number(headerValue(res && res.headers, 'Retry-After'));
  return Number.isFinite(fromHeader) && fromHeader > 0 ? Math.ceil(fromHeader) : null;
}

/** "in 40 seconds" / "in 3 minutes" (translated). */
export function waitText(seconds) {
  if (!seconds) return t('common:wait.moment', 'in a moment');
  if (seconds < 90) return t('common:wait.seconds', { one: 'in {{count}} second', other: 'in {{count}} seconds' }, { count: seconds });
  const minutes = Math.ceil(seconds / 60);
  return t('common:wait.minutes', { one: 'in {{count}} minute', other: 'in {{count}} minutes' }, { count: minutes });
}

/** Friendly, translated text for 429 / 503 (null for other statuses). */
export function transientMessage(status, code, retryAfter) {
  const when = waitText(retryAfter);
  if (status === 429 && code === 'LOGIN_LOCKED') {
    return t('common:error.loginLocked', 'Too many failed sign-in attempts. Try again {{when}}.', { when });
  }
  if (status === 429) return t('common:error.rateLimited', 'You are going a little fast. Try again {{when}}.', { when });
  if (status === 503) return t('common:error.unavailable', 'The server is busy for a moment. Try again {{when}}.', { when });
  return null;
}

const DEAD_TOKEN_422 = /signature verification failed|not enough segments|invalid header|invalid crypto padding|invalid payload/i;

function endSession(sentToken, reason) {
  // Only the token the user is on now can end the session (a stale one just lost a race).
  if (!sentToken || sentToken !== currentToken || endedFor === sentToken) return;
  endedFor = sentToken;
  if (onUnauthorized) onUnauthorized(reason);
}

async function doRefresh(sentToken) {
  // Another tab (or an earlier refresh here) already has a newer token: use it.
  const shared = storedToken();
  if (shared && shared !== sentToken) return { token: shared };
  let res;
  try {
    res = await fetch(`${API_URL}/auth/refresh`, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    });
  } catch (e) {
    return { fatal: false };
  }
  let data = null;
  try {
    data = await res.json();
  } catch (e) {
    data = null;
  }
  if (res.ok && data && data.access_token) {
    try {
      window.localStorage.setItem(TOKEN_KEY, data.access_token);
    } catch (e) {
      /* private mode */
    }
    return { token: data.access_token, user: data.user || null };
  }
  if (res.status === 429 || res.status === 503 || res.status === 0 || res.status >= 500) {
    if (onTransient && (res.status === 429 || res.status === 503)) {
      const retryAfter = retryAfterOf(res, data);
      onTransient({ status: res.status, code: data && data.code, retryAfter, message: transientMessage(res.status, data && data.code, retryAfter) });
    }
    return { fatal: false };
  }
  return { fatal: true };
}

/**
 * New access token from the refresh cookie. Single flight: parallel callers share one promise, and
 * tabs take turns through navigator.locks when available. Resolves { token, user } | { fatal }.
 */
export function refreshAccessToken(sentToken = currentToken) {
  if (!refreshing) {
    const run = () => doRefresh(sentToken);
    const locks = typeof navigator !== 'undefined' && navigator.locks && typeof navigator.locks.request === 'function' ? navigator.locks : null;
    const p = (locks ? locks.request('sr-auth-refresh', run) : run()).then((r) => {
      if (r && r.token) {
        setCurrentToken(r.token);
        if (onTokenRefreshed) onTokenRefreshed(r.token, r.user || null);
      }
      return r || { fatal: false };
    });
    refreshing = p;
    p.finally(() => {
      if (refreshing === p) refreshing = null;
    }).catch(() => null);
  }
  return refreshing;
}

/**
 * fetch() with the session rules above. Same arguments and result as fetch (the body of the
 * returned Response is untouched). Requests without a Bearer token pass straight through.
 */
export async function authFetch(url, init = {}) {
  const sent = bearerOf(init);
  const res = await fetch(url, init);
  if (!sent) return res;
  return recover(url, init, res, sent, 0);
}

async function recover(url, init, res, sent, attempt) {
  const { status } = res;
  if (status === 401) {
    if (transition) await transition;
    const body = await peekJson(res);
    const code = body && body.code;
    // Sent with a token that has since been replaced (refresh, password change): retry once with the new one.
    if (currentToken && currentToken !== sent) {
      if (attempt > 0) return res;
      const again = await fetch(url, withBearer(init, currentToken));
      return recover(url, init, again, currentToken, attempt + 1);
    }
    const expired = code === 'TOKEN_EXPIRED' || (!code && /expired/i.test(String((body && (body.msg || body.error)) || '')));
    if (expired && attempt === 0) {
      const r = await refreshAccessToken(sent);
      if (r && r.token) {
        const again = await fetch(url, withBearer(init, r.token));
        return recover(url, init, again, r.token, attempt + 1);
      }
      if (r && r.fatal) endSession(sent, 'expired');
      return res;
    }
    endSession(sent, code === 'TOKEN_REVOKED' ? 'revoked' : expired ? 'expired' : 'invalid');
    return res;
  }
  if (status === 422) {
    const body = await peekJson(res);
    if (body && DEAD_TOKEN_422.test(String(body.msg || body.error || ''))) endSession(sent, 'invalid');
    return res;
  }
  // Background reads get the notice; actions (POST/PUT/DELETE) show the friendly error themselves
  // (apiFetch rewrites data.error), so one problem never shows two toasts.
  const method = String((init && init.method) || 'GET').toUpperCase();
  if ((status === 429 || status === 503) && onTransient && method === 'GET') {
    const body = await peekJson(res);
    const code = body && body.code;
    const retryAfter = retryAfterOf(res, body);
    onTransient({ status, code, retryAfter, message: transientMessage(status, code, retryAfter) });
  }
  return res;
}

export async function apiFetch(token, path, { method = 'GET', body, headers, signal } = {}) {
  const h = { ...(headers || {}) };
  if (token) h.Authorization = `Bearer ${token}`;
  let payload;
  if (body !== undefined) {
    h['Content-Type'] = 'application/json';
    payload = JSON.stringify(body);
  }
  let res;
  try {
    res = await authFetch(`${API_URL}${path}`, { method, headers: h, body: payload, signal, credentials: 'same-origin' });
  } catch (e) {
    if (e && e.name === 'AbortError') throw e;
    return { ok: false, status: 0, data: { error: t('common:error.network', 'Network error: the server could not be reached.') } };
  }
  let data = null;
  try {
    data = await res.json();
  } catch (e) {
    data = null;
  }
  data = data == null ? {} : data;
  // The proxy answers 502/504 when the API is down or restarting: that is "unreachable", not a bug.
  if ((res.status === 502 || res.status === 504) && !data.code) {
    data = { ...data, error: t('common:error.network', 'Network error: the server could not be reached.'), message: undefined };
  }
  if (res.status === 429 || res.status === 503) {
    const retryAfter = retryAfterOf(res, data);
    data = { ...data, retry_after: retryAfter, error: transientMessage(res.status, data.code, retryAfter), message: undefined };
  }
  return { ok: res.ok, status: res.status, data };
}

/** Server error text, joined with a contact hint when the API sends one. */
export function errorText(data, fallback) {
  if (!data) return fallback;
  const parts = [data.message || data.error, data.contact_hint].filter(Boolean);
  return parts.length ? parts.join(' ') : fallback;
}

/**
 * Password policy codes from backend/services/auth_security.py (and change-password) → translated
 * text. Returns null for other codes so callers fall back to the server's text.
 */
export function passwordErrorText(code) {
  switch (code) {
    case 'PASSWORD_REQUIRED':
      return t('auth:pw.required', 'Enter a password.');
    case 'PASSWORD_TOO_SHORT':
      return t('auth:pw.tooShort', 'The password must be at least 12 characters long.');
    case 'PASSWORD_TOO_LONG':
      return t('auth:pw.tooLong', 'The password is too long: at most 72 bytes (72 Latin or about 36 Greek characters).');
    case 'PASSWORD_COMMON':
      return t('auth:pw.common', 'This password is too common. Choose another one.');
    case 'PASSWORD_CONTAINS_USERNAME':
      return t('auth:pw.containsName', 'The password must not contain your username or email.');
    case 'PASSWORD_TOO_SIMPLE':
      return t('auth:pw.tooSimple', 'The password is too simple (repeated characters or the site name).');
    case 'PASSWORD_UNCHANGED':
      return t('auth:pw.unchanged', 'The new password must differ from the current one.');
    default:
      return null;
  }
}

/** Server error for auth forms: password codes and other known codes translated, else the server text. */
export function authErrorText(data, fallback) {
  const code = data && data.code;
  const pw = passwordErrorText(code);
  if (pw) return pw;
  if (code === 'INVALID_CREDENTIALS') return t('auth:error.credentials', 'Wrong username or password.');
  if (code === 'ACCOUNT_DISABLED') return t('auth:error.disabled', 'This account is disabled. Contact an administrator.');
  if (code === 'ALREADY_REGISTERED') return t('auth:error.taken', 'That username or email is already registered.');
  if (code === 'USERNAME_INVALID') return t('auth:error.username', 'Username must be 3–150 characters, without spaces.');
  if (code === 'INVALID_INVITE') return t('auth:error.invite', 'Invalid invite code. This attempt has been recorded; ask an admin for a valid code.');
  if (code === 'EMAIL_INVALID') return t('auth:error.email', 'Enter a valid email address.');
  return errorText(data, fallback);
}
