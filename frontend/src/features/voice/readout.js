/**
 * Which chat rows are read out, and the words for each (docs/VOICE.md).
 * `rules` is the effective read-out from GET /campaigns/<cid>/voice-settings:
 * { storyteller, ic, ooc, dice, actions } (the player's override, else the chronicle default).
 */
import { messageKind, presentSpeaker, speakerMode } from '../chat/messageModel';
import { parseRollRequests, ROLL_TAG_RE, parseRollTag } from '../dice/rollRequests';

export const SPOKEN_MAX = 4000; // a whole Storyteller reply, spoken in chunks (0.22)
export const CHUNK_MAX = 220;
export const SHORT = 60;
const DICE_MAX = 200;

/** The kind of read-out rule a message falls under, or null when it is never spoken. */
export function readoutKind(msg) {
  const kind = messageKind(msg);
  if (kind === 'marker' || kind === 'diagnostic' || kind === 'system') return null;
  if (kind === 'ai') return 'storyteller';
  if (kind === 'dice') return 'dice';
  if (kind === 'action') return 'actions';
  const sm = speakerMode(msg);
  if (sm === 'staff') return msg.staff_kind === 'storyteller' ? 'storyteller' : 'ooc';
  if (sm === 'character') return 'ic';
  return 'ooc';
}

export function shouldRead(msg, rules, myUserId) {
  if (!msg || !String(msg.content || '').trim()) return false;
  if (myUserId != null && msg.role !== 'assistant' && String(msg.user_id) === String(myUserId)) return false;
  const kind = readoutKind(msg);
  if (!kind) return false;
  const r = rules || {};
  return r[kind] !== false;
}

