import { t } from '../../i18n';

/**
 * Clickable WoD-style dot track (filled circles). `maxRank` is usually 5.
 * `label` (optional) names the trait for screen readers.
 */
export default function DotTrack({ value, maxRank, onChange, disabled, accent, label }) {
  const rank = Math.max(0, Math.min(maxRank, parseInt(value, 10) || 0));
  const a = accent || 'var(--sr-arcane-300)';
  return (
    <div
      role="group"
      aria-label={label ? t('wizard:dots.labelled', '{{label}}: {{rank}} of {{max}}', { label, rank, max: maxRank }) : t('wizard:dots.rating', 'Rating {{rank}} of {{max}}', { rank, max: maxRank })}
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
            title={t('wizard:dots.setTo', 'Set to {{n}}', { n })}
            aria-label={label ? t('wizard:dots.setLabelTo', 'Set {{label}} to {{n}}', { label, n }) : t('wizard:dots.setTo', 'Set to {{n}}', { n })}
            style={{
              width: '18px',
              height: '18px',
              minWidth: '18px',
              padding: 0,
              borderRadius: '50%',
              border: `2px solid ${filled ? a : 'var(--sr-night-600)'}`,
              background: filled
                ? `radial-gradient(circle at 30% 30%, ${a}, var(--sr-arcane-700))`
                : 'transparent',
              cursor: disabled ? 'not-allowed' : 'pointer',
              boxShadow: filled ? `0 0 8px color-mix(in srgb, ${a} 33%, transparent)` : 'none',
              transition: 'transform 0.12s ease, box-shadow 0.12s ease',
            }}
            onMouseDown={(e) => e.preventDefault()}
          />
        );
      })}
    </div>
  );
}
