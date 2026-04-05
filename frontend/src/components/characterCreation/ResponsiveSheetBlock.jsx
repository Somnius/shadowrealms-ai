import React, { useEffect, useState } from 'react';
import SheetSection from './SheetSection';

/**
 * Desktop: anchored block with SheetSection.
 * Narrow view: same content inside <details> for collapsible sections (accordion-style).
 */
export default function ResponsiveSheetBlock({ sectionId, title, subtitle, accent, children }) {
  const [narrow, setNarrow] = useState(false);

  useEffect(() => {
    if (typeof window === 'undefined') return undefined;
    const mq = window.matchMedia('(max-width: 768px)');
    const fn = () => setNarrow(mq.matches);
    fn();
    mq.addEventListener('change', fn);
    return () => mq.removeEventListener('change', fn);
  }, []);

  if (!narrow) {
    return (
      <div id={sectionId}>
        <SheetSection title={title} subtitle={subtitle} accent={accent}>
          {children}
        </SheetSection>
      </div>
    );
  }

  return (
    <details
      id={sectionId}
      open
      style={{
        marginBottom: '16px',
        border: '1px solid #2a2a4e',
        borderRadius: '10px',
        background: 'linear-gradient(165deg, rgba(15,23,41,0.95) 0%, rgba(22,33,62,0.85) 100%)',
        boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04)',
      }}
    >
      <summary
        style={{
          listStyle: 'none',
          cursor: 'pointer',
          padding: '14px 16px',
          fontFamily: 'Cinzel, serif',
          fontSize: '15px',
          color: accent || '#e94560',
          letterSpacing: '0.06em',
          textTransform: 'uppercase',
          borderBottom: `1px solid ${accent || '#e94560'}44`,
        }}
      >
        {title}
        <span style={{ float: 'right', fontSize: '12px', color: '#8b8b9f' }}>▼</span>
      </summary>
      {subtitle ? (
        <p style={{ margin: '0 16px 8px', fontSize: '12px', color: '#8b8b9f' }}>{subtitle}</p>
      ) : null}
      <div style={{ padding: '0 14px 16px' }}>{children}</div>
    </details>
  );
}
