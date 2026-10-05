/**
 * "Export PDF" for a character sheet: GET /api/characters/<id>/sheet.pdf with the Bearer token (a plain
 * link wouldn't authenticate), then save the blob under the character's name.
 */
import { API_URL, authFetch, getCurrentToken } from './http';

/** 'Κωνσταντίνος / X?' → 'Κωνσταντίνος X.pdf': no path or reserved characters, keeps Greek. */
export function pdfFileName(name) {
  const base = String(name || '')
    // eslint-disable-next-line no-control-regex
    .replace(/[\\/:*?"<>|\u0000-\u001f\u007f]+/g, ' ')
    .replace(/\s+/g, ' ')
    .replace(/^[\s.]+|[\s.]+$/g, '')
    .slice(0, 80);
  return `${base || 'character'}.pdf`;
}

/** US Letter where it's the norm, A4 everywhere else. */
export function defaultPaper(langs = typeof navigator !== 'undefined' ? navigator.languages || [navigator.language] : []) {
  const lang = String((langs && langs[0]) || '');
  return /-(US|CA|MX|PH)$/i.test(lang) ? 'letter' : 'a4';
}

/** Resolves { ok: true } once the download starts, or { ok: false, status }. */
export async function downloadSheetPdf(characterId, name, { paper = defaultPaper() } = {}) {
  const token = getCurrentToken();
  const query = paper === 'letter' ? '?paper=letter' : '';
  let res;
  try {
    res = await authFetch(`${API_URL}/characters/${encodeURIComponent(characterId)}/sheet.pdf${query}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      credentials: 'same-origin',
    });
  } catch {
    return { ok: false, status: 0 };
  }
  if (!res.ok) return { ok: false, status: res.status };
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = pdfFileName(name);
  a.rel = 'noopener';
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
  return { ok: true };
}
