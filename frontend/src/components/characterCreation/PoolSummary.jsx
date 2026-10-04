import {
  abilityPoolRemainders,
  attributePoolRemainders,
} from '../../characterSheet/validation';
import { t } from '../../i18n';

const chip = (label, rem, color) => (
  <span
    key={label}
    style={{
      fontSize: '11px',
      padding: '4px 10px',
      borderRadius: '6px',
      background: rem === 0 ? 'rgba(34,197,94,0.12)' : 'rgba(248,113,113,0.08)',
      color: rem === 0 ? 'var(--sr-ok-400)' : color,
      border: `1px solid ${rem === 0 ? '#16653444' : '#991b1b33'}`,
    }}
  >
    {label}: <strong>{rem}</strong> {t('wizard:pool.left', 'left')}
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
          border: '1px solid var(--sr-night-700)',
          borderRadius: '8px',
          marginBottom: '14px',
        }}
      >
        <span style={{ fontSize: '11px', color: 'var(--sr-bone-300)', marginRight: '4px' }}>Attributes</span>
        {chip('Physical', rp, 'var(--sr-danger-400)')}
        {chip('Social', rs, 'var(--sr-arcane-400)')}
        {chip('Mental', rm, 'var(--sr-info-400)')}
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
          border: '1px solid var(--sr-night-700)',
          borderRadius: '8px',
          marginBottom: '14px',
        }}
      >
        <span style={{ fontSize: '11px', color: 'var(--sr-bone-300)', marginRight: '4px' }}>Abilities</span>
        {chip('Talents', rt, 'var(--sr-gold-400)')}
        {chip('Skills', rsk, '#34d399')}
        {chip('Knowledges', rkn, 'var(--sr-arcane-400)')}
      </div>
    );
  }

  return null;
}
