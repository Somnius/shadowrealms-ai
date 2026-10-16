/** The phone's (or browser's) own voices through speechSynthesis. Nothing leaves the device. */

export function hasPhoneVoices() {
  return (
    typeof window !== "undefined" &&
    "speechSynthesis" in window &&
    typeof window.SpeechSynthesisUtterance === "function"
  );
}

/** Best voice for a language: el-GR for Greek; en-US / en-GB by the player's accent. */
export function pickVoice(voices, lang, accent = "us") {
  const list = voices || [];
  const norm = (v) =>
    String(v.lang || "")
      .replace("_", "-")
      .toLowerCase();
  if (lang === "el") return list.find((v) => norm(v).startsWith("el")) || null;
  const want = accent === "gb" ? "en-gb" : "en-us";
  return (
    list.find((v) => norm(v) === want) ||
    list.find((v) => norm(v).startsWith("en")) ||
    null
  );
}

/** Call inside the tap that turns listening on: iOS only lets speech start from a user gesture. */
export function unlockPhoneVoice() {
  if (!hasPhoneVoices()) return;
  try {
    const u = new window.SpeechSynthesisUtterance("");
    u.volume = 0;
    window.speechSynthesis.speak(u);
  } catch {
    /* nothing to unlock */
  }
}

// After cancel() iOS Safari and Chrome drop an utterance queued in the same turn and may never
// fire its onend, so the next one starts a moment later, after a resume().
const AFTER_CANCEL_MS = 80;
let cancelledAt = 0;

/** The voice list often arrives late (voiceschanged); returns a promise of a non-empty list. */
function voicesReady(timeoutMs = 1500) {
  const synth = window.speechSynthesis;
  const now = synth.getVoices();
  if (now.length || typeof synth.addEventListener !== "function")
    return Promise.resolve(now);
  return new Promise((resolve) => {
    const finish = () => {
      synth.removeEventListener("voiceschanged", finish);
      resolve(synth.getVoices());
    };
    synth.addEventListener("voiceschanged", finish);
    setTimeout(finish, timeoutMs);
  });
}

/** Engine for createSpeechQueue. settings: { rate, volume, en_accent }. */
// A browser with no speech engine (e.g. Firefox on Linux without speech-dispatcher) has an empty
// voice list and never starts or ends an utterance. Then the line goes to `fallback` (the server
// voices) instead of waiting forever.
const START_TIMEOUT_MS = 4000;

/** The chunks of a queue item: item.parts (read along, 0.22), else the whole text. */
export const partsOf = (item) =>
  (item.parts && item.parts.length ? item.parts : [{ text: item.text, lang: item.lang }]).filter((p) => p && p.text);

export function phoneEngine(getSettings, getFallback = () => null) {
  let gen = 0; // bumped by cancel(): a cancelled line never goes on to its next chunk
  const toFallback = (item, done, onPart) => {
    const fb = getFallback();
    if (fb) fb.speak(item, done, onPart);
    else done();
  };
  return {
    speak(item, done, onPart) {
      if (!hasPhoneVoices()) {
        toFallback(item, done, onPart);
        return;
      }
      const mine = gen;
      const parts = partsOf(item);
      const sayPart = (i) => {
        if (mine !== gen) return;
        if (i >= parts.length) {
          done();
          return;
        }
        if (onPart) onPart({ index: i, count: parts.length, text: parts[i].text });
        speakNow(parts[i], () => sayPart(i + 1), () => toFallback({ ...item, parts: parts.slice(i) }, done, onPart));
      };
      const wait = Math.max(0, AFTER_CANCEL_MS - (Date.now() - cancelledAt));
      const start = () =>
        voicesReady().then((voices) => {
          if (mine !== gen) return;
          if (!voices || !voices.length) toFallback(item, done, onPart);
          else sayPart(0);
        });
      if (wait) setTimeout(start, wait);
      else start();
    },
    cancel() {
      gen += 1;
      if (!hasPhoneVoices()) return;
      window.speechSynthesis.cancel();
      cancelledAt = Date.now();
      try {
        window.speechSynthesis.resume();
      } catch {
        /* not paused */
      }
    },
  };

  function speakNow(part, next, fallback) {
    const s = getSettings() || {};
    const u = new window.SpeechSynthesisUtterance(part.text);
    const voice = pickVoice(
      window.speechSynthesis.getVoices(),
      part.lang,
      s.en_accent,
    );
    u.lang =
      part.lang === "el" ? "el-GR" : s.en_accent === "gb" ? "en-GB" : "en-US";
    if (voice) u.voice = voice;
    u.rate = Number(s.rate) || 1;
    u.volume = s.volume == null ? 1 : Number(s.volume);
    let started = false;
    let finished = false;
    const finish = () => {
      if (finished) return;
      finished = true;
      next();
    };
    u.onstart = () => {
      started = true;
    };
    u.onend = finish;
    u.onerror = finish;
    window.speechSynthesis.speak(u);
    setTimeout(() => {
      if (started || finished) return;
      finished = true;
      window.speechSynthesis.cancel();
      fallback();
    }, START_TIMEOUT_MS);
  }
}
