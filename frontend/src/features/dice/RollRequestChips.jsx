import React, { createContext, useContext } from 'react';
import { Glyph } from '../../design';
import { rollRequestText, rollRequestsOf } from './rollRequests';
import { t } from '../../i18n';
import './rollRequests.css';

/**
 * Who may roll from a request: { userId, onRoll(request) }. Provided by the play view; without it
 * (or for anyone but the player who asked the Storyteller) the chips are text only.
 */
export const RollRequestContext = createContext({ userId: null, onRoll: null });

/**
 * The rolls a Storyteller message asks for, as chips under the text. The player who asked (the
 * message was saved under their account) gets a button that opens the roll dialog pre-filled.
 */
export default function RollRequestChips({ message }) {
  const { userId, onRoll } = useContext(RollRequestContext);
  const requests = rollRequestsOf(message);
  if (!requests.length) return null;
  const mine = !!onRoll && userId != null && message.user_id != null && String(message.user_id) === String(userId) && !message.temp;
  return (
    <div className="sr-rollreq" role="group" aria-label={t('dice:request.group', 'Rolls asked for')}>
      {requests.map((req, i) => {
        const text = rollRequestText(req);
        return mine ? (
          <button
            key={i}
            type="button"
            className="sr-rollreq__chip sr-rollreq__chip--action"
            onClick={() => onRoll(req)}
            title={t('dice:request.open', 'Open the roll dialog with this pool')}
          >
            <Glyph name="d10" size={14} />
            <span>{t('dice:request.roll', 'Roll: {{text}}', { text })}</span>
          </button>
        ) : (
          <span key={i} className="sr-rollreq__chip">
            <Glyph name="d10" size={14} />
            <span>{t('dice:request.roll', 'Roll: {{text}}', { text })}</span>
          </span>
        );
      })}
    </div>
  );
}
