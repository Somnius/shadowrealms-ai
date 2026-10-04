import React, { useState } from 'react';
import { Avatar, Badge, DieFace, Glyph, RollFx, rollMood } from '../../design';
import { overlayFromMarker } from '../../dice/diceMarker';
import { classicOutcome, classifyClassicDie } from '../../dice/classicDiceDisplay';
import { classifyV5Die, v5Badges } from '../../dice/v5DiceDisplay';
import Markdown from './markdown';
import { diceAnimationId, messageTime, presentSpeaker } from './messageModel';
import { formatClock, formatFull, formatShort, isoOf } from './timeFormat';
import { t } from '../../i18n';

const BADGE_TONE = { success: 'ok', gold: 'gold', blood: 'blood', danger: 'danger', muted: 'neutral' };

function Time({ ms, timeZone, now, short = true, className }) {
  if (Number.isNaN(ms)) return null;
  return (
    <time className={className} dateTime={isoOf(ms)} title={formatFull(ms, timeZone)}>
      {short ? formatShort(ms, now, timeZone) : formatClock(ms, timeZone)}
    </time>
  );
}

function SpeakerAvatar({ msg, size = 40 }) {
  const sp = presentSpeaker(msg);
  if (sp.tone === 'ai') {
    return (
      <span className="sr-msg__ai-avatar" style={{ width: size, height: size }}>
        {/* static in the list: no infinite loops inside the scrolling message list (design §5.3) */}
        <Glyph name="ai-sigil" size={Math.round(size * 0.8)} />
      </span>
    );
  }
  return (
    <Avatar
      src={sp.avatar}
      name={sp.name}
      size={size}
      alt=""
      sigil={sp.tone === 'storyteller' ? 'crown-thorns' : sp.tone === 'player' ? 'hood' : sp.tone === 'staff' ? 'crown' : 'mask'}
    />
  );
}

function SpeakerName({ msg, secondaryLast = false }) {
  const sp = presentSpeaker(msg);
  return (
    <>
      <span className={`sr-msg__name sr-msg__name--${sp.tone}`}>
        {sp.tone === 'storyteller' ? <Glyph name="crown-thorns" size={14} /> : null}
        {sp.name}
      </span>
      {sp.badge ? (
        <Badge tone={sp.tone === 'ai' ? 'arcane' : sp.tone === 'storyteller' ? 'gold' : 'neutral'} className="sr-msg__badge">
          {sp.badge}
        </Badge>
      ) : null}
      {sp.secondary && !secondaryLast ? <span className="sr-msg__secondary sr-msg__secondary--shown">{sp.secondary}</span> : null}
    </>
  );
}

