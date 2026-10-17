/**
 * Server voices (docs/VOICE.md): a line is a job on the speech service; when it is done the
 * audio is fetched with the session (bearer) and played as a blob URL in the room's one
 * <audio playsinline>. Ogg/Opus where the browser plays it, else the AAC (m4a) copy (iOS).
 * If the server is busy or off, the phone's own voice says the line instead (onFallback).
 */
import { API_URL, authFetch, getCurrentToken } from '../../app/http';

export const POLL_MS = 400;
export const MAX_POLLS = 150; // a minute
export const TRANSLATION_TRIES = 6; // a line in the hear-in language waits up to ~9 s for its translation
export const TRANSLATION_WAIT_MS = 1500;

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
export async function awaitJob(api, start, opts) {
  return (await awaitJobInfo(api, start, opts)).key;
}

/** The same, resolving to the whole job: {key, chunks, chunk, text, original?}. */
export async function awaitJobInfo(api, start, { pollMs = POLL_MS, maxPolls = MAX_POLLS } = {}) {
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
  if (r.usedOriginal) job.original = true;
  return job;
}

/**
 * POST a TTS job for a message. While its translation into the player's hear-in language is not
 * made yet the server answers waiting_translation; after a few tries the original is read instead.
 */
export async function startTtsJob(api, messageId, { tries = TRANSLATION_TRIES, waitMs = TRANSLATION_WAIT_MS, chunk = 0, lang, original = false } = {}) {
  const body = { message_id: messageId, chunk, ...(lang === 'en' || lang === 'el' ? { lang } : {}) };
  const post = (orig) => api('/voice/tts/jobs', { method: 'POST', body: orig ? { ...body, original: true } : body });
  const asOriginal = async () => ({ ...(await post(true)), usedOriginal: true });
  if (original) return asOriginal();
  for (let n = 0; ; n += 1) {
    const r = await post(false);
    if (!r.ok || !r.data || r.data.state !== 'waiting_translation') return r;
    if (n >= tries) return asOriginal();
    await wait(waitMs);
  }
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
 * A line is said chunk by chunk (one job each, read along 0.22): chunk N plays while N+1 and N+2
 * are made, so the first audio of a long Storyteller reply comes after one sentence, not all.
 */
export const AHEAD = 2;

export function serverEngine({ api, getAudio, getSettings, fallback, onFallback }) {
  const loads = new Map(); // "id:chunk" -> Promise<{url, chunks, text}>
  let cancelCurrent = null;

  const load = (item, i) => {
    const k = `${item.id}:${i}`;
    if (!loads.has(k)) {
      // item.startJob(chunk): a line that isn't a message ("Previously on…", 0.27) starts its own job
      const start = item.startJob ? item.startJob(i) : startTtsJob(api, Number(item.id), { chunk: i, lang: item.listenLang, original: !!item.original });
      const p = awaitJobInfo(api, start).then(
        (job) => {
          if (job.original) item.original = true; // the rest of the line in the same language
          return fetchAudioUrl(job.key, preferredFormat(getAudio())).then((url) => ({
            url,
            chunks: Number(job.chunks) || 1,
            text: job.text || '',
          }));
        },
      );
      p.catch(() => {});
      loads.set(k, p);
    }
    return loads.get(k);
  };

  const release = (id) => {
    [...loads.keys()]
      .filter((k) => k.startsWith(`${id}:`))
      .forEach((k) => {
        const p = loads.get(k);
        loads.delete(k);
        p.then((x) => URL.revokeObjectURL(x.url)).catch(() => {});
      });
  };

  return {
    prefetch(item) {
      if (item) load(item, 0);
    },
    speak(item, done, onPart) {
      let cancelled = false;
      let finished = false;
      const el = getAudio();
      let lastText = null; // the chunk last played, to find where the phone goes on from
      const finish = () => {
        if (finished) return;
        finished = true;
        release(item.id);
        done();
      };
      const viaPhone = (err, from = 0) => {
        if (cancelled || finished) return;
        if (onFallback) onFallback(err);
        // the phone goes on from the same chunks the server used (original or translation), after
        // the last chunk heard, so no sentence is skipped or said twice
        const src = (item.original && item.originalParts) || item.parts;
        let start = from;
        if (src && lastText != null) {
          const at = src.findIndex((p) => p.text === lastText);
          if (at >= 0) start = at + 1;
        }
        const rest = src ? { ...item, parts: src.slice(start) } : item;
        if (fallback) fallback.speak(rest, finish, onPart);
        else finish();
      };
      cancelCurrent = () => {
        cancelled = true;
        release(item.id);
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
      const playChunk = (i) =>
        load(item, i)
          .then((c) => {
            if (cancelled) return;
            for (let n = i + 1; n <= i + AHEAD && n < c.chunks; n += 1) load(item, n);
            if (onPart) onPart({ index: i, count: c.chunks, text: c.text });
            el.onended = () => {
              lastText = c.text;
              if (i + 1 < c.chunks) playChunk(i + 1);
              else finish();
            };
            el.onerror = () => viaPhone(new Error('audio'), i);
            const p = playOn(el, c.url, getSettings());
            if (p && p.catch) p.catch((e) => viaPhone(e, i));
          })
          .catch((e) => {
            if (!cancelled) viaPhone(e, i);
          });
      playChunk(0);
    },
    forget(ids) {
      (ids || []).forEach(release);
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
    speak: (item, done, onPart) => pick().speak(item, done, onPart),
    prefetch: (item) => {
      const e = pick();
      if (e.prefetch) e.prefetch(item);
    },
    forget: (ids) => {
      if (server.forget) server.forget(ids);
    },
    cancel: () => {
      server.cancel();
      phone.cancel();
    },
  };
}
