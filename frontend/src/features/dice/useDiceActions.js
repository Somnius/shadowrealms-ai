import { useCallback, useState } from 'react';
import { buildDiceMarker } from '../../dice/diceMarker';
import { editionOf, V5 } from '../../rules/rulesEdition';
import { makeAnimationId } from '../chat/sendFlow';
import { t } from '../../i18n';

/** Storyteller (oWoD) pool: `5`, `4+3`, `7-1`: digits with +/- between. Throws with a message. */
export function parseStorytellerPool(input) {
  const s = String(input || '').replace(/\s/g, '');
  if (!/^\d+([+-]\d+)*$/.test(s)) {
    throw new Error(t('dice:error.poolFormat', 'Pool must be digits with + or - (e.g. 5, 4+3, 7-1).'));
  }
  return s.split(/(?=[+-])/).reduce((sum, p) => sum + parseInt(p, 10), 0);
}

/**
 * Dice actions of the play view: roll (POST /campaigns/<c>/roll), V5 Willpower reroll, V5 Rouse check.
 *
 * With location_id the server saves the dice marker (dice_animation[_hidden]:<id>) and the result
 * line (dice_roll[_hidden]:<id>) itself and answers server_posted: true, message_ids, messages, so
 * nobody can post a result that wasn't rolled. Then we only show the saved rows (or refetch); the
 * marker row starts the overlay through useDiceOverlay. Older backends (no server_posted) still get
 * the two rows posted from here (postRollToRoom).
 */
/** "Willpower −1 (Superficial damage)" from a reroll response, or undefined when none was spent. */
export function willpowerSpentText(data) {
  if (!data || !data.willpower_spent) return undefined;
  const cost = (data.roll_result && data.roll_result.willpower_cost) || '';
  if (cost === 'aggravated') return t('dice:reroll.spentAggravated', 'Willpower −1 (Aggravated damage: the track was full of Superficial).');
  return t('dice:reroll.spentSuperficial', 'Willpower −1 (Superficial damage).');
}

