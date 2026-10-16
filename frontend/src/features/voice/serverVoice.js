/**
 * Server voices (docs/VOICE.md): a line is a job on the speech service; when it is done the
 * audio is fetched with the session (bearer) and played as a blob URL in the room's one
 * <audio playsinline>. Ogg/Opus where the browser plays it, else the AAC (m4a) copy (iOS).
 * If the server is busy or off, the phone's own voice says the line instead (onFallback).
 */
import { API_URL, authFetch, getCurrentToken } from '../../app/http';

export const POLL_MS = 400;
export const MAX_POLLS = 150; // a minute

const wait = (ms) => new Promise((r) => setTimeout(r, ms));

/** One <audio playsinline> element (made once per room by useListen). */
export function makeRoomAudio() {
  if (typeof document === 'undefined') return null;
  const el = document.createElement('audio');
  el.setAttribute('playsinline', '');
  el.preload = 'auto';
  el.style.display = 'none';
  if (document.body) document.body.appendChild(el); // iOS unlocks only an element in the document
  return el;
}

/** A 0.05 s silent WAV, played inside the ear tap so later play() calls are allowed on iOS. */
export const SILENT_CLIP = (() => {
  const n = 400; // 8 kHz, 8-bit mono
  const bytes = [];
  const str = (s) => [...s].forEach((c) => bytes.push(c.charCodeAt(0)));
  const u32 = (v) => bytes.push(v & 255, (v >> 8) & 255, (v >> 16) & 255, (v >> 24) & 255);
  const u16 = (v) => bytes.push(v & 255, (v >> 8) & 255);
  str('RIFF'); u32(36 + n); str('WAVE'); str('fmt '); u32(16); u16(1); u16(1); u32(8000); u32(8000); u16(1); u16(8);
  str('data'); u32(n);
  for (let i = 0; i < n; i += 1) bytes.push(128);
  const b64 = typeof btoa === 'function' ? btoa(String.fromCharCode(...bytes)) : '';
  return `data:audio/wav;base64,${b64}`;
})();

/** Call inside a user gesture: plays the silent clip on the room's element (unlocks it on iOS). */
export function unlockRoomAudio(el) {
  if (!el) return;
  try {
    el.src = SILENT_CLIP;
    const p = el.play();
    if (p && p.catch) p.catch(() => {});
  } catch {
    /* not supported here */
  }
}

export function preferredFormat(el) {
  try {
    return el && el.canPlayType && el.canPlayType('audio/ogg; codecs=opus') ? 'ogg' : 'm4a';
  } catch {
    return 'm4a';
  }
}

/** Waits for a TTS job started by `start` (an api() promise); resolves to the audio key. */
export async function awaitJob(api, start, { pollMs = POLL_MS, maxPolls = MAX_POLLS } = {}) {
  const r = await start;
  if (!r.ok) throw new Error((r.data && r.data.error) || 'speech_failed');
  let job = r.data || {};
  for (let n = 0; job.state !== 'done'; n += 1) {
    if (job.state === 'failed') throw new Error(job.error || 'speech_failed');
    if (n >= maxPolls) throw new Error('timeout');
    await wait(pollMs);
    const s = await api(`/voice/tts/jobs/${job.job_id}`);
    if (!s.ok) throw new Error((s.data && s.data.error) || 'speech_failed');
    job = { ...job, ...s.data };
  }
  return job.key;
}

export async function fetchAudioUrl(key, fmt) {
  const res = await authFetch(`${API_URL}/voice/audio/${encodeURIComponent(key)}?fmt=${fmt}`, {
    headers: { Authorization: `Bearer ${getCurrentToken()}` },
    credentials: 'same-origin',
  });
  if (!res.ok) throw new Error('audio');
  return URL.createObjectURL(await res.blob());
}

/** Plays a blob URL on an element with the player's speed and volume; resolves when it ends. */
export function playOn(el, url, settings) {
  const s = settings || {};
  const rate = Number(s.rate) || 1;
  el.src = url;
  el.defaultPlaybackRate = rate;
  el.playbackRate = rate;
  el.volume = s.volume == null ? 1 : Math.max(0, Math.min(1, Number(s.volume)));
  const p = el.play();
  // WebKit resets the rate when playback starts: set it again once it has
  if (p && p.then) return p.then(() => { el.playbackRate = rate; });
  return p;
}

/** Speak a voice preview (settings and chronicle pages): a fixed sentence in voice `voiceId`. */
export async function previewVoice(api, voiceId, lang) {
  const key = await awaitJob(api, api('/voice/tts/preview', { method: 'POST', body: { voice_id: voiceId, lang } }));
  const el = makeRoomAudio();
  const url = await fetchAudioUrl(key, preferredFormat(el));
  el.onended = () => {
    URL.revokeObjectURL(url);
    if (el.parentNode) el.parentNode.removeChild(el);
  };
  await playOn(el, url, { rate: 1, volume: 1 });
}

/**
 * Engine for createSpeechQueue. getAudio() returns the room's element, getSettings() the
 * player's voice settings, fallback is the phone engine, onFallback(error) tells the player.
 */
export function serverEngine({ api, getAudio, getSettings, fallback, onFallback }) {
  const loads = new Map(); // message id -> Promise<blob url>
  let cancelCurrent = null;

  const load = (item) => {
    if (!loads.has(item.id)) {
      const p = awaitJob(api, api('/voice/tts/jobs', { method: 'POST', body: { message_id: Number(item.id) } })).then((key) =>
        fetchAudioUrl(key, preferredFormat(getAudio())),
      );
      p.catch(() => {});
      loads.set(item.id, p);
    }
    return loads.get(item.id);
  };

  const release = (id) => {
    const p = loads.get(id);
    loads.delete(id);
    if (p) p.then((url) => URL.revokeObjectURL(url)).catch(() => {});
  };

  return {
    prefetch(item) {
      if (item) load(item);
    },
    speak(item, done) {
      let cancelled = false;
      let finished = false;
      const el = getAudio();
      const finish = () => {
        if (finished) return;
        finished = true;
        release(item.id);
        done();
      };
      const viaPhone = (err) => {
        if (cancelled || finished) return;
        if (onFallback) onFallback(err);
        if (fallback) fallback.speak(item, finish);
        else finish();
      };
      cancelCurrent = () => {
        cancelled = true;
        if (el) {
          el.onended = null;
          el.onerror = null;
          el.pause();
        }
      };
      if (!el) {
        viaPhone(new Error('no_audio'));
        return;
      }
      load(item)
        .then((url) => {
          if (cancelled) return;
          el.onended = finish;
          el.onerror = () => viaPhone(new Error('audio'));
          const p = playOn(el, url, getSettings());
          if (p && p.catch) p.catch((e) => viaPhone(e));
        })
        .catch((e) => {
          if (!cancelled) viaPhone(e);
        });
    },
    cancel() {
      if (cancelCurrent) cancelCurrent();
      cancelCurrent = null;
      if (fallback) fallback.cancel();
    },
  };
}

/** Speaks with the server or the phone, as the player's settings say at that moment. */
export function switchingEngine(getSettings, server, phone) {
  const pick = () => ((getSettings() || {}).tts_source === 'server' ? server : phone);
  return {
    speak: (item, done) => pick().speak(item, done),
    prefetch: (item) => {
      const e = pick();
      if (e.prefetch) e.prefetch(item);
    },
    cancel: () => {
      server.cancel();
      phone.cancel();
    },
  };
}
