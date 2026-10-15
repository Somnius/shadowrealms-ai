/**
 * Shared look and plumbing for the V5 forge steps: styles, the small display components, and the
 * context that hands every step the forge state (see useV5ForgeState.js).
 */
import { createContext, useContext } from 'react';
import { getLanguage, t } from '../../../i18n';
import { bookRef, descIn } from '../../../characterSheet/v5/rulesData';

export const ACCENT = 'var(--sr-blood-500)';

export const inputStyle = {
  width: '100%',
  padding: '10px',
  background: 'var(--sr-night-850)',
  color: 'var(--sr-bone-100)',
  border: '2px solid var(--sr-night-700)',
  borderRadius: '8px',
};
export const labelStyle = { color: 'var(--sr-arcane-300)', display: 'block', marginBottom: '6px', fontSize: '13px' };
export const rowStyle = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: '8px',
  marginBottom: '8px',
  padding: '5px 8px',
  background: 'rgba(0,0,0,0.2)',
  borderRadius: '6px',
};
export const gridStyle = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
  gap: '14px',
};
export const smallButtonStyle = {
  padding: '6px 10px',
  background: 'var(--sr-night-800)',
  color: 'var(--sr-bone-300)',
  border: '1px solid var(--sr-night-600)',
  borderRadius: '6px',
  cursor: 'pointer',
};
export const addButtonStyle = {
  padding: '6px 12px',
  fontSize: '12px',
  background: 'transparent',
  color: 'var(--sr-arcane-300)',
  border: '1px dashed var(--sr-arcane-700)',
  borderRadius: '6px',
  cursor: 'pointer',
};
export const noteStyle = { color: 'var(--sr-bone-300)', fontSize: '13px', lineHeight: 1.5 };
/** The forge's plain and main buttons (Cancel / Create character), also used by the guided mode. */
export const buttonStyle = {
  padding: '10px 18px',
  background: 'var(--sr-night-800)',
  color: 'var(--sr-bone-100)',
  border: '1px solid var(--sr-night-600)',
  borderRadius: '8px',
  cursor: 'pointer',
};
export const primaryButtonStyle = {
  ...buttonStyle,
  padding: '10px 22px',
  background: 'var(--sr-arcane-500)',
  color: 'white',
  border: 'none',
  fontWeight: 'bold',
  fontFamily: 'var(--sr-font-display)',
};

export function scrollToSection(id) {
  const el = typeof document !== 'undefined' ? document.getElementById(id) : null;
  el?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

const ForgeContext = createContext(null);
export const ForgeProvider = ForgeContext.Provider;

/** The forge state object from useV5ForgeState(), for the step components. */
export function useForge() {
  const f = useContext(ForgeContext);
  if (!f) throw new Error('useForge() needs a ForgeProvider');
  return f;
}

/** The error message of a section, under its title. */
export function InlineError({ id }) {
  const { fieldErrors } = useForge();
  return fieldErrors[id] ? (
    <p style={{ color: 'var(--sr-danger-400)', fontSize: '13px', marginBottom: '12px' }}>{fieldErrors[id]}</p>
  ) : null;
}

export function SpreadChips({ status }) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '14px' }}>
      {status.map(({ rating, need, have }) => {
        const ok = need === have;
        return (
          <span
            key={rating}
            style={{
              fontSize: '11px',
              padding: '4px 10px',
              borderRadius: '6px',
              background: ok ? 'rgba(34,197,94,0.12)' : 'rgba(248,113,113,0.08)',
              color: ok ? 'var(--sr-ok-400)' : 'var(--sr-blood-300)',
              border: `1px solid ${ok ? '#16653444' : '#991b1b33'}`,
            }}
          >
            {'●'.repeat(rating)} {have}/{need}
          </span>
        );
      })}
    </div>
  );
}

const DOT_COLOURS = { base: ACCENT, predator: 'var(--sr-gold-400)', xp: 'var(--sr-ok-400)' };

/**
 * Read-only Discipline dots, coloured by source: creation dots, the predator type's dot, XP dots.
 */
export function SourceDots({ label, row, maxRank = 5 }) {
  const sources = [
    ...Array(row.base).fill('base'),
    ...Array(row.predator).fill('predator'),
    ...Array(row.xp).fill('xp'),
  ];
  return (
    <div
      role="group"
      aria-label={t('wizard:dots.labelled', '{{label}}: {{rank}} of {{max}}', { label, rank: row.level, max: maxRank })}
      style={{ display: 'flex', alignItems: 'center', gap: '5px' }}
    >
      {Array.from({ length: Math.max(maxRank, sources.length) }, (_, i) => {
        const src = sources[i];
        const c = src ? DOT_COLOURS[src] : null;
        return (
          <span
            key={i}
            data-dot={src || 'empty'}
            style={{
              width: '18px',
              height: '18px',
              borderRadius: '50%',
              boxSizing: 'border-box',
              border: `2px ${src && src !== 'base' ? 'dashed' : 'solid'} ${c || 'var(--sr-night-600)'}`,
              background: c ? `radial-gradient(circle at 30% 30%, ${c}, var(--sr-arcane-700))` : 'transparent',
            }}
          />
        );
      })}
    </div>
  );
}

/** A labelled text input whose id is v5-field-<key>. */
export function TextField({ id, label, value, onChange, placeholder }) {
  return (
    <div>
      <label htmlFor={id} style={labelStyle}>
        {label}
      </label>
      <input id={id} value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} style={inputStyle} />
    </div>
  );
}

/** A catalog entry's short description in the UI language, with its book and page. */
export function CatalogNote({ entry, style }) {
  if (!entry) return null;
  const text = descIn(entry, getLanguage());
  const ref = bookRef(entry);
  if (!text && !ref) return null;
  return (
    <p className="sr-catalog-note" style={{ color: 'var(--sr-bone-300)', fontSize: '12px', lineHeight: 1.45, margin: '4px 0 0', ...style }}>
      {text}
      {text && ref ? ' ' : ''}
      {ref ? <span style={{ color: 'var(--sr-bone-500)', whiteSpace: 'nowrap' }}>({ref})</span> : null}
    </p>
  );
}
