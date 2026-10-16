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
export function phoneEngine(getSettings) {
  return {
    speak(item, done) {
      if (!hasPhoneVoices()) {
        done();
        return;
      }
      const wait = Math.max(0, AFTER_CANCEL_MS - (Date.now() - cancelledAt));
      const start = () => voicesReady().then(() => speakNow(item, done));
      if (wait) setTimeout(start, wait);
      else start();
    },
    cancel() {
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

  function speakNow(item, done) {
    const s = getSettings() || {};
    const u = new window.SpeechSynthesisUtterance(item.text);
    const voice = pickVoice(
      window.speechSynthesis.getVoices(),
      item.lang,
      s.en_accent,
    );
    u.lang =
      item.lang === "el" ? "el-GR" : s.en_accent === "gb" ? "en-GB" : "en-US";
    if (voice) u.voice = voice;
    u.rate = Number(s.rate) || 1;
    u.volume = s.volume == null ? 1 : Number(s.volume);
    u.onend = done;
    u.onerror = done;
    window.speechSynthesis.speak(u);
  }
}
