import React from 'react';
import { editionLabel, editionOf, V5 } from '../rules/rulesEdition';

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
      title={editionLabel(campaign, { long: true })}
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
        color: v5 ? '#fca5a5' : '#cbd5e1',
        border: `1px solid ${v5 ? '#dc2626' : '#64748b'}`,
        ...style,
      }}
    >
      {editionLabel(campaign)}
    </span>
  );
}
