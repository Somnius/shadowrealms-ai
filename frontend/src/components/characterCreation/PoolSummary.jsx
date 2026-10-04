import React from 'react';
import {
  abilityPoolRemainders,
  attributePoolRemainders,
} from '../../characterSheet/validation';

const chip = (label, rem, color) => (
  <span
    key={label}
    style={{
      fontSize: '11px',
      padding: '4px 10px',
      borderRadius: '6px',
      background: rem === 0 ? 'rgba(34,197,94,0.12)' : 'rgba(248,113,113,0.08)',
      color: rem === 0 ? '#86efac' : color,
      border: `1px solid ${rem === 0 ? '#16653444' : '#991b1b33'}`,
    }}
  >
    {label}: <strong>{rem}</strong> left
  </span>
);

/**
 * Sticky strip showing remaining dots for attribute or ability pools.
 */
export default function PoolSummary({
  variant,
  attrs,
  pools,
  abilities,
  abilityPools,
  customAbilities,
  nosferatu = false,
}) {
  if (variant === 'attributes') {
    const rem = attributePoolRemainders(attrs, pools, { nosferatu });
    const rp = Math.max(0, rem.physical);
    const rs = Math.max(0, rem.social);
    const rm = Math.max(0, rem.mental);
    return (
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '8px',
          alignItems: 'center',
          padding: '10px 12px',
          background: 'rgba(15,23,41,0.92)',
          border: '1px solid #2a2a4e',
          borderRadius: '8px',
          marginBottom: '14px',
        }}
      >
        <span style={{ fontSize: '11px', color: '#94a3b8', marginRight: '4px' }}>Attributes</span>
        {chip('Physical', rp, '#f87171')}
        {chip('Social', rs, '#a78bfa')}
        {chip('Mental', rm, '#38bdf8')}
      </div>
    );
  }

  if (variant === 'abilities') {
    const rem = abilityPoolRemainders(abilities, abilityPools, customAbilities);
    const rt = rem.talents;
    const rsk = rem.skills;
    const rkn = rem.knowledges;
    return (
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '8px',
          alignItems: 'center',
          padding: '10px 12px',
          background: 'rgba(15,23,41,0.92)',
          border: '1px solid #2a2a4e',
          borderRadius: '8px',
          marginBottom: '14px',
        }}
      >
        <span style={{ fontSize: '11px', color: '#94a3b8', marginRight: '4px' }}>Abilities</span>
        {chip('Talents', rt, '#fbbf24')}
        {chip('Skills', rsk, '#34d399')}
        {chip('Knowledges', rkn, '#818cf8')}
      </div>
    );
  }

  return null;
}
