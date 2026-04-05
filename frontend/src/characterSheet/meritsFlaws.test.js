import { buildMeritsFlawsPayload, parseMeritsFlawsFromApi } from './meritsFlaws';

describe('buildMeritsFlawsPayload', () => {
  it('returns empty object when nothing entered', () => {
    expect(buildMeritsFlawsPayload([{ id: '1', name: '', points: 0, note: '' }], '')).toEqual({});
  });

  it('includes entries and notes', () => {
    const p = buildMeritsFlawsPayload(
      [{ id: '1', name: 'Eidetic Memory', points: 2, note: 'ST ok' }],
      'extra'
    );
    expect(p.entries).toHaveLength(1);
    expect(p.entries[0].name).toBe('Eidetic Memory');
    expect(p.notes).toBe('extra');
  });
});

describe('parseMeritsFlawsFromApi', () => {
  it('reads legacy notes-only', () => {
    const { globalNotes, rows } = parseMeritsFlawsFromApi({ notes: 'legacy text' });
    expect(globalNotes).toBe('legacy text');
    expect(rows.length).toBeGreaterThanOrEqual(1);
  });
});
