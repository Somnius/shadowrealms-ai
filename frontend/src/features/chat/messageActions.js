/**
 * Chat message actions (v0.10 phase 3): copy, reply, delete. Pure helpers, no React.
 *
 * Who may delete mirrors backend services/message_actions.py delete_decision (the server decides;
 * this only hides buttons that would get a 403):
 *  - the chronicle's owner (Storyteller) and site admins: any message;
 *  - players: their own messages, never dice rows (dice_* kinds) or AI (Storyteller) messages.
 */
import { stripRollTags } from '../dice/rollRequests';
import { presentSpeaker } from './messageModel';

export const REPLY_EXCERPT_CHARS = 140;

const kindOf = (msg) => String((msg && msg.ai_message_kind) || '').toLowerCase();

export function isChronicleStaff(user, campaign) {
  if (!user) return false;
  if (user.role === 'admin') return true;
  return campaign?.created_by != null && user.id != null && String(campaign.created_by) === String(user.id);
}

export function isDiceMessage(msg) {
  return kindOf(msg).startsWith('dice_');
}

export function isAiMessage(msg) {
  return !!msg && msg.role === 'assistant' && !isDiceMessage(msg);
}

/** A saved row (optimistic lines have no actions until the server has them). */
export function isActionable(msg) {
  return !!msg && msg.id != null && !msg.temp;
}

export function canDeleteMessage(msg, { user, campaign } = {}) {
  if (!isActionable(msg) || !user) return false;
  if (isChronicleStaff(user, campaign)) return true;
  if (isDiceMessage(msg) || isAiMessage(msg)) return false;
  return msg.user_id != null && String(msg.user_id) === String(user.id);
}

/** The text Copy puts on the clipboard (the AI's roll tags are shown as chips, not copied). */
export function copyTextOf(msg) {
  const text = String((msg && msg.content) || '');
  return msg && msg.role === 'assistant' ? stripRollTags(text).trim() : text;
}

/** One plain line for a reply quote (same idea as the server's reply_excerpt). */
export function excerptOf(text, limit = REPLY_EXCERPT_CHARS) {
  let s = stripRollTags(String(text || ''))
    .replace(/[*_`#>~]+/g, '')
    .replace(/\s+/g, ' ')
    .trim();
  if (s.length > limit) s = `${s.slice(0, limit - 1).trimEnd()}…`;
  return s;
}

/** What the composer shows while replying, and the optimistic row's reply_to. */
export function replyTargetOf(msg) {
  const sp = presentSpeaker(msg);
  return {
    id: msg.id,
    author: msg.role === 'assistant' ? '' : sp.name,
    excerpt: excerptOf(msg.content),
    role: msg.role === 'assistant' ? 'assistant' : 'user',
  };
}

/** Clipboard write with a fallback for browsers without the async API (or without permission). */
export async function copyToClipboard(text) {
  try {
    if (typeof navigator !== 'undefined' && navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch (e) {
    /* fall through to the textarea fallback */
  }
  try {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    const ok = typeof document.execCommand === 'function' && document.execCommand('copy');
    document.body.removeChild(ta);
    return !!ok;
  } catch (e) {
    return false;
  }
}

/**
 * Where to put scrollTop after older rows were added above, so what you were reading stays put:
 * the old offset plus however much the content grew.
 */
export function anchoredScrollTop(prevScrollHeight, prevScrollTop, newScrollHeight) {
  return Math.max(0, prevScrollTop + (newScrollHeight - prevScrollHeight));
}
