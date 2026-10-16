/**
 * The read-out queue (docs/VOICE.md): arrival order, at most QUEUE_CAP waiting (older ones are
 * dropped and counted as missed), pause / resume / skip / stop. Engine-agnostic: the engine is
 * { speak(item, onDone), cancel() }; phase 1 uses the phone's own voices (phoneVoice.js).
 */
export const QUEUE_CAP = 20;

export function createSpeechQueue(engine) {
  let items = [];
  let current = null;
  let paused = false;
  let needsResume = false;
  let missed = 0;
  let token = 0;
  const seen = new Set();
  const listeners = new Set();

  const snapshot = () => ({ current, queued: items.length, paused, needsResume, missed });
  const emit = () => listeners.forEach((fn) => fn(snapshot()));

  const next = () => {
    if (paused || current || !items.length) {
      emit();
      return;
    }
    current = items.shift();
    const mine = ++token;
    emit();
    engine.speak(current, () => {
      if (mine !== token) return; // cancelled by skip / stop / pause
      current = null;
      next();
    });
  };

  const interrupt = () => {
    token += 1;
    engine.cancel();
  };

  const pause = () => {
    if (paused) return;
    paused = true;
    if (current) {
      interrupt();
      items.unshift(current); // said again from the start on resume
      current = null;
    }
    emit();
  };

  return {
    enqueue(list) {
      for (const it of list || []) {
        if (!it || seen.has(it.id)) continue;
        seen.add(it.id);
        items.push(it);
      }
      if (items.length > QUEUE_CAP) {
        missed += items.length - QUEUE_CAP;
        items = items.slice(-QUEUE_CAP);
      }
      next();
    },
    /** Ids that must never be read (already on screen when listening started). */
    markSeen(ids) {
      (ids || []).forEach((id) => seen.add(id));
    },
    skip() {
      if (!current) return;
      interrupt();
      current = null;
      next();
    },
    pause,
    /** The page went to the background: pause, and wait for a tap to go on. */
    hide() {
      // Also when idle: lines that arrive while hidden wait for the tap instead of being lost.
      needsResume = true;
      pause();
    },
    resume() {
      paused = false;
      needsResume = false;
      next();
    },
    stop() {
      interrupt();
      items = [];
      current = null;
      paused = false;
      needsResume = false;
      missed = 0;
      emit();
    },
    subscribe(fn) {
      listeners.add(fn);
      fn(snapshot());
      return () => listeners.delete(fn);
    },
    state: snapshot,
  };
}
