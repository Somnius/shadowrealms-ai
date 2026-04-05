import React from 'react';
import { createEmptyMeritRow } from '../../characterSheet/meritsFlaws';

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
      <div style={{ color: '#94a3b8', fontSize: '12px', marginBottom: '10px' }}>
        Named merits and flaws (points + for merits, − for flaws). Add rows as on a paper sheet.
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
            placeholder="Name"
            value={r.name}
            onChange={(e) => update(r.id, 'name', e.target.value)}
            style={{
              flex: '2 1 160px',
              padding: '8px',
              background: '#0f1729',
              color: '#e0e0e0',
              border: '1px solid #2a2a4e',
              borderRadius: '6px',
            }}
          />
          <input
            type="number"
            title="Points (+ merit / − flaw)"
            placeholder="±pts"
            value={r.points === '' || r.points === null ? '' : r.points}
            onChange={(e) => {
              const v = e.target.value;
              if (v === '') update(r.id, 'points', '');
              else update(r.id, 'points', parseInt(v, 10) || 0);
            }}
            style={{
              width: '72px',
              padding: '8px',
              background: '#0f1729',
              color: '#e0e0e0',
              border: '1px solid #2a2a4e',
              borderRadius: '6px',
            }}
          />
          <input
            placeholder="Note (optional)"
            value={r.note}
            onChange={(e) => update(r.id, 'note', e.target.value)}
            style={{
              flex: '2 1 140px',
              padding: '8px',
              background: '#0f1729',
              color: '#e0e0e0',
              border: '1px solid #2a2a4e',
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
              background: '#1e293b',
              color: rows.length <= 1 ? '#475569' : '#94a3b8',
              border: '1px solid #475569',
              borderRadius: '6px',
              cursor: rows.length <= 1 ? 'not-allowed' : 'pointer',
            }}
          >
            Remove
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
          color: '#c4b5fd',
          border: '1px dashed #6d28d9',
          borderRadius: '6px',
          cursor: 'pointer',
        }}
      >
        + Add row
      </button>
      <label style={{ color: '#c4b5fd', display: 'block', marginTop: '18px', marginBottom: '8px' }}>
        Extra notes (optional)
      </label>
      <textarea
        value={globalNotes}
        onChange={(e) => setGlobalNotes(e.target.value)}
        rows={2}
        placeholder="House rules, ST approval, page refs…"
        style={{
          width: '100%',
          padding: '12px',
          background: '#0f1729',
          color: '#e0e0e0',
          border: '2px solid #2a2a4e',
          borderRadius: '8px',
          resize: 'vertical',
        }}
      />
    </div>
  );
}
