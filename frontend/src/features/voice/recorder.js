/**
 * Recorder helpers (docs/VOICE.md, Phase 3). Pure where possible so the timer colours, the rate
 * control and the filler stripping are testable without a microphone.
 */

export const MAX_SECONDS = 180;
export const RATES = [0.75, 1, 1.25, 1.5, 1.75, 2];

/**
 * Timer phase by elapsed seconds: gold until 0:59, warn from 1:00, blood from 2:00, the bright
 * blood from 2:45 to the end. The class names are sr-rec--<phase>.
 */
export function timerPhase(sec) {
  if (sec >= 165) return 'bright';
  if (sec >= 120) return 'blood';
  if (sec >= 60) return 'warn';
  return 'gold';
}

/** Pulse every 5 s; every second in the last 15 s. True on the seconds that pulse. */
export function pulsesAt(sec) {
  if (sec <= 0) return false;
  return sec >= 165 ? true : sec % 5 === 0;
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
