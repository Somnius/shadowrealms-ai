import React from 'react';

export default function SheetSection({ title, subtitle, children, accent }) {
  return (
    <div
      style={{
        marginBottom: '22px',
        padding: '16px 14px',
        background: 'linear-gradient(165deg, rgba(15,23,41,0.95) 0%, rgba(22,33,62,0.85) 100%)',
        border: '1px solid var(--sr-night-700)',
        borderRadius: '10px',
        boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04)',
      }}
    >
      <div
        style={{
          borderBottom: `1px solid color-mix(in srgb, ${accent || 'var(--sr-blood-500)'} 27%, transparent)`,
          paddingBottom: '10px',
          marginBottom: '14px',
        }}
      >
        <h3
          style={{
            margin: 0,
            fontFamily: 'var(--sr-font-display)',
            fontSize: '16px',
            color: accent || 'var(--sr-blood-500)',
            letterSpacing: '0.06em',
            textTransform: 'uppercase',
          }}
        >
          {title}
        </h3>
        {subtitle ? (
          <p style={{ margin: '6px 0 0', fontSize: '12px', color: 'var(--sr-bone-500)' }}>{subtitle}</p>
        ) : null}
      </div>
      {children}
    </div>
  );
}
