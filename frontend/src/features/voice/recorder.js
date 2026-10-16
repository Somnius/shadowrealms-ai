/**
 * Recorder helpers (docs/VOICE.md, Phase 3). Pure where possible so the timer colours, the rate
 * control and the filler stripping are testable without a microphone.
 */

export const RATES = [0.75, 1, 1.25, 1.5, 1.75, 2];

/**
 * Timer phase by elapsed seconds against the chronicle's limit (max, default 180 s): gold for the
 * first third, warn for the second, blood for the last, the bright blood in the last 15 s.
 * With 180 s: warn from 1:00, blood from 2:00, bright from 2:45. Class names: sr-rec--<phase>.
 */
export function timerPhase(sec, max = 180) {
  if (sec >= max - 15) return 'bright';
  if (sec >= (2 * max) / 3) return 'blood';
  if (sec >= max / 3) return 'warn';
  return 'gold';
}

/** Pulse every 5 s; every second in the last 15 s. True on the seconds that pulse. */
export function pulsesAt(sec, max = 180) {
  if (sec <= 0) return false;
  return sec >= max - 15 ? true : sec % 5 === 0;
}

export function nextRate(rate) {
  const i = RATES.indexOf(Number(rate));
  return RATES[(i + 1) % RATES.length];
}

export function clock(sec) {
  const s = Math.max(0, Math.floor(Number(sec) || 0));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

/** First container the browser can record: WebM/Opus (Android), MP4/AAC (iOS), Ogg/Opus. */
export function pickMime(MR = typeof MediaRecorder !== 'undefined' ? MediaRecorder : null) {
  if (!MR || typeof MR.isTypeSupported !== 'function') return '';
  return ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus'].find((m) => MR.isTypeSupported(m)) || '';
}

export function canRecord() {
  return typeof navigator !== 'undefined' && !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia) && typeof MediaRecorder !== 'undefined';
}

/** Hesitation sounds Whisper sometimes writes, in English and Greek. */
const FILLERS = /(^|[\s,.;!?])(?:u+h+m*|u+m+|e+r+m*|hmm+|μμ+|εε+|εμ+|αα+)(?=[\s,.;!?]|$)[,.]?/giu;

export function stripFillers(text) {
  return String(text || '')
    .replace(FILLERS, '$1')
    .replace(/\s{2,}/g, ' ')
    .replace(/\s+([,.;!?])/g, '$1')
    .replace(/^[\s,.;]+/, '')
    .trim();
}

/** The language to transcribe in: the player's "I speak", else the app's language. */
export function sttLang(speakLang, uiLang) {
  if (speakLang === 'en' || speakLang === 'el') return speakLang;
  return String(uiLang || '').toLowerCase().startsWith('el') ? 'el' : 'en';
}

export function speechRecognitionCtor() {
  if (typeof window === 'undefined') return null;
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

/**
 * Phone dictation: the phone's own recogniser (audio goes to Apple or Google). Resolves the text
 * when stopped; onPartial(text) while listening. Returns {stop, done}.
 */
export function startPhoneDictation(lang, { onPartial = () => {} } = {}) {
  const Ctor = speechRecognitionCtor();
  if (!Ctor) return null;
  const rec = new Ctor();
  rec.lang = lang === 'el' ? 'el-GR' : 'en-US';
  rec.continuous = true;
  rec.interimResults = true;
  let finalText = '';
  let interim = '';
  const done = new Promise((resolve, reject) => {
    rec.onresult = (e) => {
      interim = '';
      for (let i = e.resultIndex; i < e.results.length; i += 1) {
        const r = e.results[i];
        if (r.isFinal) finalText += `${r[0].transcript} `;
        else interim += r[0].transcript;
      }
      onPartial(`${finalText}${interim}`.trim());
    };
    rec.onerror = (e) => {
      if (e && (e.error === 'no-speech' || e.error === 'aborted')) return;
      reject(new Error((e && e.error) || 'dictation'));
    };
    rec.onend = () => resolve(`${finalText}${interim}`.trim());
  });
  rec.start();
  return { stop: () => rec.stop(), done };
}

/** Phase 6 (transcript check): swap one checked span in the text, e.g. back to Whisper's words.
 * Replaces the first whole occurrence of `from`; the text is returned unchanged when it is gone
 * (the player edited it). */
export function swapSpan(text, from, to) {
  const s = String(text || '');
  if (!from || from === to) return s;
  const at = s.indexOf(from);
  return at < 0 ? s : s.slice(0, at) + to + s.slice(at + from.length);
}

/** The changed spans of a checked transcript: [{ fixed, raw }]. */
export function checkedChanges(segments) {
  return (Array.isArray(segments) ? segments : [])
    .filter((x) => x && typeof x.t === 'string' && typeof x.raw === 'string')
    .map((x) => ({ fixed: x.t, raw: x.raw }));
}
