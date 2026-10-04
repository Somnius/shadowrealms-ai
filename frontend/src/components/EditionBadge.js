import React from 'react';
import { editionOf, V5 } from '../rules/rulesEdition';
import { t } from '../i18n';

/**
 * Small "V5" / "Classic" pill shown next to a campaign's game system.
 * Only shown for Vampire chronicles (the only line with a choice) or anything marked V5,
 * and only when the object actually carries `rules_edition`.
 */
export default function EditionBadge({ campaign, style }) {
  // Only show what the API told us; never guess an edition for objects without the field.
  if (!campaign || campaign.rules_edition == null) return null;
  const gs = String(campaign.game_system || '').toLowerCase();
  const ed = editionOf(campaign);
  if (gs !== 'vampire' && ed !== V5) return null;
  const v5 = ed === V5;
  return (
    <span
      title={v5 ? t('dice:edition.v5Long', 'V5 (5th Edition)') : t('dice:edition.classicLong', 'Classic (Revised)')}
      data-testid="edition-badge"
      style={{
        display: 'inline-block',
        marginLeft: '6px',
        padding: '1px 7px',
        borderRadius: '999px',
        fontSize: '11px',
        fontWeight: 700,
        letterSpacing: '0.04em',
        lineHeight: '16px',
        verticalAlign: 'middle',
        background: v5 ? 'rgba(220, 38, 38, 0.18)' : 'rgba(148, 163, 184, 0.15)',
        color: v5 ? 'var(--sr-blood-300)' : 'var(--sr-bone-300)',
        border: `1px solid ${v5 ? 'var(--sr-blood-600)' : 'var(--sr-bone-500)'}`,
        ...style,
      }}
    >
      {v5 ? t('dice:edition.v5', 'V5') : t('dice:edition.classic', 'Classic')}
    </span>
  );
}
