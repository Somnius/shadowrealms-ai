/**
 * The read-out queue (docs/VOICE.md): arrival order, at most QUEUE_CAP waiting (older ones are
 * dropped and counted as missed), pause / resume / skip / stop. Engine-agnostic: the engine is
 * { speak(item, onDone, onPart?), cancel(), prefetch?(item) }: the phone's own voices (phoneVoice.js) or
 * server voices (serverVoice.js), which start the next line's audio while this one plays. An
 * engine says a line chunk by chunk and calls onPart({index, count, text}) as each one starts
 * (read along, 0.22); `part` in the state is the chunk being said.
 */
export const QUEUE_CAP = 20;

export function createSpeechQueue(engine, { onDone } = {}) {
  let items = [];
  let current = null;
  let paused = false;
  let needsResume = false;
  let missed = 0;
  let token = 0;
  let part = null;
  const seen = new Set();
  const listeners = new Set();

  const snapshot = () => ({ current, part, queued: items.length, paused, needsResume, missed });
  const emit = () => listeners.forEach((fn) => fn(snapshot()));

  const next = () => {
    if (paused || current || !items.length) {
      emit();
      return;
    }
    current = items.shift();
    part = null;
    const mine = ++token;
    emit();
    prefetchNext();
    const said = current;
    engine.speak(
      current,
      () => {
        if (mine !== token) return; // cancelled by skip / stop / pause
        current = null;
        part = null;
        if (onDone) onDone(said);
        next();
      },
      (p) => {
        if (mine !== token) return;
        part = p;
        emit();
      },
    );
  };

  function prefetchNext() {
    if (current && items.length && engine.prefetch) engine.prefetch(items[0]);
  }

  // lines thrown away by stop / play: the engine drops anything it fetched ahead for them
  const forget = (list) => {
    if (engine.forget && list.length) engine.forget(list.map((it) => it.id));
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
      part = null;
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
      if (current) prefetchNext();
      next();
    },
    /** "Read this" / "Read from here": stop what is said and read these now, even if read before. */
    play(list) {
      interrupt();
      forget(items);
      current = null;
      part = null;
      paused = false;
      needsResume = false;
      items = [];
      for (const it of list || []) {
        if (!it) continue;
        seen.add(it.id);
        items.push(it);
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
      part = null;
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
      forget(items);
      items = [];
      current = null;
      part = null;
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
