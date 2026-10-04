/**
 * Turns a flat message list into the rows the chat renders:
 *   { type: 'day', key, time }                      date separator
 *   { type: 'unread', key }                         "new messages" divider (before firstUnreadId)
 *   { type: 'group', key, kind, speaker, messages } consecutive rows of one speaker
 *   { type: 'card', key, kind, message }            dice / system / diagnostic rows (never grouped)
 *
 * Markers (dice animation transport rows) and rows in `hiddenIds` are dropped.
 */
import { messageKind, messageTime, speakerKey } from './messageModel';

export const GROUP_WINDOW_MS = 5 * 60 * 1000;

const CARD_KINDS = new Set(['dice', 'system', 'diagnostic']);

/** Calendar day key in the given IANA zone (or the browser's zone). */
export function dayKey(ms, timeZone) {
  const d = new Date(ms);
  if (Number.isNaN(d.getTime())) return 'unknown';
  if (!timeZone) {
    return `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`;
  }
  try {
    return new Intl.DateTimeFormat('en-CA', { timeZone, year: 'numeric', month: '2-digit', day: '2-digit' }).format(d);
  } catch (e) {
    return `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`;
  }
}

export function buildTimeline(messages, { firstUnreadId = null, hiddenIds = null, timeZone = null, windowMs = GROUP_WINDOW_MS } = {}) {
  const rows = [];
  let lastDay = null;
  let group = null;
  let unreadPlaced = false;

  for (const msg of messages || []) {
    const kind = messageKind(msg);
    if (kind === 'marker') continue;
    if (hiddenIds && msg.id != null && hiddenIds.has(String(msg.id))) continue;

    const ms = messageTime(msg);
    const day = Number.isNaN(ms) ? lastDay : dayKey(ms, timeZone);
    if (day && day !== lastDay) {
      rows.push({ type: 'day', key: `day-${day}`, time: ms });
      lastDay = day;
      group = null;
    }

    if (!unreadPlaced && firstUnreadId != null && msg.id != null && Number(msg.id) >= Number(firstUnreadId)) {
      rows.push({ type: 'unread', key: 'unread' });
      unreadPlaced = true;
      group = null;
    }

    const msgKey = msg.id != null ? `m-${msg.id}` : `tmp-${msg.client_id || rows.length}`;

    if (CARD_KINDS.has(kind)) {
      rows.push({ type: 'card', key: msgKey, kind, message: msg });
      group = null;
      continue;
    }

    const who = speakerKey(msg);
    const prev = group && group.messages[group.messages.length - 1];
    const prevMs = prev ? messageTime(prev) : NaN;
    const close = prev && !Number.isNaN(ms) && !Number.isNaN(prevMs) && ms - prevMs <= windowMs && ms >= prevMs;
    if (group && group.speaker === who && group.kind === kind && close) {
      group.messages.push(msg);
    } else {
      group = { type: 'group', key: `g-${msgKey}`, kind, speaker: who, messages: [msg] };
      rows.push(group);
    }
  }
  return rows;
}
