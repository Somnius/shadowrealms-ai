import React from 'react';

/**
 * Clickable WoD-style dot track (filled circles). `maxRank` is usually 5.
 */
export default function DotTrack({ value, maxRank, onChange, disabled, accent }) {
  const rank = Math.max(0, Math.min(maxRank, parseInt(value, 10) || 0));
  const a = accent || '#c4b5fd';
  return (
    <div
      role="group"
      aria-label={`Rating ${rank} of ${maxRank}`}
      style={{ display: 'flex', alignItems: 'center', gap: '5px', flexWrap: 'nowrap' }}
    >
      {Array.from({ length: maxRank }, (_, i) => {
        const n = i + 1;
        const filled = n <= rank;
        return (
          <button
            key={n}
            type="button"
            disabled={disabled}
            onClick={() => onChange(filled && n === rank ? n - 1 : n)}
            title={`Set to ${n}`}
            style={{
              width: '18px',
              height: '18px',
              minWidth: '18px',
              padding: 0,
              borderRadius: '50%',
              border: `2px solid ${filled ? a : '#4b5568'}`,
              background: filled
                ? `radial-gradient(circle at 30% 30%, ${a}, #5b21b6)`
                : 'transparent',
              cursor: disabled ? 'not-allowed' : 'pointer',
              boxShadow: filled ? `0 0 8px ${a}55` : 'none',
              transition: 'transform 0.12s ease, box-shadow 0.12s ease',
            }}
            onMouseDown={(e) => e.preventDefault()}
          />
        );
      })}
    </div>
  );
}
