/**
 * What a stored chat row is, and who it speaks for.
 *
 * Message rows come from GET /campaigns/<c>/locations/<l> (backend/routes/messages.py
 * _message_dict_from_row). Kinds:
 *  - marker:     dice animation transport rows (ai_message_kind dice_animation[_hidden]:<id>), never shown
 *  - dice:       the final roll line (dice_roll[_hidden]:<id>), shown as a dice card
 *  - ai:         AI Storyteller narration (role assistant)
 *  - diagnostic: /ai tool output (role assistant, ai_message_kind slash_assistant)
 *  - system:     message_type system (room events, moderation notes)
 *  - action:     message_type action without a dice kind (Rouse checks, /me emotes)
 *  - text:       everything else (players, characters, staff)
 */
import { t } from '../../i18n';

export const MARKER_PREFIXES = ['dice_animation:', 'dice_animation_hidden:'];
export const DICE_PREFIXES = ['dice_roll:', 'dice_roll_hidden:'];

const kindOf = (msg) => String((msg && msg.ai_message_kind) || '').toLowerCase();

export function isMarker(msg) {
  const k = kindOf(msg);
  return MARKER_PREFIXES.some((p) => k.startsWith(p));
}

export function diceAnimationId(msg) {
  const k = kindOf(msg);
  const prefix = [...MARKER_PREFIXES, ...DICE_PREFIXES].find((p) => k.startsWith(p));
  if (!prefix) return null;
  const id = k.slice(prefix.length);
  return id || null;
}

export function isHiddenRoll(msg) {
  const k = kindOf(msg);
  return k.startsWith('dice_roll_hidden:') || k.startsWith('dice_animation_hidden:');
}

export function speakerMode(msg) {
  const raw = msg && msg.speaker_mode;
  if (raw === 'staff' || raw === 'player' || raw === 'character') return raw;
  const cid = msg && msg.character_id != null && msg.character_id !== '' ? Number(msg.character_id) : null;
  return cid ? 'character' : 'player';
}

export function messageKind(msg) {
  if (!msg) return 'text';
  if (isMarker(msg)) return 'marker';
  const k = kindOf(msg);
  if (DICE_PREFIXES.some((p) => k.startsWith(p))) return 'dice';
  if (msg.role === 'assistant') return k === 'slash_assistant' ? 'diagnostic' : 'ai';
  const mt = String(msg.message_type || '').toLowerCase();
  if (mt === 'system') return 'system';
  if (mt === 'action') return 'action';
  return 'text';
}

/** Stable key: consecutive rows with the same key (and close in time) form one group. */
export function speakerKey(msg) {
  if (!msg) return '';
  if (msg.role === 'assistant') return 'ai';
  const sm = speakerMode(msg);
  if (sm === 'character') return `character:${msg.character_id || ''}:${msg.user_id || msg.username || ''}`;
  return `${sm}:${msg.user_id || msg.username || ''}`;
}

/**
 * Display data for the author of a message: name, secondary label, avatar, tone.
 * tone: 'ai' | 'storyteller' | 'staff' | 'character' | 'player'
 */
export function presentSpeaker(msg) {
  if (!msg) return { name: '', tone: 'player' };
  if (msg.role === 'assistant') {
    return { name: t('chat:speaker.ai', 'Storyteller'), badge: t('chat:badge.ai', 'AI'), tone: 'ai', avatar: null };
  }
  const username = String(msg.username || '').trim() || t('chat:speaker.player', 'Player');
  const sm = speakerMode(msg);
  if (sm === 'staff') {
    const storyteller = msg.staff_kind === 'storyteller';
    return {
      name: username,
      badge: storyteller ? t('chat:badge.storyteller', 'Storyteller') : t('chat:badge.staff', 'Staff'),
      tone: storyteller ? 'storyteller' : 'staff',
      avatar: msg.player_avatar_url || null,
    };
  }
  const charName = String(msg.character_name || '').trim();
  if (sm === 'character' && (charName || msg.character_id)) {
    return {
      name: charName || t('chat:speaker.character', 'Character'),
      secondary: username,
      tone: 'character',
      avatar: msg.character_portrait_url || msg.player_avatar_url || null,
    };
  }
  return {
    name: username,
    badge: t('chat:badge.ooc', 'OOC'),
    tone: 'player',
    avatar: msg.player_avatar_url || null,
  };
}

/** Parse a server timestamp ("Sun, 04 Oct 2026 00:18:04 GMT" or ISO). Returns ms or NaN. */
export function messageTime(msg) {
  if (!msg || msg.created_at == null) return NaN;
  const d = msg.created_at instanceof Date ? msg.created_at : new Date(msg.created_at);
  return d.getTime();
}

/** Map animation id → parsed marker JSON (for dice cards). */
export function markersById(messages) {
  const map = {};
  for (const m of messages || []) {
    if (!isMarker(m)) continue;
    const id = diceAnimationId(m);
    if (!id) continue;
    try {
      const obj = typeof m.content === 'string' ? JSON.parse(m.content) : m.content;
      if (obj && typeof obj === 'object') map[id] = obj;
    } catch (e) {
      /* malformed marker: card falls back to the text line */
    }
  }
  return map;
}

/**
 * A Rouse check line (ai_message_kind dice_rouse:<id>) as data, parsed from the fixed English
 * template in backend services/v5_dice.py format_rouse_markdown (older rows start with a blood-drop
 * emoji). Returns {die, success, hungerBefore, hungerAfter, atMax} or null when it does not match.
 */
const ROUSE_RE = /^(?:\u{1FA78}\s*)?(?:\*\*.+\*\* makes a Rouse check|\*\*Rouse check\*\*): rolled \*\*(\d+)\*\* — (success|failure), (.*)$/su;
export function parseRouseLine(msg) {
  if (!kindOf(msg).startsWith('dice_rouse:')) return null;
  const m = ROUSE_RE.exec(String(msg.content || '').trim());
  if (!m) return null;
  const die = Number(m[1]);
  const success = m[2] === 'success';
  const tail = m[3];
  if (success) {
    const h = /Hunger stays \*\*(\d+)\*\*/.exec(tail);
    return h ? { die, success, hungerBefore: Number(h[1]), hungerAfter: Number(h[1]), atMax: false } : null;
  }
  if (/Hunger cannot rise further/.test(tail)) return { die, success, hungerBefore: 5, hungerAfter: 5, atMax: true };
  const f = /Hunger \*\*(\d+) → (\d+)\*\*/.exec(tail);
  return f ? { die, success, hungerBefore: Number(f[1]), hungerAfter: Number(f[2]), atMax: false } : null;
}
