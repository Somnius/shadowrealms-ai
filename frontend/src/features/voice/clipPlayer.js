/**
 * Voice-message replay (docs/VOICE.md): one <audio playsinline> for the room, so one clip plays at
 * a time and tapping another chip switches. Audio is fetched with the session as a blob URL;
 * Ogg/Opus where the browser plays it, else the AAC copy (iOS Safari).
 */
import { API_URL, authFetch, getCurrentToken } from '../../app/http';
import { makeRoomAudio, preferredFormat } from './serverVoice';

let el = null;
const urls = new Map(); // clip id -> blob url
let state = { clipId: null, playing: false, loading: false, time: 0, duration: 0, error: null };
const subs = new Set();

function set(patch) {
  state = { ...state, ...patch };
  subs.forEach((f) => f(state));
}

export function subscribe(fn) {
  subs.add(fn);
  return () => subs.delete(fn);
}

export const getState = () => state;

function audio() {
  if (el) return el;
  el = makeRoomAudio();
  if (!el) return null;
  el.addEventListener('timeupdate', () => set({ time: el.currentTime }));
  el.addEventListener('durationchange', () => Number.isFinite(el.duration) && set({ duration: el.duration }));
  el.addEventListener('play', () => set({ playing: true }));
  el.addEventListener('pause', () => set({ playing: false }));
  el.addEventListener('ended', () => set({ playing: false, time: 0 }));
  return el;
}

async function clipUrl(clipId, fmt) {
  if (urls.has(clipId)) return urls.get(clipId);
  const res = await authFetch(`${API_URL}/voice/clips/${encodeURIComponent(clipId)}/audio?fmt=${fmt}`, {
    headers: { Authorization: `Bearer ${getCurrentToken()}` },
    credentials: 'same-origin',
  });
  if (!res.ok) throw new Error('audio');
  const url = URL.createObjectURL(await res.blob());
  urls.set(clipId, url);
  return url;
}

let defaults = { rate: 1, volume: 1 };
/** The player's listening speed and volume (voice settings), used when a chip passes none. */
export function setDefaults({ rate = 1, volume = 1 } = {}) {
  defaults = { rate, volume };
}

/** Play or pause this clip (a tap: the user gesture iOS needs). */
export async function toggle(clipId, opts) {
  const { rate = 1, volume = 1 } = opts || defaults;
  const a = audio();
  if (!a) return;
  if (state.clipId === clipId && state.playing) {
    a.pause();
    return;
  }
  if (state.clipId !== clipId) {
    a.pause();
    set({ clipId, time: 0, duration: 0, loading: true, error: null });
    try {
      a.src = await clipUrl(clipId, preferredFormat(a));
    } catch {
      set({ loading: false, error: 'audio' });
      return;
    }
  }
  a.playbackRate = Number(rate) || 1;
  a.volume = Math.max(0, Math.min(1, Number(volume)));
  set({ loading: false });
  try {
    await a.play();
  } catch {
    set({ playing: false, error: 'play' });
  }
}

/** Jump to a point (seconds) of the clip that is loaded. */
export function seek(clipId, sec) {
  if (!el || state.clipId !== clipId) return;
  el.currentTime = Math.max(0, Number(sec) || 0);
  set({ time: el.currentTime });
}

/** Leaving the room: stop and free the blobs. */
export function reset() {
  if (el) el.pause();
  urls.forEach((u) => {
    try {
      URL.revokeObjectURL(u);
    } catch {
      /* ignore */
    }
  });
  urls.clear();
  set({ clipId: null, playing: false, loading: false, time: 0, duration: 0, error: null });
}
