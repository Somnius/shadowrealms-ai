import { createEmptyMeritRow } from '../../characterSheet/meritsFlaws';
import { t } from '../../i18n';

export default function MeritFlawRows({ rows, setRows, globalNotes, setGlobalNotes }) {
  const update = (id, field, value) => {
    setRows((prev) => prev.map((r) => (r.id === id ? { ...r, [field]: value } : r)));
  };

  const addRow = () => setRows((prev) => [...prev, createEmptyMeritRow()]);
  const removeRow = (id) => {
    setRows((prev) => (prev.length <= 1 ? prev : prev.filter((r) => r.id !== id)));
  };

  return (
    <div>
      <div style={{ color: 'var(--sr-bone-300)', fontSize: '12px', marginBottom: '10px' }}>
        {t('wizard:merits.intro', 'Named merits and flaws (points + for merits, − for flaws). Add rows as on a paper sheet.')}
      </div>
      {rows.map((r) => (
        <div
          key={r.id}
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            gap: '10px',
            marginBottom: '10px',
          }}
        >
          <input
            placeholder={t('wizard:merits.name', 'Name')}
            value={r.name}
            onChange={(e) => update(r.id, 'name', e.target.value)}
            style={{
              flex: '2 1 160px',
              padding: '8px',
              background: 'var(--sr-night-850)',
              color: 'var(--sr-bone-100)',
              border: '1px solid var(--sr-night-700)',
              borderRadius: '6px',
            }}
          />
          <input
            type="number"
            title={t('wizard:merits.pointsTitle', 'Points (+ merit / − flaw)')}
            placeholder={t('wizard:merits.pointsPlaceholder', '±pts')}
            value={r.points === '' || r.points === null ? '' : r.points}
            onChange={(e) => {
              const v = e.target.value;
              if (v === '') update(r.id, 'points', '');
              else update(r.id, 'points', parseInt(v, 10) || 0);
            }}
            style={{
              width: '80px',
              padding: '8px',
              background: 'var(--sr-night-850)',
              color: 'var(--sr-bone-100)',
              border: '1px solid var(--sr-night-700)',
              borderRadius: '6px',
            }}
          />
          <input
            placeholder={t('wizard:merits.note', 'Note (optional)')}
            value={r.note}
            onChange={(e) => update(r.id, 'note', e.target.value)}
            style={{
              flex: '2 1 140px',
              padding: '8px',
              background: 'var(--sr-night-850)',
              color: 'var(--sr-bone-100)',
              border: '1px solid var(--sr-night-700)',
              borderRadius: '6px',
            }}
          />
          <button
            type="button"
            onClick={() => removeRow(r.id)}
            disabled={rows.length <= 1}
            style={{
              padding: '8px 12px',
              fontSize: '12px',
              background: 'var(--sr-night-800)',
              color: rows.length <= 1 ? 'var(--sr-night-600)' : 'var(--sr-bone-300)',
              border: '1px solid var(--sr-night-600)',
              borderRadius: '6px',
              cursor: rows.length <= 1 ? 'not-allowed' : 'pointer',
            }}
          >
            {t('wizard:merits.remove', 'Remove')}
          </button>
        </div>
      ))}
      <button
        type="button"
        onClick={addRow}
        style={{
          marginTop: '6px',
          padding: '8px 14px',
          fontSize: '12px',
          background: 'transparent',
          color: 'var(--sr-arcane-300)',
          border: '1px dashed var(--sr-arcane-700)',
          borderRadius: '6px',
          cursor: 'pointer',
        }}
      >
        {t('wizard:merits.addRow', '+ Add row')}
      </button>
      <label style={{ color: 'var(--sr-arcane-300)', display: 'block', marginTop: '18px', marginBottom: '8px' }}>
        {t('wizard:merits.extraNotes', 'Extra notes (optional)')}
      </label>
      <textarea
        value={globalNotes}
        onChange={(e) => setGlobalNotes(e.target.value)}
        rows={2}
        placeholder={t('wizard:merits.extraNotesPlaceholder', 'House rules, ST approval, page refs…')}
        style={{
          width: '100%',
          padding: '12px',
          background: 'var(--sr-night-850)',
          color: 'var(--sr-bone-100)',
          border: '2px solid var(--sr-night-700)',
          borderRadius: '8px',
          resize: 'vertical',
        }}
      />
    </div>
  );
}
