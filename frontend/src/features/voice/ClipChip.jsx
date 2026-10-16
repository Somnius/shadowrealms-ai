/** Voice message marker and replay chip (docs/VOICE.md §6.3). Everyone in the room sees both. */
import { useEffect, useState } from 'react';
import { Glyph, IconButton } from '../../design';
import { t } from '../../i18n';
import { clock } from './recorder';
import * as player from './clipPlayer';
import './voice.css';

export function isVoiceMessage(m) {
  return !!m && (m.source === 'voice' || m.source === 'phone-voice');
}

/** 14-px mic after the speaker's name (and at the start of later rows), with a spoken name. */
export function VoiceMark({ message }) {
  if (!isVoiceMessage(message)) return null;
  const label = message.source === 'phone-voice'
    ? t('voice:mark.phone', 'Dictated on the phone')
    : t('voice:mark.voice', 'Sent by voice');
  return (
    <span className="sr-msg__voice" role="img" aria-label={label} title={label} data-testid="voice-mark">
      <Glyph name="mic" size={14} />
    </span>
  );
}

function usePlayer() {
  const [s, setS] = useState(player.getState());
  useEffect(() => player.subscribe(setS), []);
  return s;
}

/** One line: play/pause, time, and a separate seek bar (44-px touch box, thin painted bar). */
export function ClipChip({ message, settings }) {
  const s = usePlayer();
  if (!message || !message.clip_id) return null;
  const mine = s.clipId === message.clip_id;
  const total = (mine && s.duration) || (Number(message.clip_ms) || 0) / 1000;
  const time = mine ? s.time : 0;
  const playing = mine && s.playing;
  return (
    <div className="sr-clipchip" data-testid="clip-chip">
      <IconButton
        size="sm"
        icon={playing ? 'pause' : 'play'}
        label={playing ? t('voice:clip.pause', 'Pause the recording') : t('voice:clip.play', 'Play the recording')}
        loading={mine && s.loading}
        onClick={() => player.toggle(message.clip_id, settings)}
      />
      <span className="sr-clipchip__time">{clock(playing || time ? time : total)}</span>
      <label className="sr-seek">
        <span className="sr-visually-hidden">{t('voice:clip.seek', 'Position in the recording')}</span>
        <input
          type="range"
          min="0"
          max={Math.max(1, Math.round(total))}
          step="1"
          value={Math.round(time)}
          disabled={!mine}
          onChange={(e) => player.seek(message.clip_id, Number(e.target.value))}
        />
      </label>
      {mine && s.error ? <span className="sr-clipchip__err">{t('voice:clip.failed', 'Could not play it')}</span> : null}
    </div>
  );
}
