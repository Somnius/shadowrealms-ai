/**
 * Which chat rows are read out, and the words for each (docs/VOICE.md).
 * `rules` is the effective read-out from GET /campaigns/<cid>/voice-settings:
 * { storyteller, ic, ooc, dice, actions } (the player's override, else the chronicle default).
 */
import { messageKind, presentSpeaker, speakerMode } from '../chat/messageModel';

export const SPOKEN_MAX = 600;

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
  const text = plainText(msg && msg.content);
  if (kind === 'dice') {
    const first = plainText(String((msg && msg.content) || '').split('\n')[0]);
    const who = presentSpeaker(msg).name;
    const line = first.toLowerCase().startsWith(String(who).toLowerCase()) ? first : `${who}: ${first}`;
    return line.slice(0, 200);
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
