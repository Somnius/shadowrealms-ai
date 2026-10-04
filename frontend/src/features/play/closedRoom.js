import { t } from '../../i18n';

/** Thematic copy for a room the Storyteller closed (aligned with backend `location_closed` flavor). */
export function closedRoomCopy(gameSystem, closureReason, locationName) {
  const gs = String(gameSystem || '').toLowerCase();
  const reason = String(closureReason || '').trim();
  const label = locationName || t('play:closed.thisRoom', 'This room');
  const lead = reason
    ? t('play:closed.leadReason', '{{room}} is sealed: “{{reason}}”', { room: label, reason })
    : t('play:closed.lead', '{{room}} is sealed until the Storyteller reopens it.', { room: label });
  let flavor = t('play:closed.flavor', 'The table has called cut on this scene.');
  if (gs.includes('vampire') || gs.includes('masquerade')) {
    flavor = t('play:closed.flavorVampire', 'Even the oldest Kindred must wait when the Prince locks Elysium’s doors.');
  } else if (gs.includes('werewolf') || gs.includes('garou') || gs.includes('apocalypse')) {
    flavor = t('play:closed.flavorWerewolf', 'The caern’s pulse says “hunt elsewhere tonight.”');
  } else if (gs.includes('mage') || gs.includes('ascension') || gs.includes('awakening')) {
    flavor = t('play:closed.flavorMage', 'The Consensus politely declines your Paradigm until further notice.');
  }
  return { title: t('play:closed.title', '{{room}}: unavailable', { room: label }), lead, flavor };
}
