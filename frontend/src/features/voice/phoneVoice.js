/** The phone's (or browser's) own voices through speechSynthesis. Nothing leaves the device. */

export function hasPhoneVoices() {
  return typeof window !== 'undefined' && 'speechSynthesis' in window && typeof window.SpeechSynthesisUtterance === 'function';
}

/** Best voice for a language: el-GR for Greek; en-US / en-GB by the player's accent. */
export function pickVoice(voices, lang, accent = 'us') {
  const list = voices || [];
  const norm = (v) => String(v.lang || '').replace('_', '-').toLowerCase();
  if (lang === 'el') return list.find((v) => norm(v).startsWith('el')) || null;
  const want = accent === 'gb' ? 'en-gb' : 'en-us';
  return list.find((v) => norm(v) === want) || list.find((v) => norm(v).startsWith('en')) || null;
}

/** Call inside the tap that turns listening on: iOS only lets speech start from a user gesture. */
export function unlockPhoneVoice() {
  if (!hasPhoneVoices()) return;
  try {
    const u = new window.SpeechSynthesisUtterance('');
    u.volume = 0;
    window.speechSynthesis.speak(u);
  } catch {
    /* nothing to unlock */
  }
}

/** Engine for createSpeechQueue. settings: { rate, volume, en_accent }. */
export function phoneEngine(getSettings) {
  return {
    speak(item, done) {
      if (!hasPhoneVoices()) {
        done();
        return;
      }
      const s = getSettings() || {};
      const u = new window.SpeechSynthesisUtterance(item.text);
      const voice = pickVoice(window.speechSynthesis.getVoices(), item.lang, s.en_accent);
      u.lang = item.lang === 'el' ? 'el-GR' : s.en_accent === 'gb' ? 'en-GB' : 'en-US';
      if (voice) u.voice = voice;
      u.rate = Number(s.rate) || 1;
      u.volume = s.volume == null ? 1 : Number(s.volume);
      u.onend = done;
      u.onerror = done;
      window.speechSynthesis.speak(u);
    },
    cancel() {
      if (hasPhoneVoices()) window.speechSynthesis.cancel();
    },
  };
}