export function useDiceActions({
  api,
  campaign,
  location,
  speakAs,
  character,
  onCharacterHunger,
  startFromMarker,
  appendMessages,
  fetchRoom,
  toast,
}) {
  const [lastV5Roll, setLastV5Roll] = useState(null);
  const [rolling, setRolling] = useState(false);
  const [rerolling, setRerolling] = useState(false);
  const [rousing, setRousing] = useState(false);

  const err = useCallback((title) => toast({ tone: 'danger', title }), [toast]);

  /** Server already saved the chat rows: show them now if they're for the open room. */
  const showServerRows = useCallback(
    (data, locationId) => {
      if (String(locationId) !== String(location?.id)) return;
      const rows = Array.isArray(data.messages) ? data.messages.filter((m) => m && m.id != null) : [];
      if (rows.length) appendMessages(rows);
      else if (fetchRoom) fetchRoom();
    },
    [location, appendMessages, fetchRoom]
  );

  const postRollToRoom = useCallback(
    async (rollResult, chatBody, { hidden = false, locationId, speakAs: sa, characterId } = {}) => {
      if (locationId == null) {
        err(t('dice:error.noRoom', 'Join a room first.'));
        return false;
      }
      const animationId = makeAnimationId();
      const marker = buildDiceMarker(rollResult, { animationId, startedAtMs: Date.now(), durationMs: 3000 });
      startFromMarker(marker);
      const roomPath = `/campaigns/${campaign.id}/locations/${locationId}`;
      const m1 = await api(roomPath, {
        method: 'POST',
        body: {
          content: JSON.stringify(marker),
          message_type: 'system',
          role: 'assistant',
          ai_message_kind: `${hidden ? 'dice_animation_hidden' : 'dice_animation'}:${animationId}`,
        },
      });
      if (!m1.ok) {
        err(m1.data.error || t('dice:error.marker', 'Could not post the dice animation.'));
        return false;
      }
      const m2 = await api(roomPath, {
        method: 'POST',
        body: {
          content: chatBody,
          message_type: 'action',
          role: 'user',
          ai_message_kind: `${hidden ? 'dice_roll_hidden' : 'dice_roll'}:${animationId}`,
          speak_as: sa,
          ...(sa === 'character' && characterId ? { character_id: characterId } : {}),
        },
      });
      if (!m2.ok) {
        err(m2.data.error || t('dice:error.resultNotPosted', 'Roll saved but could not be posted to the room.'));
        return false;
      }
      if (String(locationId) === String(location?.id)) appendMessages([m1.data.data, m2.data.data].filter(Boolean));
      return true;
    },
    [api, campaign, location, startFromMarker, appendMessages, err]
  );

  /**
   * form: { pool, difficulty, v5Difficulty, hunger, specialty, willpower, hidden, reason }
   * Returns true when the roll was posted.
   */
  const roll = useCallback(
    async (form) => {
      if (!campaign?.id || !location?.id) {
        err(t('dice:error.noRoom', 'Join a room first.'));
        return false;
      }
      let pool;
      try {
        pool = parseStorytellerPool(form.pool);
      } catch (e) {
        err(e.message);
        return false;
      }
      if (pool < 1 || pool > 50) {
        err(t('dice:error.poolRange', 'Pool must be between 1 and 50 dice.'));
        return false;
      }
      const v5 = editionOf(campaign) === V5;
      const d = Number(v5 ? form.v5Difficulty : form.difficulty);
      if (v5 ? !(d >= 0 && d <= 10) : !(d >= 2 && d <= 10)) {
        err(v5 ? t('dice:error.v5Diff', 'Difficulty must be between 0 and 10.') : t('dice:error.diff', 'Difficulty must be between 2 and 10.'));
        return false;
      }
      const asChar = speakAs === 'character' && character?.id;
      setRolling(true);
      try {
        const r = await api(`/campaigns/${campaign.id}/roll`, {
          method: 'POST',
          body: {
            pool_size: pool,
            ...(v5 ? { difficulty: d, hunger: form.hunger } : { difficulty: d, specialty: !!form.specialty, willpower: !!form.willpower }),
            speak_as: speakAs,
            ...(asChar ? { character_id: character.id } : {}),
            // No reason typed: leave it out and the server labels the roll (in English, the same for
            // every reader), instead of saving it in this player's interface language.
            ...(String(form.reason || '').trim() ? { action_description: String(form.reason).trim() } : {}),
            location_id: location.id,
            hidden: !!form.hidden,
          },
        });
        if (!r.ok) {
          err(r.data.error || t('dice:error.rollFailed', 'Roll failed.'));
          return false;
        }
        const result = r.data.roll_result || {};
        if (r.data.server_posted) showServerRows(r.data, location.id);
        else {
          const ok = await postRollToRoom(result, r.data.chat_message || '', {
            hidden: !!form.hidden,
            locationId: location.id,
            speakAs,
            characterId: asChar ? character.id : undefined,
          });
          if (!ok) return false;
        }
        if (editionOf(result) === V5 && result.can_reroll) {
          setLastV5Roll({
            ...result,
            roll_id: result.roll_id != null ? result.roll_id : r.data.roll_id,
            hidden: !!form.hidden,
            campaignId: campaign.id,
            locationId: location.id,
            speakAs,
            characterId: asChar ? character.id : undefined,
          });
        } else setLastV5Roll(null);
        toast({ tone: 'ok', title: form.hidden ? t('dice:posted.hidden', 'Private roll posted to this room.') : t('dice:posted.public', 'Roll posted to this room.') });
        return true;
      } finally {
        setRolling(false);
      }
    },
    [api, campaign, location, speakAs, character, postRollToRoom, showServerRows, err, toast]
  );

  const reroll = useCallback(
    async (indices) => {
      const last = lastV5Roll;
      if (!last) return;
      if (String(campaign?.id) !== String(last.campaignId)) {
        err(t('dice:error.rerollElsewhere', 'Go back to the chronicle where you rolled to reroll.'));
        return;
      }
      setRerolling(true);
      try {
        const r = await api(`/campaigns/${last.campaignId}/roll/${last.roll_id}/reroll`, {
          method: 'POST',
          body: { indices, location_id: last.locationId, hidden: !!last.hidden, speak_as: last.speakAs },
        });
        if (!r.ok) {
          err(r.data.error || t('dice:error.rerollFailed', 'Reroll failed.'));
          if (r.status === 409) setLastV5Roll(null);
          return;
        }
        let ok = true;
        if (r.data.server_posted) showServerRows(r.data, last.locationId);
        else {
          ok = await postRollToRoom(r.data.roll_result || {}, r.data.chat_message || '', {
            hidden: last.hidden,
            locationId: last.locationId,
            speakAs: last.speakAs,
            characterId: last.characterId,
          });
        }
        if (ok) {
          toast({
            tone: 'ok',
            title:
              String(last.locationId) === String(location?.id)
                ? t('dice:reroll.done', 'Willpower reroll posted.')
                : t('dice:reroll.doneElsewhere', 'Willpower reroll posted to the room you rolled in.'),
            body: willpowerSpentText(r.data),
          });
        }
        setLastV5Roll(null);
      } finally {
        setRerolling(false);
      }
    },
    [api, campaign, location, lastV5Roll, postRollToRoom, showServerRows, err, toast]
  );

  /** V5 Rouse check; hunger = value typed in the dialog (used when not speaking as the character). */
  const rouse = useCallback(
    async (hunger) => {
      if (!campaign?.id || !location?.id) return null;
      const asChar = speakAs === 'character' && character?.id;
      setRousing(true);
      try {
        const r = await api(`/campaigns/${campaign.id}/rouse`, {
          method: 'POST',
          body: { location_id: location.id, speak_as: speakAs, ...(asChar ? { character_id: character.id } : { hunger }) },
        });
        if (!r.ok) {
          err(r.data.error || t('dice:error.rouseFailed', 'Rouse check failed.'));
          return null;
        }
        const d = r.data;
        const after = Number(d.hunger_after);
        if (asChar && Number.isFinite(after) && onCharacterHunger) onCharacterHunger(after);
        if (d.server_posted) showServerRows(d, location.id);
        else {
          const msg = await api(`/campaigns/${campaign.id}/locations/${location.id}`, {
            method: 'POST',
            body: {
              content: d.chat_message || `Rouse check: ${d.die}`,
              message_type: 'action',
              role: 'user',
              speak_as: speakAs,
              ...(asChar ? { character_id: character.id } : {}),
            },
          });
          if (msg.ok && msg.data.data) appendMessages([msg.data.data]);
        }
        toast({
          tone: d.success ? 'ok' : 'blood',
          title: d.success
            ? t('dice:rouse.ok', 'Rouse check: {{die}}, no Hunger gain.', { die: d.die })
            : t('dice:rouse.fail', 'Rouse check: {{die}}, Hunger {{before}} → {{after}}.', { die: d.die, before: d.hunger_before, after: d.hunger_after }),
        });
        // undefined (not null) = posted, but no new Hunger value to show
        return Number.isFinite(after) ? after : undefined;
      } finally {
        setRousing(false);
      }
    },
    [api, campaign, location, speakAs, character, onCharacterHunger, appendMessages, showServerRows, err, toast]
  );

  return { roll, reroll, rouse, lastV5Roll, setLastV5Roll, rolling, rerolling, rousing };
}
