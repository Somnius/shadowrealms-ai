/**
 * Roll requests in Storyteller messages.
 *
 * The backend (services/dice_pools.py apply_roll_tags) rewrites every roll the Storyteller asks
 * for into a canonical tag computed from the requester's sheet, and saves it in the message text:
 *
 *   [[roll: Dexterity + Stealth | 6 dice | difficulty 6]]                                     classic
 *   [[roll: Charisma + Persuasion | specialty Seduction | 8 dice | 2 hunger | difficulty 3]]  V5
 *
 * (a "N hunger" part marks V5; notes such as "impaired (Health)" may follow). /api/ai/chat also
 * returns the same data as `roll_requests`, which the send flow attaches to the saved message; rows
 * loaded later or received live are parsed from the text.
 */
import { t } from '../../i18n';

export const ROLL_TAG_RE = /\[\[roll:\s*([^\]\n]+?)\s*\]\]/g;

/** One canonical tag body → request, or null when it isn't one the backend resolved (no "N dice"). */
export function parseRollTag(body) {
  const parts = String(body || '')
    .split('|')
    .map((s) => s.trim())
    .filter(Boolean);
  if (parts.length < 2) return null;
  const req = { label: parts[0], pool: null, hunger: null, difficulty: null, specialty: null, notes: [] };
  parts.slice(1).forEach((p) => {
    let m;
    if ((m = /^(\d+) dice$/i.exec(p))) req.pool = Number(m[1]);
    else if ((m = /^(\d+) hunger$/i.exec(p))) req.hunger = Number(m[1]);
    else if ((m = /^difficulty (\d+)$/i.exec(p))) req.difficulty = Number(m[1]);
    else if ((m = /^specialty (.+)$/i.exec(p))) req.specialty = m[1];
    else req.notes.push(p);
  });
  if (req.pool === null) return null;
  req.edition = req.hunger === null ? 'classic' : 'v5';
  if (req.hunger === null) req.hunger = 0;
  return req;
}

/** All resolved roll requests in a message text, in order. */
export function parseRollRequests(text) {
  const out = [];
  String(text || '').replace(ROLL_TAG_RE, (all, body) => {
    const r = parseRollTag(body);
    if (r) out.push(r);
    return all;
  });
  return out;
}

/** The text with each tag replaced by its bold label, so the sentence still reads. */
export function stripRollTags(text) {
  return String(text || '').replace(ROLL_TAG_RE, (all, body) => {
    const r = parseRollTag(body);
    return r ? `**${r.label}**` : all;
  });
}

/** Requests of a Storyteller message: the API's structured ones when attached, else the text's. */
export function rollRequestsOf(message) {
  if (!message || message.role !== 'assistant') return [];
  if (Array.isArray(message.roll_requests) && message.roll_requests.length) {
    return message.roll_requests.filter((r) => r && r.label && Number.isFinite(Number(r.pool)));
  }
  return parseRollRequests(message.content);
}

/** "Dexterity + Stealth (6 dice, diff 6)" / "… (5 dice, 2 Hunger, 3 successes needed)", translated. */
export function rollRequestText(req) {
  const label = req.specialty ? t('dice:request.withSpecialty', '{{label}}, {{specialty}} specialty', { label: req.label, specialty: req.specialty }) : req.label;
  const pool = Number(req.pool) || 0;
  let detail;
  if (req.edition === 'v5') {
    const dice = t('dice:request.v5Dice', { one: '{{count}} die, {{hunger}} Hunger', other: '{{count}} dice, {{hunger}} Hunger' }, { count: pool, hunger: Number(req.hunger) || 0 });
    detail =
      req.difficulty != null
        ? t('dice:request.v5', '{{dice}}, {{difficulty}} needed', { dice, difficulty: req.difficulty })
        : dice;
  } else {
    const dice = t('dice:request.classicDice', { one: '{{count}} die', other: '{{count}} dice' }, { count: pool });
    detail = req.difficulty != null ? t('dice:request.classic', '{{dice}}, diff {{difficulty}}', { dice, difficulty: req.difficulty }) : dice;
  }
  return `${label} (${detail})`;
}

/**
 * Roll dialog fields from a request: { pool, difficulty | v5Difficulty, hunger, specialty, reason }.
 * Specialty: V5 already counts its die in the pool; classic only ticks the checkbox (10s reroll).
 */
export function rollPrefill(req) {
  const v5 = req.edition === 'v5';
  const reason = req.specialty ? `${req.label} (${req.specialty})` : req.label;
  return {
    pool: String(Math.max(0, Number(req.pool) || 0)),
    ...(v5
      ? { v5Difficulty: req.difficulty != null ? Number(req.difficulty) : null, hunger: Number(req.hunger) || 0 }
      : { difficulty: req.difficulty != null ? Number(req.difficulty) : 6, specialty: !!req.specialty }),
    reason,
  };
}
