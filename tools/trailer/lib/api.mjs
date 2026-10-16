// Tiny client for the demo stack's API (http://127.0.0.1:8180/api by default).
import fs from 'node:fs';
export const BASE = process.env.SR_DEMO_URL || 'http://127.0.0.1:8180';
export const ROOT = new URL('../../../', import.meta.url).pathname;
// The trailer's data folder (accounts, demo state, clips): data/trailer (v1) or TRAILER_DATA=data/trailer-v2
export const T = ROOT + (process.env.TRAILER_DATA || 'data/trailer').replace(/\/+$/, '') + '/';

export async function api(path, { method = 'GET', body, token } = {}) {
  const r = await fetch(`${BASE}/api${path}`, {
    method,
    redirect: 'manual', // never follow a redirect off the demo origin
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (r.status >= 300 && r.status < 400) throw new Error(`API redirect ${r.status} for ${path} -> ${r.headers.get('location')} (not followed)`);
  let data = null; const txt = await r.text();
  try { data = JSON.parse(txt); } catch { data = { raw: txt.slice(0, 500) }; }
  return { ok: r.ok, status: r.status, data };
}
export async function must(p) {
  const r = await p;
  if (!r.ok) throw new Error(`API ${r.status}: ${JSON.stringify(r.data).slice(0, 400)}`);
  return r.data;
}
export function accounts() { return JSON.parse(fs.readFileSync(T + 'demo-accounts.json', 'utf8')); }
export function saveAccounts(a) { fs.writeFileSync(T + 'demo-accounts.json', JSON.stringify(a, null, 2), { mode: 0o600 }); fs.chmodSync(T + 'demo-accounts.json', 0o600); }
export async function login(username) {
  const a = accounts()[username];
  const d = await must(api('/auth/login', { method: 'POST', body: { username, password: a.password } }));
  return d.access_token || d.token;
}
