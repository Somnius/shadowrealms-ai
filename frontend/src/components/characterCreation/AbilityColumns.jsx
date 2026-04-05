import React from 'react';
import { KNOWLEDGES, SKILLS, TALENTS } from '../../characterSheet/constants';
import DotTrack from './DotTrack';

function newCustomRow() {
  return { id: `c_${Math.random().toString(36).slice(2, 11)}`, label: '', dots: 0 };
}

/**
 * Three-column abilities + optional custom rows per column (count toward same pools).
 */
export default function AbilityColumns({
  abilities,
  setAbilities,
  pools,
  customAbilities,
  setCustomAbilities,
}) {
  const sumCustom = (rows) => (rows || []).reduce((s, r) => s + (parseInt(r.dots, 10) || 0), 0);

  const setDot = (key, list, poolSize, n) => {
    const old = parseInt(abilities[key], 10) || 0;
    const next = Math.max(0, Math.min(5, n));
    const delta = next - old;
    const cat = list === TALENTS ? 'talents' : list === SKILLS ? 'skills' : 'knowledges';
    const customRows = customAbilities?.[cat] || [];
    const sum =
      list.reduce((s, [kk]) => s + (parseInt(abilities[kk], 10) || 0), 0) + sumCustom(customRows);
    if (sum + delta > poolSize) return;
    setAbilities((prev) => ({ ...prev, [key]: next }));
  };

  const setCustomDot = (cat, id, poolSize, list, n) => {
    const nextVal = Math.max(0, Math.min(5, n));
    const rows = customAbilities?.[cat] || [];
    const row = rows.find((r) => r.id === id);
    if (!row) return;
    const old = parseInt(row.dots, 10) || 0;
    const delta = nextVal - old;
    const baseList = list === TALENTS ? TALENTS : list === SKILLS ? SKILLS : KNOWLEDGES;
    const baseSum = baseList.reduce((s, [k]) => s + (parseInt(abilities[k], 10) || 0), 0);
    const otherCustom = rows.filter((r) => r.id !== id).reduce((s, r) => s + (parseInt(r.dots, 10) || 0), 0);
    if (baseSum + otherCustom + nextVal > poolSize) return;
    setCustomAbilities((prev) => ({
      ...prev,
      [cat]: rows.map((r) => (r.id === id ? { ...r, dots: nextVal } : r)),
    }));
  };

  const addCustom = (cat) => {
    setCustomAbilities((prev) => ({
      ...prev,
      [cat]: [...(prev[cat] || []), newCustomRow()],
    }));
  };

  const removeCustom = (cat, id) => {
    setCustomAbilities((prev) => ({
      ...prev,
      [cat]: (prev[cat] || []).filter((r) => r.id !== id),
    }));
  };

  const updateCustomLabel = (cat, id, label) => {
    setCustomAbilities((prev) => ({
      ...prev,
      [cat]: (prev[cat] || []).map((r) => (r.id === id ? { ...r, label } : r)),
    }));
  };

  const col = (title, list, pool, colAccent, catKey) => (
    <div style={{ flex: '1 1 220px', minWidth: 0 }}>
      <div
        style={{
          textAlign: 'center',
          fontFamily: 'Cinzel, serif',
          fontSize: '12px',
          color: colAccent,
          marginBottom: '12px',
          letterSpacing: '0.08em',
        }}
      >
        {title}
        <span style={{ color: '#6b7280', fontFamily: 'system-ui', marginLeft: '6px' }}>
          ({pool} dots)
        </span>
      </div>
      {list.map(([k, label]) => (
        <div
          key={k}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '8px',
            marginBottom: '8px',
            padding: '5px 6px',
            background: 'rgba(0,0,0,0.18)',
            borderRadius: '6px',
          }}
        >
          <span style={{ color: '#c4c4d4', fontSize: '12px', flex: '1 1 auto' }}>{label}</span>
          <DotTrack
            value={abilities[k]}
            maxRank={5}
            accent={colAccent}
            onChange={(n) => setDot(k, list, pool, n)}
          />
        </div>
      ))}
      {(customAbilities?.[catKey] || []).map((row) => (
        <div
          key={row.id}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            marginBottom: '8px',
            padding: '5px 6px',
            background: 'rgba(99,102,241,0.08)',
            borderRadius: '6px',
            border: '1px dashed #4c1d95',
          }}
        >
          <input
            placeholder="Custom ability"
            value={row.label}
            onChange={(e) => updateCustomLabel(catKey, row.id, e.target.value)}
            style={{
              flex: '1 1 100px',
              padding: '6px 8px',
              fontSize: '12px',
              background: '#0f1729',
              color: '#e0e0e0',
              border: '1px solid #2a2a4e',
              borderRadius: '6px',
            }}
          />
          <DotTrack
            value={row.dots}
            maxRank={5}
            accent={colAccent}
            onChange={(n) => setCustomDot(catKey, row.id, pool, list, n)}
          />
          <button
            type="button"
            onClick={() => removeCustom(catKey, row.id)}
            style={{
              padding: '4px 8px',
              fontSize: '11px',
              background: '#1e293b',
              color: '#94a3b8',
              border: '1px solid #475569',
              borderRadius: '6px',
              cursor: 'pointer',
            }}
          >
            ×
          </button>
        </div>
      ))}
      <button
        type="button"
        onClick={() => addCustom(catKey)}
        style={{
          width: '100%',
          marginTop: '6px',
          padding: '6px',
          fontSize: '11px',
          background: 'transparent',
          color: colAccent,
          border: `1px dashed ${colAccent}55`,
          borderRadius: '6px',
          cursor: 'pointer',
        }}
      >
        + Add custom {title.slice(0, -1)}
      </button>
    </div>
  );

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '18px', justifyContent: 'space-between' }}>
      {col('Talents', TALENTS, pools.talents, '#fbbf24', 'talents')}
      {col('Skills', SKILLS, pools.skills, '#34d399', 'skills')}
      {col('Knowledges', KNOWLEDGES, pools.knowledges, '#818cf8', 'knowledges')}
    </div>
  );
}
