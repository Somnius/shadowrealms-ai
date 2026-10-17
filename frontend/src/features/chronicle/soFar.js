/**
 * "The chronicle so far" (docs/CHRONICLE.md): small helpers for the panel — time and number
 * formatting, which job states are live, how often to poll, and the Markdown downloads.
 */
import { API_URL, authFetch, getCurrentToken } from '../../app/http';

export const LIVE = ['queued', 'waiting', 'running'];
export const POLL_MS = 1500;
export const POLL_WAITING_MS = 5000;

export const isLive = (job) => !!job && LIVE.includes(job.status);

/** 1.5 s while writing, 5 s while queued or waiting for a quiet moment. */
export const pollDelay = (job) => (job && job.status === 'running' ? POLL_MS : POLL_WAITING_MS);

/** 75 -> "1:15"; 3725 -> "1:02:05". */
export function clock(seconds) {
  const s = Math.max(0, Math.round(Number(seconds) || 0));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const r = String(s % 60).padStart(2, '0');
  return h ? `${h}:${String(m).padStart(2, '0')}:${r}` : `${m}:${r}`;
}

export function number(n, lang) {
  try {
    return new Intl.NumberFormat(lang === 'el' ? 'el-GR' : 'en-GB').format(Number(n) || 0);
  } catch {
    return String(n);
  }
}

export function shortDate(iso, lang) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  try {
    return d.toLocaleDateString(lang === 'el' ? 'el-GR' : 'en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
  } catch {
    return d.toISOString().slice(0, 10);
  }
}

/** 'Athens / X?' + ' — so far' -> 'Athens X — so far.md' (no path or reserved characters, keeps Greek). */
export function mdFileName(name, suffix) {
  const base = String(name || '')
    // eslint-disable-next-line no-control-regex
    .replace(/[\\/:*?"<>|\u0000-\u001f\u007f]+/g, ' ')
    .replace(/[؜‎‏‪-‮⁦-⁩]/g, '')
    .replace(/\s+/g, ' ')
    .replace(/^[\s.]+|[\s.]+$/g, '')
    .slice(0, 80);
  return `${base || 'chronicle'} — ${suffix}.md`;
}

/** GET a Markdown export with the Bearer token and save it. Resolves { ok } or { ok: false, status }. */
export async function downloadMarkdown(path, fileName) {
  const token = getCurrentToken();
  let blob;
  try {
    const res = await authFetch(`${API_URL}${path}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      credentials: 'same-origin',
    });
    if (!res.ok) return { ok: false, status: res.status };
    blob = await res.blob();
  } catch {
    return { ok: false, status: 0 };
  }
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = fileName;
  a.rel = 'noopener';
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
  return { ok: true };
}