/** Markdown and emoji off, whitespace collapsed: what the voice should say. */
export function plainText(text) {
  return String(text || '')
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/!\[[^\]]*\]\([^)]*\)/g, ' ')
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/[*_`~>#|]+/g, '')
    .replace(/\p{Extended_Pictographic}️?/gu, '')
    .replace(/\s+/g, ' ')
    .trim();
}

/** The words spoken for a message: dice as one sentence with the roller's name, else the text. */
export function spokenText(msg) {
  const kind = readoutKind(msg);
  const text = plainText(stripTags(msg && msg.content));
  if (kind === 'dice') {
    const first = plainText(String((msg && msg.content) || '').split('\n')[0]);
    const who = presentSpeaker(msg).name;
    const line = first.toLowerCase().startsWith(String(who).toLowerCase()) ? first : `${who}: ${first}`;
    return line.slice(0, DICE_MAX);
  }
  if (kind === 'ic' || kind === 'ooc') {
    const who = presentSpeaker(msg).name;
    return `${who}: ${text}`.slice(0, SPOKEN_MAX);
  }
  return text.slice(0, SPOKEN_MAX);
}

/** 'el' when the text is mostly Greek letters, else 'en'. */
export function guessLang(text) {
  const s = String(text || '');
  const greek = (s.match(/[Ͱ-Ͽἀ-῿]/g) || []).length;
  const latin = (s.match(/[A-Za-z]/g) || []).length;
  return greek > latin ? 'el' : 'en';
}

// ---------------------------------------------------------------------------------------------
// Read along (0.22): the same rules as backend/services/voice_tts.py (keep the two in step).

/** Each resolved roll tag becomes its bold label; unresolved ones go. */
export function stripTags(text) {
  return String(text || '').replace(ROLL_TAG_RE, (all, body) => {
    const r = parseRollTag(body);
    return r ? `**${r.label}**` : '';
  });
}

export const WORDS = {
  en: {
    roll: 'Roll', plus: 'plus', die: 'die', dice: 'dice', hunger: 'Hunger', difficulty: 'difficulty', specialty: 'specialty',
    success: 'success', successes: 'successes', critical: 'critical win', messy: 'messy critical', bestial: 'bestial failure',
    total: 'total failure', botch: 'botch', win: 'success', fail: 'failure', reroll: 'Willpower reroll',
  },
  el: {
    roll: 'Ρίψη', plus: 'συν', die: 'ζάρι', dice: 'ζάρια', hunger: 'Πείνα', difficulty: 'δυσκολία', specialty: 'ειδίκευση',
    success: 'επιτυχία', successes: 'επιτυχίες', critical: 'κρίσιμη επιτυχία', messy: 'βρώμικη κρίσιμη επιτυχία',
    bestial: 'θηριώδης αποτυχία', total: 'ολική αποτυχία', botch: 'καταστροφική αποτυχία', win: 'επιτυχία', fail: 'αποτυχία',
    reroll: 'νέα ρίψη με Willpower',
  },
};
const words = (lang) => WORDS[lang === 'el' ? 'el' : 'en'];
/** Trait names stay English (game terms, i18n/glossary.jsx); '+' is said in the listener's language. */
const sayLabel = (label, lang) => plainText(label).replace(/\s*\+\s*/g, ` ${words(lang).plus} `).trim();
const diceWord = (n, lang) => `${n} ${n === 1 ? words(lang).die : words(lang).dice}`;

/** "Roll: Intelligence plus Investigation, 7 dice, 1 Hunger, difficulty 2." in `lang`. */
export function rollRequestSentence(req, lang) {
  const w = words(lang);
  const bits = [`${w.roll}: ${sayLabel(req.label, lang)}`];
  if (req.specialty) bits.push(`${w.specialty} ${plainText(req.specialty)}`);
  bits.push(diceWord(Number(req.pool) || 0, lang));
  if (Number(req.hunger)) bits.push(lang === 'el' ? `${w.hunger} ${Number(req.hunger)}` : `${Number(req.hunger)} ${w.hunger}`); // «Πείνα 1», as on screen
  if (req.difficulty != null) bits.push(`${w.difficulty} ${Number(req.difficulty)}`);
  return `${bits.join(', ')}.`;
}

function rollReason(content) {
  const first = String(content || '').split('\n')[0];
  const m = /\bfor \*\*(.+?)\*\*\s*$/.exec(first);
  let reason = m ? m[1].trim() : '';
  const reroll = /\s*\(Willpower reroll\)$/.test(reason);
  reason = reason.replace(/\s*\(Willpower reroll\)$/, '').trim();
  return { reason: reason === 'Dice roll' ? '' : reason, reroll };
}

function outcome(m) {
  const succ = Number(m.successes) || 0;
  if (String(m.rules_edition || '').toLowerCase() === 'v5') {
    if (m.is_messy_critical) return 'messy';
    if (m.is_critical || m.isCritical) return 'critical';
    if (m.is_bestial_failure) return 'bestial';
    if (m.is_total_failure) return 'total';
    const diff = m.difficulty == null || m.difficulty === '' ? 1 : Number(m.difficulty);
    return succ > 0 && succ >= diff ? 'win' : 'fail';
  }
  if (m.is_botch || m.isBotch) return 'botch';
  return succ > 0 ? 'win' : 'fail';
}

/** "Mira: Roll Brawl, 7 dice, 4 successes, critical win." in `lang`, from the roll's marker. */
export function diceSentence(who, content, marker, lang) {
  const w = words(lang);
  const { reason, reroll } = rollReason(content);
  const faces = marker.dice_preview || marker.diceFinal || [];
  const pool = Number(marker.pool_size || marker.poolSize || faces.length) || 0;
  const succ = Number(marker.successes) || 0;
  const bits = [`${who}: ${w.roll}${reason ? ` ${sayLabel(reason, lang)}` : ''}`];
  if (reroll) bits.push(w.reroll);
  bits.push(diceWord(pool, lang));
  bits.push(`${succ} ${succ === 1 ? w.success : w.successes}`);
  bits.push(w[outcome(marker)]);
  return `${bits.join(', ').slice(0, DICE_MAX)}.`;
}

const SPLIT = /([.!?…;·\u037e]+["'”»’)\]]*)\s+|\n+/g;

/** Sentences (Greek and English punctuation, closing quotes kept), short ones joined, long cut. */
export function splitChunks(text, cap = CHUNK_MAX) {
  const s = String(text || '').trim();
  const sents = [];
  let pos = 0;
  let m;
  SPLIT.lastIndex = 0;
  while ((m = SPLIT.exec(s))) {
    const piece = (s.slice(pos, m.index) + (m[1] || '')).trim();
    pos = m.index + m[0].length;
    if (piece) sents.push(piece);
  }
  if (s.slice(pos).trim()) sents.push(s.slice(pos).trim());
  const out = [];
  let cur = '';
  for (let sent of sents) {
    while (sent.length > cap) {
      let cut = sent.lastIndexOf(', ', cap - 1);
      cut = cut > Math.floor(cap / 3) ? cut + 1 : sent.lastIndexOf(' ', cap - 1);
      if (cut <= 0) cut = cap;
      if (cur) {
        out.push(cur);
        cur = '';
      }
      out.push(sent.slice(0, cut).trim());
      sent = sent.slice(cut).trim();
    }
    if (cur && (cur.length >= SHORT || cur.length + 1 + sent.length > cap)) {
      out.push(cur);
      cur = sent;
    } else cur = `${cur} ${sent}`.trim();
  }
  if (cur) out.push(cur);
  return out;
}

/**
 * [{text, lang}] in reading order: the message in chunks in its own language, then each roll the
 * Storyteller asks for, and dice lines, in the listener's language. rollSource: the text the roll
 * tags come from (the original when msg carries a translation).
 */
export function spokenParts(msg, { listenLang = 'en', marker = null, rollSource } = {}) {
  const kind = readoutKind(msg);
  if (!kind) return [];
  const ll = listenLang === 'el' ? 'el' : 'en';
  if (kind === 'dice') {
    if (marker && typeof marker === 'object') return [{ text: diceSentence(presentSpeaker(msg).name, msg.content, marker, ll), lang: ll }];
    const text = spokenText(msg);
    return text ? [{ text, lang: guessLang(text) }] : [];
  }
  const lang = msg.lang || guessLang(String(msg.content || '').replace(ROLL_TAG_RE, ' '));
  const parts = splitChunks(spokenText(msg)).map((text) => ({ text, lang }));
  if (kind === 'storyteller') {
    const src = rollSource === undefined ? msg.content : rollSource;
    parseRollRequests(src).forEach((r) => parts.push({ text: rollRequestSentence(r, ll), lang: ll }));
  }
  return parts;
}
