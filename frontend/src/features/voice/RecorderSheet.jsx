/**
 * Recorder sheet (docs/VOICE.md §6.5): replaces the composer while open. Three steps:
 *   record  timer with colour phases and a pulse every 5 s, auto-stop at the chronicle's limit
 *   review  play it back, seek, one speed control; nothing leaves the phone until Transcribe
 *   text    the transcript to fix; Send is its own tap and goes through the normal send (OOC checks)
 * With phone dictation the phone's recogniser writes the text while you speak (no recording kept).
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { Button, Glyph, IconButton } from '../../design';
import { API_URL, authFetch, getCurrentToken } from '../../app/http';
import { t } from '../../i18n';
import { clock, nextRate, pickMime, pulsesAt, startPhoneDictation, stripFillers, timerPhase } from './recorder';
import './voice.css';

const POLL_MS = 700;
const MAX_POLLS = 400;
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

export function sttErrorText(code) {
  if (code === 'gpu_busy' || code === 'queue_full') {
    return t('voice:rec.busy', 'The server’s speech engine is busy. Type what you said, or use phone dictation.');
  }
  if (code === 'too_large' || code === 'too_long') return t('voice:rec.tooLong', 'The recording is too long for the server.');
  if (code === 'clips_disk_full') return t('voice:rec.diskFull', 'The server has no room for more recordings. Tell the site admin.');
  if (code === 'speech_unavailable') return t('voice:rec.down', 'The speech service is not running. Type what you said, or use phone dictation.');
  return t('voice:rec.failed', 'Transcription failed. Type what you said, or record again.');
}

async function uploadClip({ blob, campaignId, locationId, lang }) {
  const fd = new FormData();
  const ext = blob.type.includes('mp4') ? 'm4a' : blob.type.includes('ogg') ? 'ogg' : 'webm';
  fd.append('audio', blob, `clip.${ext}`);
  fd.append('campaign_id', String(campaignId));
  fd.append('location_id', String(locationId));
  fd.append('lang', lang);
  let res;
  try {
    res = await authFetch(`${API_URL}/voice/clips`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${getCurrentToken()}` },
      body: fd,
      credentials: 'same-origin',
    });
  } catch {
    return { ok: false, data: { error: 'speech_unavailable' } };
  }
  let data = {};
  try {
    data = await res.json();
  } catch {
    data = { error: res.status === 413 ? 'too_large' : 'speech_failed' };
  }
  return { ok: res.ok, data };
}

export default function RecorderSheet({
  api,
  campaignId,
  locationId,
  lang,
  enAccent = 'us',
  maxSeconds = 180,
  phoneDictation = false,
  canPhoneDictate = false,
  header = null,
  onSend,
  onClose,
  onMicDenied,
  onRestart,
  micStream = null,
  pushToTalk = false,
}) {
  // The language you speak in this recording: it tells the transcriber which language to expect.
  // Remembered on this device; first time it follows your voice settings / interface language.
  const [spoken, setSpokenState] = useState(() => {
    try {
      const v = window.localStorage.getItem('sr.voice.spokenLang');
      if (v === 'el' || v === 'en') return v;
    } catch {
      /* no storage */
    }
    return lang === 'el' ? 'el' : 'en';
  });
  const setSpoken = (v) => {
    setSpokenState(v);
    try {
      window.localStorage.setItem('sr.voice.spokenLang', v);
    } catch {
      /* no storage */
    }
  };
  const [step, setStep] = useState('record');
  const [elapsed, setElapsed] = useState(0);
  const [pulse, setPulse] = useState(false);
  const [blobUrl, setBlobUrl] = useState(null);
  const [text, setText] = useState('');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState('');
  const [clipId, setClipId] = useState(null);
  const [source, setSource] = useState(phoneDictation ? 'phone-voice' : 'voice');
  const [playing, setPlaying] = useState(false);
  const [pos, setPos] = useState(0);
  const [dur, setDur] = useState(0);
  const [rate, setRate] = useState(1);
  const rec = useRef(null);
  const stream = useRef(null);
  const chunks = useRef([]);
  const blob = useRef(null);
  const dictation = useRef(null);
  const clockRef = useRef({ start: 0, pausedAt: 0, pausedFor: 0 });
  const audioEl = useRef(null);
  const lastPulse = useRef(0);
  const released = useRef(false);

  // push-to-talk (desktop Space): letting go of Space stops the recording
  useEffect(() => {
    if (!pushToTalk || typeof window === 'undefined') return undefined;
    const up = (e) => {
      if (e.code !== 'Space' && e.key !== ' ') return;
      e.preventDefault();
      released.current = true;
      if (rec.current && rec.current.state !== 'inactive') rec.current.stop();
    };
    window.addEventListener('keyup', up);
    return () => window.removeEventListener('keyup', up);
  }, [pushToTalk]);

  const stopTracks = () => {
    if (stream.current) stream.current.getTracks().forEach((tr) => tr.stop());
    stream.current = null;
  };

  const stop = useCallback(() => {
    if (dictation.current) {
      dictation.current.stop();
      return;
    }
    if (rec.current && rec.current.state !== 'inactive') rec.current.stop();
  }, []);

  // ---- step 1: start recording (or dictating) as soon as the sheet opens (the mic tap) ----
  useEffect(() => {
    let live = true;
    clockRef.current = { start: Date.now(), pausedAt: 0, pausedFor: 0 };
    if (phoneDictation) {
      try {
        const d = startPhoneDictation(spoken, { onPartial: (p) => live && setText(p) });
        if (!d) throw new Error('none');
        dictation.current = d;
        d.done
          .then((final) => {
            if (!live) return;
            setText(stripFillers(final));
            setStep('text');
          })
          .catch(() => {
            if (!live) return;
            setSource(null); // typed after all: a normal line
            setNote(t('voice:rec.dictationFailed', 'Phone dictation stopped. Type what you said.'));
            setStep('text');
          });
      } catch {
        setSource(null);
        setNote(t('voice:rec.noDictation', 'This phone has no dictation here. Type what you said.'));
        setStep('text');
      }
      return () => {
        live = false;
        if (dictation.current) dictation.current.stop();
      };
    }
    (async () => {
      let s;
      try {
        // micStream comes from the mic tap itself (iOS wants getUserMedia inside the user gesture)
        s = await (micStream || navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } }));
      } catch (e) {
        if (!live) return;
        if (e && (e.name === 'NotAllowedError' || e.name === 'SecurityError')) onMicDenied && onMicDenied();
        onClose();
        return;
      }
      if (!live) {
        s.getTracks().forEach((tr) => tr.stop());
        return;
      }
      stream.current = s;
      const mime = pickMime();
      let r;
      try {
        r = new MediaRecorder(s, { ...(mime ? { mimeType: mime } : {}), audioBitsPerSecond: 32000 });
        chunks.current = [];
        r.ondataavailable = (e) => e.data && e.data.size && chunks.current.push(e.data);
        r.onstop = () => {
          stopTracks();
          if (!live) return;
          blob.current = new Blob(chunks.current, { type: r.mimeType || mime || 'audio/webm' });
          setBlobUrl(URL.createObjectURL(blob.current));
          setStep('review');
        };
        rec.current = r;
        clockRef.current = { start: Date.now(), pausedAt: 0, pausedFor: 0 };
        r.start(1000);
        if (released.current) r.stop(); // Space let go before the mic was ready
      } catch {
        rec.current = null;
        stopTracks();
        onClose();
      }
    })();
    return () => {
      live = false;
      if (rec.current && rec.current.state !== 'inactive') rec.current.stop();
      stopTracks();
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // the timer, the pulse (a class toggle, so reduced motion can keep the colour only) and the limit
  useEffect(() => {
    if (step !== 'record') return undefined;
    const id = setInterval(() => {
      const c = clockRef.current;
      if (c.pausedAt) return;
      const sec = Math.floor((Date.now() - c.start - c.pausedFor) / 1000);
      setElapsed(sec);
      if (pulsesAt(sec, maxSeconds) && lastPulse.current !== sec) {
        lastPulse.current = sec;
        setPulse(true);
        setTimeout(() => setPulse(false), 300);
      }
      if (sec >= maxSeconds) stop();
    }, 250);
    return () => clearInterval(id);
  }, [step, maxSeconds, stop]);

  // backgrounding: the phone may kill the mic (and iOS cannot pause a MediaRecorder), so stop
  // and go to review with what was recorded so far
  useEffect(() => {
    if (step !== 'record' || phoneDictation) return undefined;
    const onVis = () => {
      if (document.visibilityState === 'hidden' && rec.current && rec.current.state !== 'inactive') {
        try {
          rec.current.stop();
        } catch {
          stopTracks();
        }
      }
    };
    document.addEventListener('visibilitychange', onVis);
    return () => document.removeEventListener('visibilitychange', onVis);
  }, [step, phoneDictation]);

  useEffect(() => () => blobUrl && URL.revokeObjectURL(blobUrl), [blobUrl]);

  // ---- step 2: review ----
  const togglePlay = () => {
    const a = audioEl.current;
    if (!a) return;
    if (a.paused) {
      a.playbackRate = rate;
      a.preservesPitch = true;
      a.play().catch(() => setPlaying(false));
    } else a.pause();
  };
  const changeRate = () => {
    const r = nextRate(rate);
    setRate(r);
    if (audioEl.current) {
      audioEl.current.playbackRate = r;
      // older iOS ignores some rates: show what the element really uses
      if (audioEl.current.playbackRate !== r) setRate(audioEl.current.playbackRate || 1);
    }
  };

  const transcribe = async () => {
    if (!blob.current) return;
    if (audioEl.current) audioEl.current.pause();
    if (clipId) {
      setStep('text'); // already sent up and transcribed: back to the text
      return;
    }
    setNote('');
    setBusy(t('voice:rec.uploading', 'Sending the recording…'));
    const up = await uploadClip({ blob: blob.current, campaignId, locationId, lang: spoken });
    if (!up.ok || !up.data.clip_id) {
      setBusy('');
      setNote(sttErrorText(up.data && up.data.error));
      return;
    }
    setClipId(up.data.clip_id);
    setSource('voice');
    let job = up.data;
    for (let n = 0; job.state !== 'done' && job.state !== 'failed' && n < MAX_POLLS; n += 1) {
      setBusy(job.position ? t('voice:rec.position', 'Transcribing… {{count}} ahead of you', { count: job.position }) : t('voice:rec.transcribing', 'Transcribing…'));
      await wait(POLL_MS);
      const r = await api(`/voice/stt/jobs/${job.job_id}`);
      if (!r.ok) {
        job = { state: 'failed', error: 'speech_failed' };
        break;
      }
      job = { ...job, ...r.data };
    }
    setBusy('');
    if (job.state === 'done') {
      setText(stripFillers(job.text));
      if (!String(job.text || '').trim()) setNote(t('voice:rec.empty', 'No words were heard. Type what you said, or record again.'));
    } else setNote(sttErrorText(job.error || 'timeout'));
    setStep('text');
  };

  const dictateInstead = () => {
    const d = startPhoneDictation(spoken, { onPartial: setText });
    if (!d) return;
    dictation.current = d;
    setBusy(t('voice:rec.dictating', 'Listening… tap Stop when you are done.'));
    d.done
      .then((final) => setText(stripFillers(final)))
      .catch(() => setNote(t('voice:rec.dictationFailed', 'Phone dictation stopped. Type what you said.')))
      .finally(() => {
        dictation.current = null;
        setBusy('');
      });
  };

  // ---- step 3: send ----
  const send = async () => {
    if (!text.trim()) return;
    setBusy(t('voice:rec.sending', 'Sending…'));
    const ok = await onSend({ text: text.trim(), clipId, source: clipId ? 'voice' : source === 'phone-voice' ? 'phone-voice' : null });
    setBusy('');
    if (ok !== false) onClose();
  };

  const phase = timerPhase(elapsed, maxSeconds);
  const left = Math.max(0, maxSeconds - elapsed);
  const langLabel = spoken === 'el' ? 'Ελληνικά' : 'English';

  return (
    <section className="sr-recsheet" aria-label={t('voice:rec.title', 'Voice message')} data-testid="recorder-sheet">
      <div className="sr-recsheet__head">
        <IconButton icon="close" label={t('voice:rec.cancel', 'Cancel the voice message')} onClick={onClose} />
        <span className="sr-recsheet__title">
          {step === 'record' ? (phoneDictation ? t('voice:rec.dictateTitle', 'Dictating') : t('voice:rec.recording', 'Recording'))
            : step === 'review' ? t('voice:rec.review', 'Your recording · {{time}}', { time: clock(dur || elapsed) })
              : t('voice:rec.text', 'What you said')}
        </span>
        {step !== 'text' ? (
          <div className="sr-rec-lang" role="group" aria-label={t('voice:rec.spokenLang', 'Language you speak')}>
            {[['el', '🇬🇷', 'Ελληνικά'], ['en', enAccent === 'gb' ? '🇬🇧' : '🇺🇸', 'English']].map(([v, short, full]) => (
              <button
                key={v}
                type="button"
                className="sr-rec-lang__btn"
                aria-pressed={spoken === v}
                aria-label={full}
                title={full}
                onClick={() => setSpoken(v)}
                data-testid={`spoken-${v}`}
              >
                {short}
              </button>
            ))}
          </div>
        ) : null}
        {header}
      </div>

      {step === 'record' ? (
        <div className={`sr-rec sr-rec--${phase}${pulse ? ' is-pulse' : ''}`} data-phase={phase}>
          <span className="sr-rec__ring" aria-hidden="true">
            <Glyph name="mic" size={24} />
          </span>
          <span className="sr-rec__timer" role="timer" aria-label={t('voice:rec.left', '{{time}} left', { time: clock(left) })}>
            {clock(elapsed)}
          </span>
          <span className="sr-rec__bar" aria-hidden="true">
            <span style={{ width: `${Math.min(100, (elapsed / maxSeconds) * 100)}%` }} />
          </span>
          {phoneDictation && text ? <p className="sr-rec__partial">{text}</p> : null}
          <div className="sr-recsheet__row">
            <Button type="button" variant="ghost" onClick={onClose}>{t('voice:rec.cancelShort', 'Cancel')}</Button>
            <IconButton size="lg" icon="stop" variant="primary" label={t('voice:rec.stop', 'Stop')} onClick={stop} />
          </div>
        </div>
      ) : null}

      {step === 'review' ? (
        <div className="sr-rec-review">
          <audio
            ref={(el) => {
              audioEl.current = el;
              if (el) el.setAttribute('playsinline', ''); // iOS: play in the page, not fullscreen
            }}
            src={blobUrl || undefined}
            preload="auto"
            onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)}
            onEnded={() => setPlaying(false)}
            onTimeUpdate={(e) => setPos(e.currentTarget.currentTime)}
            onLoadedMetadata={(e) => Number.isFinite(e.currentTarget.duration) && setDur(e.currentTarget.duration)}
          />
          <div className="sr-rec-review__player">
            <IconButton icon={playing ? 'pause' : 'play'} label={playing ? t('voice:clip.pause', 'Pause the recording') : t('voice:clip.play', 'Play the recording')} onClick={togglePlay} />
            <span className="sr-clipchip__time">{clock(pos)}</span>
            <label className="sr-seek sr-seek--wide">
              <span className="sr-visually-hidden">{t('voice:clip.seek', 'Position in the recording')}</span>
              <input
                type="range"
                min="0"
                max={Math.max(1, Math.round(dur || elapsed))}
                step="1"
                value={Math.round(pos)}
                onChange={(e) => {
                  if (audioEl.current) audioEl.current.currentTime = Number(e.target.value);
                  setPos(Number(e.target.value));
                }}
              />
            </label>
            <button type="button" className="sr-rec-rate" onClick={changeRate} aria-label={t('voice:rec.rate', 'Playback speed {{rate}}×. Tap to change', { rate })} data-testid="rate">
              {rate}×
            </button>
          </div>
          {note ? <p className="sr-rec__note" role="alert">{note}</p> : null}
          {busy ? <p className="sr-rec__note" role="status">{busy}</p> : null}
          <div className="sr-recsheet__row">
            <Button type="button" variant="ghost" disabled={!!busy} onClick={onClose}>{t('voice:rec.discard', 'Discard')}</Button>
            {onRestart && !clipId ? <Button type="button" variant="secondary" disabled={!!busy} onClick={onRestart}>{t('voice:rec.again', 'Record again')}</Button> : null}
            <Button type="button" variant="primary" loading={!!busy} onClick={transcribe}>{t('voice:rec.transcribe', 'Transcribe')}</Button>
          </div>
        </div>
      ) : null}

      {step === 'text' ? (
        <div className="sr-rec-text">
          <span className="sr-rec-text__lang">{langLabel}</span>
          <label className="sr-visually-hidden" htmlFor="sr-rec-text">{t('voice:rec.text', 'What you said')}</label>
          <textarea id="sr-rec-text" className="sr-rec-text__input" rows={4} value={text} onChange={(e) => setText(e.target.value)} />
          {note ? <p className="sr-rec__note" role="alert">{note}</p> : null}
          {busy ? <p className="sr-rec__note" role="status">{busy}</p> : null}
          {canPhoneDictate && !dictation.current && source !== 'phone-voice' && note ? (
            <Button type="button" variant="secondary" size="sm" onClick={dictateInstead}>
              <Glyph name="mic" size={16} /> {t('voice:rec.dictateInstead', 'Use phone dictation')}
            </Button>
          ) : null}
          {dictation.current ? (
            <Button type="button" variant="secondary" size="sm" onClick={() => dictation.current && dictation.current.stop()}>{t('voice:rec.stop', 'Stop')}</Button>
          ) : null}
          <div className="sr-recsheet__row">
            {blobUrl ? <Button type="button" variant="ghost" disabled={!!busy} onClick={() => setStep('review')}>{t('voice:rec.back', 'Back')}</Button> : null}
            <Button type="button" variant="ghost" disabled={!!busy} onClick={onClose}>{t('voice:rec.discard', 'Discard')}</Button>
            <Button type="button" variant="primary" disabled={!text.trim() || !!busy} onClick={send} className="sr-recsheet__send">
              {t('voice:rec.send', 'Send')}
            </Button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
