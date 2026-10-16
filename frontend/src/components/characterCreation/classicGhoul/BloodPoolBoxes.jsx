import { t } from '../../../i18n';

/**
 * A Classic ghoul's Blood Pool as squares, like the paper sheet: `max` squares (10), the first
 * `current` filled. Read-only.
 */
export default function BloodPoolBoxes({ current, max = 10, accent = 'var(--sr-blood-500)' }) {
  const m = Math.max(1, Math.min(20, parseInt(max, 10) || 10));
  const c = Math.max(0, Math.min(m, parseInt(current, 10) || 0));
  return (
    <div
      role="img"
      aria-label={t('sheet:classicGhoul.poolAria', 'Blood Pool {{current}} of {{max}}', { current: c, max: m })}
      data-blood-pool={c}
      style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', maxWidth: `${10 * 22}px` }}
    >
      {Array.from({ length: m }, (_, i) => (
        <span
          key={i}
          data-filled={i < c ? 'true' : 'false'}
          style={{
            width: '16px',
            height: '16px',
            border: `2px solid ${i < c ? accent : 'var(--sr-night-600)'}`,
            background: i < c ? accent : 'transparent',
            borderRadius: '2px',
          }}
        />
      ))}
    </div>
  );
}
