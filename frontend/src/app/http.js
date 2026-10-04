/**
 * Minimal JSON client for the shell (the older utils/api.js stays as-is for legacy pages).
 * Every call returns { ok, status, data } and never throws on HTTP errors; network errors
 * resolve to { ok: false, status: 0, data: { error } }.
 */
import { t } from '../i18n';

export const API_URL = '/api';

let onUnauthorized = null;

/** The auth provider registers a callback so a 401 anywhere logs the user out. */
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn;
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
    res = await fetch(`${API_URL}${path}`, { method, headers: h, body: payload, signal });
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
  if (res.status === 401 && token && onUnauthorized) onUnauthorized();
  return { ok: res.ok, status: res.status, data: data == null ? {} : data };
}

/** Server error text, joined with a contact hint when the API sends one. */
export function errorText(data, fallback) {
  if (!data) return fallback;
  const parts = [data.message || data.error, data.contact_hint].filter(Boolean);
  return parts.length ? parts.join(' ') : fallback;
}
