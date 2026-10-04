import { MENTAL, PHYSICAL, SOCIAL } from '../../characterSheet/constants';
import { attributeBase } from '../../characterSheet/validation';
import DotTrack from './DotTrack';
import { t } from '../../i18n';

/**
 * `pools` = dots to ADD per category on top of the free dot in each attribute (7/5/3).
 * Without `freebieMode` the UI stops at the budget; with it, any rating 1–5 (priced as freebies).
 * `nosferatu`: Appearance is fixed at 0 (classic.json creation.attributes.nosferatu_appearance).
 */
export default function AttributeColumns({
  attrs,
  setAttrs,
  pools,
  freebieMode = false,
  nosferatu = false,
}) {
  const col = (title, keys, pool, accent) => (
    <div style={{ flex: '1 1 200px', minWidth: 0 }}>
      <div
        style={{
          textAlign: 'center',
          fontFamily: 'var(--sr-font-display)',
          fontSize: '12px',
          color: accent,
          marginBottom: '12px',
          letterSpacing: '0.08em',
        }}
      >
        {title}
        <span style={{ color: 'var(--sr-bone-500)', fontFamily: 'var(--sr-font-ui)', marginLeft: '6px' }}>
          {t('wizard:pool.plusDots', '(+{{n}} dots)', { n: pool })}
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
              color: 'var(--sr-bone-100)',
              fontSize: '13px',
              textTransform: 'capitalize',
              flex: '1 1 auto',
            }}
          >
            {k}
            {nosferatu && k === 'appearance' ? (
              <span style={{ display: 'block', color: 'var(--sr-bone-300)', fontSize: '11px', textTransform: 'none' }}>
                {t('wizard:nosferatuAlwaysZero', 'Nosferatu: always 0')}
              </span>
            ) : null}
          </span>
          <DotTrack
            value={attrs[k]}
            maxRank={5}
            accent={accent}
            disabled={nosferatu && k === 'appearance'}
            onChange={(n) => {
              if (nosferatu && k === 'appearance') return;
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
              const added = catKeys.reduce(
                (s, key) =>
                  s + (parseInt(attrs[key], 10) || 0) - attributeBase(key, { nosferatu }),
                0
              );
              if (!freebieMode && delta > 0 && added + delta > poolSize) return;
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
      {col('Physical', PHYSICAL, pools.physical, 'var(--sr-danger-400)')}
      {col('Social', SOCIAL, pools.social, 'var(--sr-arcane-400)')}
      {col('Mental', MENTAL, pools.mental, 'var(--sr-info-400)')}
    </div>
  );
}
