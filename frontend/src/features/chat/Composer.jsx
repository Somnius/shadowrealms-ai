import { useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { DRAFT_PREFIX, readSession, writeSession } from '../../app/hooks';
import { Avatar, Glyph, IconButton } from '../../design';
import MenuButton from '../../app/Menu';
import { completeSlash, parseLocalCommand, slashSuggestions } from './slashCommands';
import { ReplyBar } from './MessageActions';
import { t } from '../../i18n';
import RecorderSheet from '../voice/RecorderSheet';
import { canRecord, isPushToTalkKey } from '../voice/recorder';

const MAX_ROWS = 10;

/** Voice options for the "Speaking as" control. */
export function voiceOptions({ character, user, canStaff }) {
  const out = [];
  if (character) {
    out.push({ id: 'character', label: t('chat:voice.character', '{{name}} (in character)', { name: character.name }), avatar: character.portrait_url, name: character.name, sigil: 'mask' });
  }
  out.push({ id: 'player', label: t('chat:voice.player', '{{name}} (out of character)', { name: user?.username || '' }), avatar: user?.player_avatar_url, name: user?.username, sigil: 'hood' });
  if (canStaff) out.push({ id: 'staff', label: t('chat:voice.staff', 'Storyteller voice'), avatar: null, name: t('chat:voice.staffShort', 'Storyteller'), sigil: 'crown-thorns', glyph: 'crown-thorns' });
  return out;
}

export function placeholderFor(speakAs, { character, roomName }) {
  if (speakAs === 'character' && character) return t('chat:composer.ic', 'Speak as {{name}} in {{room}}…', { name: character.name, room: roomName });
  if (speakAs === 'staff') return t('chat:composer.staff', 'Speak as the Storyteller…');
  return t('chat:composer.ooc', 'Say something out of character in {{room}}…', { room: roomName });
}

function SpeakingAs({ voices, value, onChange }) {
  const current = voices.find((v) => v.id === value) || voices[0];
  if (!current) return null;
  const items = [
    { id: 'caption', render: () => <div className="sr-menu__caption">{t('chat:voice.title', 'Speaking as')}</div> },
    ...voices.map((v) => ({
      id: v.id,
      icon: v.glyph || v.sigil,
      label: v.label,
      checked: v.id === value,
      radio: true, // one voice at a time: a radio group, not checkboxes
      keepFocus: true,
      onSelect: () => onChange(v.id),
    })),
  ];
  return (
    <MenuButton
      label={t('chat:voice.button', 'Speaking as {{name}}. Change voice', { name: current.name })}
      menuLabel={t('chat:voice.title', 'Speaking as')}
      placement="top-start"
      items={items}
      className="sr-composer__voice"
      renderButton={(props, open) => (
        <button {...props} className={`sr-composer__voicebtn${open ? ' is-open' : ''}`}>
          {current.glyph ? (
            <span className="sr-composer__voiceglyph">
              <Glyph name={current.glyph} size={20} />
            </span>
          ) : (
            <Avatar src={current.avatar} name={current.name} size={28} alt="" sigil={current.sigil} />
          )}
          <Glyph name="chevron-up" size={14} />
        </button>
      )}
    />
  );
}

/**
 * Multi-line composer: Enter sends, Shift+Enter is a newline, "/" opens command autocomplete
 * (↑/↓ move, Tab/Enter complete, Esc closes). The voice control sits on the left, dice + send on the right.
 *
 * onSend(text) → Promise<boolean> (false keeps the text so nothing typed is lost).
 * replyTo ({id, author, excerpt}) shows a "Replying to" bar; Esc or its close button calls onCancelReply.
 */
export default function Composer({
  roomName,
  speakAs,
  voices,
  onSpeakAsChange,
  character,
  onSend,
  onRoll,
  busy = false,
  disabled = false,
  isAdmin = false,
  edition = null,
  draftKey,
  inputRef,
  replyTo = null,
  onCancelReply,
  voice = null,
}) {
  // voice: {api, campaignId, locationId, lang, maxSeconds, phoneDictation, canPhoneDictate, onSend}
  const [recording, setRecording] = useState(0); // 0 closed, else a key (Record again remounts)
  const micStream = useRef(null);
  // iOS Safari only grants the mic when getUserMedia runs inside the tap, so ask here and hand
  // the pending stream to the sheet (phone dictation asks on its own).
  const openRecorder = (key) => {
    micStream.current = null;
    if (!voice.phoneDictation && typeof navigator !== 'undefined' && navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
      micStream.current = navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
      micStream.current.catch(() => {}); // the sheet reports the error
    }
    setRecording(key);
  };
  const [micDenied, setMicDenied] = useState(false);
  const [micHint, setMicHint] = useState(false);
  const voiceOn = !!voice && !disabled && (voice.phoneDictation ? voice.canPhoneDictate : canRecord());
  // Desktop push-to-talk: hold Space with focus on the page or the message list to record, release to stop and review.
  const [ptt, setPtt] = useState(false);
  const pttReleased = useRef(false);
  const pttOn = voiceOn && !voice.phoneDictation && !micDenied && !recording;
  useEffect(() => {
    if (!pttOn || typeof window === 'undefined') return undefined;
    const down = (e) => {
      if (!isPushToTalkKey(e)) return;
      e.preventDefault();
      // a quick tap can let go before the sheet listens: note the keyup here too
      pttReleased.current = false;
      const up = (ev) => {
        if (ev.code !== 'Space' && ev.key !== ' ') return;
        pttReleased.current = true;
        window.removeEventListener('keyup', up);
      };
      window.addEventListener('keyup', up);
      setPtt(true);
      openRecorder(1);
    };
    window.addEventListener('keydown', down);
    return () => window.removeEventListener('keydown', down);
  }, [pttOn]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!voiceOn || voice.phoneDictation || typeof navigator === 'undefined' || !navigator.permissions) return undefined;
    let live = true;
    navigator.permissions.query({ name: 'microphone' }).then((p) => {
      if (!live) return;
      setMicDenied(p.state === 'denied');
      p.onchange = () => setMicDenied(p.state === 'denied');
    }).catch(() => {});
    return () => {
      live = false;
    };
  }, [voiceOn, voice && voice.phoneDictation]); // eslint-disable-line react-hooks/exhaustive-deps
  // The unsent draft lives in sessionStorage per user and room, so it survives switching rooms and
  // the remount that a language switch causes (App re-keys the tree on language change).
  const storeKey = draftKey ? `${DRAFT_PREFIX}${draftKey}` : null;
  const [text, setTextState] = useState(() => (storeKey ? readSession(storeKey, '') : ''));
  const [active, setActive] = useState(0);
  const [dismissed, setDismissed] = useState(false);
  const ownRef = useRef(null);
  const ref = inputRef || ownRef;
  const listId = useId();
  const keyRef = useRef(storeKey);
  keyRef.current = storeKey;

  const setText = (value) => {
    setTextState((cur) => {
      const next = typeof value === 'function' ? value(cur) : value;
      if (keyRef.current) writeSession(keyRef.current, next);
      return next;
    });
  };

  // Switching rooms: show that room's draft.
  const prevKey = useRef(storeKey);
  useEffect(() => {
    if (prevKey.current !== storeKey) {
      setTextState(storeKey ? readSession(storeKey, '') : '');
      prevKey.current = storeKey;
    }
  }, [storeKey]);

  const suggestions = useMemo(() => (dismissed ? [] : slashSuggestions(text, { isAdmin, edition })), [text, isAdmin, edition, dismissed]);
  const open = suggestions.length > 0;
  useEffect(() => setActive(0), [text]);

  // Auto-grow 1..MAX_ROWS lines, then scroll.
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = 'auto';
    const lh = parseFloat(window.getComputedStyle(el).lineHeight) || 24;
    const max = lh * MAX_ROWS + 16;
    el.style.height = `${Math.min(el.scrollHeight, max)}px`;
    el.style.overflowY = el.scrollHeight > max ? 'auto' : 'hidden';
  }, [text, ref]);

  const accept = (cmd) => {
    setText(completeSlash(cmd));
    setDismissed(false);
    requestAnimationFrame(() => ref.current && ref.current.focus());
  };

  const send = async () => {
    const value = text;
    if (!value.trim() || busy || disabled) return;
    const local = parseLocalCommand(value);
    if (local && local.type === 'roll') {
      setText('');
      if (onRoll) onRoll();
      return;
    }
    setText('');
    const ok = await onSend(value, local);
    if (ok === false) setText((cur) => (cur ? cur : value));
    requestAnimationFrame(() => ref.current && ref.current.focus());
  };

  const onKeyDown = (e) => {
    if (e.nativeEvent && e.nativeEvent.isComposing) return;
    if (open) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setActive((i) => (i + 1) % suggestions.length);
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setActive((i) => (i - 1 + suggestions.length) % suggestions.length);
        return;
      }
      if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        setDismissed(true);
        return;
      }
      const cmd = suggestions[active];
      if (cmd && (e.key === 'Tab' || (e.key === 'Enter' && !e.shiftKey))) {
        const exact = text.trim().toLowerCase() === cmd.name;
        // Enter on a complete argument-less command ("/roll") sends it; otherwise complete it.
        if (!(e.key === 'Enter' && exact && !cmd.args)) {
          e.preventDefault();
          accept(cmd);
          return;
        }
      }
    }
    if (e.key === 'Escape' && replyTo && onCancelReply) {
      e.preventDefault();
      e.stopPropagation();
      onCancelReply();
      return;
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  const tone = speakAs === 'staff' ? 'staff' : speakAs === 'character' ? 'character' : 'player';

  return (
    <form
      className={`sr-composer sr-composer--${tone}${disabled ? ' is-disabled' : ''}`}
      onSubmit={(e) => {
        e.preventDefault();
        send();
      }}
    >
      {open ? (
        <ul className="sr-slash" role="listbox" id={listId} aria-label={t('chat:slash.label', 'Commands')}>
          {suggestions.map((c, i) => (
            <li
              key={c.name}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === active}
              className={`sr-slash__item${i === active ? ' is-active' : ''}`}
              onMouseDown={(e) => {
                e.preventDefault();
                accept(c);
              }}
              onMouseEnter={() => setActive(i)}
            >
              <span className="sr-slash__name">{c.name}</span>
              {c.args ? <span className="sr-slash__args">{c.args}</span> : null}
              <span className="sr-slash__desc">{c.description()}</span>
              {c.admin ? <span className="sr-slash__tag">{t('chat:slash.admin', 'admin')}</span> : null}
            </li>
          ))}
        </ul>
      ) : null}
      {replyTo ? (
        <ReplyBar
          reply={replyTo}
          onCancel={() => {
            if (onCancelReply) onCancelReply();
            requestAnimationFrame(() => ref.current && ref.current.focus());
          }}
        />
      ) : null}
      {recording ? (
        <RecorderSheet
          key={recording}
          api={voice.api}
          campaignId={voice.campaignId}
          locationId={voice.locationId}
          lang={voice.lang}
          enAccent={voice.enAccent}
          maxSeconds={voice.maxSeconds}
          phoneDictation={voice.phoneDictation}
          canPhoneDictate={voice.canPhoneDictate}
          header={<SpeakingAs voices={voices} value={speakAs} onChange={onSpeakAsChange} />}
          onSend={voice.onSend}
          onClose={() => { setRecording(0); setPtt(false); }}
          onRestart={() => { setPtt(false); openRecorder(recording + 1); }}
          pushToTalk={ptt}
          pushToTalkReleased={pttReleased}
          micStream={micStream.current}
          onMicDenied={() => setMicDenied(true)}
        />
      ) : null}
      {micHint && micDenied ? (
        <p className="sr-composer__michint" role="status">
          {t('voice:rec.denied', 'The microphone is blocked. Allow the microphone for this site in your phone’s Settings, then try again.')}
        </p>
      ) : null}
      <div className="sr-composer__box" hidden={!!recording}>
        <SpeakingAs voices={voices} value={speakAs} onChange={onSpeakAsChange} />
        <label className="sr-visually-hidden" htmlFor={`${listId}-input`}>
          {t('chat:composer.label', 'Message {{room}}', { room: roomName })}
        </label>
        <textarea
          id={`${listId}-input`}
          ref={ref}
          className="sr-composer__input"
          rows={1}
          value={text}
          disabled={disabled}
          placeholder={disabled ? t('chat:composer.closed', 'This room is sealed.') : placeholderFor(speakAs, { character, roomName })}
          onChange={(e) => {
            setText(e.target.value);
            setDismissed(false);
          }}
          onKeyDown={onKeyDown}
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={open}
          aria-controls={open ? listId : undefined}
          aria-activedescendant={open ? `${listId}-${active}` : undefined}
          enterKeyHint="send"
        />
        <div className="sr-composer__tools">
          {voiceOn ? (
            micDenied ? (
              <IconButton
                icon="mic-off"
                label={t('voice:rec.deniedShort', 'Microphone blocked: allow the microphone in Settings')}
                onClick={() => setMicHint((v) => !v)}
                aria-pressed={micHint}
                data-testid="mic-off"
              />
            ) : (
              <IconButton
                icon="mic"
                label={voice.phoneDictation ? t('voice:rec.dictate', 'Dictate a message') : t('voice:rec.record', 'Record a voice message')}
                onClick={() => openRecorder(1)}
                data-testid="mic"
              />
            )
          ) : null}
          {onRoll ? <IconButton icon="d10" label={t('chat:composer.roll', 'Roll dice')} onClick={onRoll} disabled={disabled} /> : null}
          <IconButton
            type="submit"
            icon="send"
            variant="primary"
            label={busy ? t('chat:composer.sending', 'Sending…') : t('chat:composer.send', 'Send')}
            disabled={disabled || !text.trim()}
            loading={busy}
            className="sr-composer__send"
          />
        </div>
      </div>
    </form>
  );
}