/** Consecutive messages of one speaker: avatar + header once, compact rows after. */
export function MessageGroup({ group, timeZone, now }) {
  const head = group.messages[0];
  const sp = presentSpeaker(head);
  const longNarration = sp.tone === 'ai' && String(head.content || '').length > 280;
  return (
    <div className={`sr-msg-group sr-msg-group--${sp.tone} sr-msg-group--${group.kind}`}>
      {group.messages.map((m, i) => {
        const ms = messageTime(m);
        const first = i === 0;
        return (
          <div
            key={m.id != null ? m.id : m.client_id}
            id={m.id != null ? `msg-${m.id}` : undefined}
            className={`sr-msg${first ? ' sr-msg--first' : ''}${m.temp ? ' is-pending' : ''}`}
            data-message-id={m.id != null ? m.id : undefined}
          >
            {first ? (
              <>
                <div className="sr-msg__avatar">
                  <SpeakerAvatar msg={m} />
                </div>
                <div className="sr-msg__header">
                  <SpeakerName msg={m} secondaryLast />
                  <Time ms={ms} timeZone={timeZone} now={now} className="sr-msg__time" />
                  {sp.secondary ? <span className="sr-msg__secondary">{sp.secondary}</span> : null}
                </div>
              </>
            ) : (
              <Time ms={ms} timeZone={timeZone} now={now} short={false} className="sr-msg__gutter" />
            )}
            <div className={`sr-msg__body${group.kind === 'action' ? ' sr-msg__body--action' : ''}${first && longNarration ? ' sr-msg__body--dropcap' : ''}`}>
              <Markdown text={m.content} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function diceFaces(marker) {
  const parsed = overlayFromMarker(marker);
  const v5 = parsed.rulesEdition === 'v5';
  const faces = parsed.diceFinal.map((value, i) => {
    const hunger = !!parsed.hungerFlags[i];
    let state;
    if (v5) {
      const c = classifyV5Die(value, hunger).state;
      state = c === 'ten' ? 'crit' : c === 'bestial' ? 'one' : c;
    } else {
      const c = classifyClassicDie(value, parsed.difficulty);
      state = c === 'ten' ? 'crit' : c;
    }
    return { value, hunger, state };
  });
  const badges = v5 ? v5Badges(parsed.result) : [classicOutcome(parsed.result)];
  return { faces, badges, v5, parsed };
}

/** Rolls newer than this still play their landing / effect when the card appears. */
export const FRESH_ROLL_MS = 20000;

/**
 * A roll: dice faces + outcome from the marker, the server's text line below.
 * A fresh roll (just revealed) lands its dice one by one and plays its outcome effect once;
 * history cards are static (a botch / bestial failure keeps a few dried drips).
 */
export function DiceCard({ message, marker, timeZone, now }) {
  const ms = messageTime(message);
  const hidden = String(message.ai_message_kind || '').startsWith('dice_roll_hidden');
  const info = marker ? diceFaces(marker) : null;
  // Decided once when the card mounts, so a re-render never replays the effect.
  const [fresh] = useState(() => !Number.isNaN(ms) && Date.now() - ms < FRESH_ROLL_MS);
  const mood = info ? rollMood(info.parsed.result) : null;
  return (
    <div className="sr-card-row" id={message.id != null ? `msg-${message.id}` : undefined} data-message-id={message.id}>
      <figure className={`sr-dicecard${hidden ? ' sr-dicecard--hidden' : ''}${fresh ? ' is-fresh' : ''}`} data-mood={mood || undefined}>
        <figcaption className="sr-dicecard__head">
          <SpeakerAvatar msg={message} size={24} />
          <SpeakerName msg={message} />
          {hidden ? (
            <Badge tone="neutral" icon="eye-shut">
              {t('dice:hiddenBadge', 'Hidden roll')}
            </Badge>
          ) : null}
          <Time ms={ms} timeZone={timeZone} now={now} className="sr-msg__time" />
        </figcaption>
        {info ? (
          <>
            <div className="sr-dicecard__dice" aria-hidden="true">
              {info.faces.map((f, i) => (
                <span key={i} className="sr-dicecard__die" style={{ '--i': i }} data-state={f.state}>
                  <DieFace value={f.value} hunger={f.hunger} state={f.state} size={34} decorative />
                </span>
              ))}
              {info.parsed.extraDiceCount > 0 ? <span className="sr-dicecard__more">+{info.parsed.extraDiceCount}</span> : null}
            </div>
            <div className="sr-dicecard__outcome">
              {info.badges.map((b) => (
                <Badge key={b.key} tone={BADGE_TONE[b.tone] || 'neutral'} data-testid={`outcome-${b.key}`}>
                  {b.label}
                </Badge>
              ))}
            </div>
          </>
        ) : null}
        <div className="sr-dicecard__text">
          <Markdown text={message.content} />
        </div>
        {info ? <RollFx mood={mood} play={fresh} compact playKey={typeof message.id === 'number' ? message.id : 0} /> : null}
      </figure>
    </div>
  );
}

/** /ai tool output: collapsed, reads as diagnostics, not narration. */
export function DiagnosticCard({ message, timeZone, now }) {
  const ms = messageTime(message);
  const first = String(message.content || '').split('\n').find((l) => l.trim()) || '';
  return (
    <div className="sr-card-row" id={message.id != null ? `msg-${message.id}` : undefined} data-message-id={message.id}>
      <details className="sr-diag">
        <summary>
          <Glyph name="ai-sigil" size={16} />
          <span className="sr-diag__label">{t('chat:diagnostics', 'Storyteller diagnostics')}</span>
          <span className="sr-diag__preview">{first.replace(/[*`#_]/g, '').slice(0, 90)}</span>
          <Time ms={ms} timeZone={timeZone} now={now} className="sr-msg__time" />
        </summary>
        <div className="sr-diag__body">
          <Markdown text={message.content} />
        </div>
      </details>
    </div>
  );
}

/** Room events / moderation notes: one centred line. */
export function SystemLine({ message, timeZone }) {
  const ms = messageTime(message);
  return (
    <div className="sr-card-row sr-sysline" id={message.id != null ? `msg-${message.id}` : undefined} data-message-id={message.id}>
      <Glyph name="raven" size={16} />
      <span className="sr-sysline__text">
        <Markdown text={message.content} />
      </span>
      <Time ms={ms} timeZone={timeZone} short={false} className="sr-msg__time" />
    </div>
  );
}

export function cardFor(row, markers, timeZone, now) {
  const m = row.message;
  if (row.kind === 'dice') return <DiceCard key={row.key} message={m} marker={markers[diceAnimationId(m)]} timeZone={timeZone} now={now} />;
  if (row.kind === 'diagnostic') return <DiagnosticCard key={row.key} message={m} timeZone={timeZone} now={now} />;
  return <SystemLine key={row.key} message={m} timeZone={timeZone} />;
}
