import React from 'react';
import { MENTAL, PHYSICAL, SOCIAL } from '../../characterSheet/constants';
import DotTrack from './DotTrack';

export default function AttributeColumns({ attrs, setAttrs, pools }) {
  const col = (title, keys, pool, accent) => (
    <div style={{ flex: '1 1 200px', minWidth: 0 }}>
      <div
        style={{
          textAlign: 'center',
          fontFamily: 'Cinzel, serif',
          fontSize: '12px',
          color: accent,
          marginBottom: '12px',
          letterSpacing: '0.08em',
        }}
      >
        {title}
        <span style={{ color: '#6b7280', fontFamily: 'system-ui', marginLeft: '6px' }}>
          ({pool} pts)
        </span>
      </div>
      {keys.map((k) => (
        <div
          key={k}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '10px',
            marginBottom: '10px',
            padding: '6px 8px',
            background: 'rgba(0,0,0,0.2)',
            borderRadius: '6px',
          }}
        >
          <span
            style={{
              color: '#d1d5db',
              fontSize: '13px',
              textTransform: 'capitalize',
              flex: '1 1 auto',
            }}
          >
            {k}
          </span>
          <DotTrack
            value={attrs[k]}
            maxRank={5}
            accent={accent}
            onChange={(n) => {
              const catKeys =
                title === 'Physical' ? PHYSICAL : title === 'Social' ? SOCIAL : MENTAL;
              const poolSize =
                title === 'Physical'
                  ? pools.physical
                  : title === 'Social'
                    ? pools.social
                    : pools.mental;
              const old = parseInt(attrs[k], 10) || 1;
              const next = Math.max(1, Math.min(5, n));
              const delta = next - old;
              const sum = catKeys.reduce((s, key) => s + (parseInt(attrs[key], 10) || 1), 0);
              if (sum + delta > poolSize) return;
              setAttrs((prev) => ({ ...prev, [k]: next }));
            }}
          />
        </div>
      ))}
    </div>
  );

  return (
    <div
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: '18px',
        justifyContent: 'space-between',
      }}
    >
      {col('Physical', PHYSICAL, pools.physical, '#f87171')}
      {col('Social', SOCIAL, pools.social, '#a78bfa')}
      {col('Mental', MENTAL, pools.mental, '#38bdf8')}
    </div>
  );
}
