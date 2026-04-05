/**
 * Serialize merit rows + optional global notes for API.
 * Backward compatible: legacy `{ notes: "..." }` only is still valid when reading.
 */

export function createEmptyMeritRow() {
  return { id: `m_${Math.random().toString(36).slice(2, 11)}`, name: '', points: 0, note: '' };
}

/**
 * @param {Array<{ name: string, points: number, note?: string }>} rows
 * @param {string} globalNotes - optional catch-all notes (merits section footer)
 * @returns {Record<string, unknown>} payload for merits_flaws JSON column
 */
export function buildMeritsFlawsPayload(rows, globalNotes = '') {
  const entries = (rows || [])
    .filter((r) => r && String(r.name || '').trim())
    .map((r) => ({
      name: String(r.name).trim(),
      points: Number.isFinite(Number(r.points)) ? Number(r.points) : 0,
      ...(String(r.note || '').trim() ? { note: String(r.note).trim() } : {}),
    }));
  const notes = String(globalNotes || '').trim();
  if (!entries.length && !notes) return {};
  const out = {};
  if (entries.length) out.entries = entries;
  if (notes) out.notes = notes;
  return out;
}

/**
 * Hydrate UI state from stored merits_flaws (entries + notes or legacy notes-only).
 */
export function parseMeritsFlawsFromApi(raw) {
  if (!raw || typeof raw !== 'object') {
    return { rows: [createEmptyMeritRow()], globalNotes: '' };
  }
  const notes = typeof raw.notes === 'string' ? raw.notes : '';
  if (Array.isArray(raw.entries) && raw.entries.length) {
    const rows = raw.entries.map((e, i) => ({
      id: `m_${i}_${String(e.name || '').slice(0, 20)}`,
      name: e.name != null ? String(e.name) : '',
      points: Number(e.points) || 0,
      note: e.note != null ? String(e.note) : '',
    }));
    return { rows, globalNotes: notes };
  }
  if (notes) {
    return { rows: [createEmptyMeritRow()], globalNotes: notes };
  }
  return { rows: [createEmptyMeritRow()], globalNotes: '' };
}
