/**
 * Sending a chat line (ported from SimpleApp.handleSendMessage, same server protocol):
 *
 * 1. POST the user's line to the room (speak_as, character_id, message_type ic/ooc/action).
 * 2. `/ai <verb>` (site admins): POST /api/ai/slash, then save the returned text as an assistant line
 *    (`slash_assistant`), or for `/ai roll[-hidden]` the dice marker + final line.
 *    `/ai explain` (`/ai εξήγησε`) is open to every member: it explains the replied-to dice roll.
 *    The reply target goes to /api/ai/slash and /api/ai/chat as reply_to_id.
 *    `/chat <text>`: POST /api/ai/chat with assistant_direct, save the reply (`chat_assistant`).
 *    Anything else: POST /api/ai/chat; OOC rooms may answer `ooc_no_reply`.
 * 3. The browser saves AI replies as role "assistant" messages; the server only accepts text it
 *    handed to this user (phase 2 services/assistant_grants.py).
 *
 * Everything UI-related goes through callbacks so this stays testable and component-free.
 */
import { canUseStaffVoice } from '../../app/hooks';
import { buildDiceMarker } from '../../dice/diceMarker';
import { t } from '../../i18n';

let tempSeq = 0;

/**
 * OOC moderation notice from the server's structured `ooc_warning_info`
 * ({count, threshold, banned, ban_hours, until}) as translated {title, body}; null without it.
 */
export function oocWarningNotice(info) {
  if (!info || typeof info !== 'object') return null;
  const count = Number(info.count) || 0;
  const threshold = Number(info.threshold) || 0;
  if (info.banned) {
    const until = info.until ? new Date(info.until) : null;
    const when = until && !Number.isNaN(until.getTime()) ? until.toLocaleString() : '';
    return {
      title: t('chat:ooc.bannedTitle', 'Temporarily barred from this chronicle'),
      body: [
        t('chat:ooc.bannedBody', 'You can’t post in this chronicle for {{hours}} hours: too many in-character lines in the out-of-character room.', { hours: info.ban_hours || '' }),
        when ? t('chat:ooc.bannedUntil', 'You can post again after {{when}}.', { when }) : '',
      ].filter(Boolean).join(' '),
    };
  }
  const left = Math.max(0, threshold - count);
  return {
    title: t('chat:ooc.warningTitle', 'Out-of-character room: warning {{count}} of {{threshold}}', { count, threshold }),
    body: [
      t('chat:ooc.warningBody', 'This line reads as in-character. Keep roleplay to the story rooms; this room is for talking as players.'),
      t('chat:ooc.warningsLeft', 'Warnings left before a temporary bar from this chronicle: {{left}}.', { left }),
    ].join(' '),
  };
}

export function makeAnimationId() {
  return `dice_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

/** Strip BOM; bare `/ai` → `/ai help` for admins. */
export function normalizeInput(raw, isAdmin) {
  const s = String(raw == null ? '' : raw).replace(/^\uFEFF+/, '').trim();
  if (!s) return s;
  if (isAdmin && /^\s*\/ai\s*$/i.test(s)) return '/ai help';
  return s;
}

/** `/ai explain …` / `/ai εξήγησε …`: the one /ai verb every chronicle member may use. */
export function isExplainCommand(text) {
  return /^\s*\/ai\s+(explain|εξήγησε)(\s|$)/i.test(String(text || ''));
}

export function staffKindFor(user, campaign) {
  if (user?.role === 'admin' || user?.role === 'helper') return 'admin';
  if (campaign?.created_by != null && user?.id != null && String(campaign.created_by) === String(user.id)) return 'storyteller';
  return 'staff';
}

/** Optimistic row shown until the server echoes the saved message. */
export function optimisticMessage({ text, user, campaign, location, speakAs, character, messageType, replyTo = null }) {
  tempSeq += 1;
  const asChar = speakAs === 'character' && character?.id;
  return {
    client_id: `tmp-${Date.now()}-${tempSeq}`,
    temp: true,
    role: 'user',
    content: text,
    message_type: messageType,
    created_at: new Date().toISOString(),
    location_id: location.id,
    user_id: user?.id,
    username: user?.username,
    poster_role: user?.role || '',
    speaker_mode: speakAs,
    staff_kind: speakAs === 'staff' ? staffKindFor(user, campaign) : null,
    player_avatar_url: user?.player_avatar_url || null,
    character_id: asChar ? character.id : null,
    character_name: asChar ? character.name : null,
    character_portrait_url: asChar ? character.portrait_url || null : null,
    reply_to: replyTo ? { id: replyTo.id, author: replyTo.author || '', excerpt: replyTo.excerpt || '', role: replyTo.role || 'user' } : null,
  };
}

/**
 * @param {object} ctx
 *  api(path, opts) → {ok,status,data}; campaign; location; user; speakAs; character;
 *  callbacks: onOptimistic(msg), onSaved(clientId, msg|null), onAppend(msgs), onError(text),
 *             onPrivateNotice({title, markdown}) (shown to this user only, never saved),
 *             onAiPending(bool), onDiceMarker(marker), onRoomReload(), onLocationsChanged(),
 *             onReplyGone() (the replied-to message was deleted meanwhile)
 * @param {string} rawText
 * @param {{ messageType?: 'action', replyTo?: {id, author, excerpt, role} }} [opts]
 *   replyTo: the message this line answers (reply_to_id; shown as a quote above it)
 * @returns {Promise<boolean>} true when the user's line was saved
 */
export async function sendChatMessage(ctx, rawText, opts = {}) {
  const { api, campaign, location, user, speakAs, character } = ctx;
  const cb = {
    onOptimistic: () => {},
    onSaved: () => {},
    onAppend: () => {},
    onError: () => {},
    onAiPending: () => {},
    onDiceMarker: () => {},
    onRoomReload: () => {},
    onLocationsChanged: () => {},
    onReplyGone: () => {},
    ...ctx,
  };
  const isAdmin = user?.role === 'admin';
  const text = normalizeInput(rawText, isAdmin);
  if (!text) return false;

  const explain = isExplainCommand(text);
  if (/^\s*\/ai(\s+|$)/i.test(text) && !isAdmin && !explain) {
    cb.onError(t('chat:error.aiAdminOnly', 'Only site administrators can use /ai commands. Use the dice button to roll.'));
    return false;
  }
  const chatMatch = text.match(/^\s*\/chat(?:\s+([\s\S]*))?$/i);
  if (chatMatch && !(chatMatch[1] || '').trim()) {
    cb.onError(t('chat:error.chatUsage', 'Usage: /chat followed by your message to the AI assistant.'));
    return false;
  }
  const slashMatch = text.match(/^\s*\/ai\s+(\S+)(?:\s+([\s\S]*))?$/i);
  const inOoc = String(location?.type || '').toLowerCase() === 'ooc';
  const roomType = inOoc ? 'ooc' : 'ic';
  const messageType = opts.messageType || roomType;
  const roomPath = `/campaigns/${campaign.id}/locations/${location.id}`;

  const replyTo = opts.replyTo && opts.replyTo.id != null ? opts.replyTo : null;
  // /ai commands are posted with the staff voice; a player's /ai explain uses the player voice.
  const slashVoice = explain && !canUseStaffVoice(user, campaign) ? 'player' : 'staff';
  const temp = optimisticMessage({ text, user, campaign, location, speakAs: slashMatch ? slashVoice : speakAs, character, messageType, replyTo });
  cb.onOptimistic(temp);

  const save = await api(roomPath, {
    method: 'POST',
    body: {
      content: text,
      message_type: messageType,
      role: 'user',
      // /ai commands are staff tools, never the character's in-character line.
      speak_as: slashMatch ? slashVoice : speakAs,
      ...(!slashMatch && speakAs === 'character' && character?.id ? { character_id: character.id } : {}),
      ...(slashMatch ? { ai_message_kind: 'slash_user' } : chatMatch ? { ai_message_kind: 'chat_user' } : {}),
      ...(replyTo ? { reply_to_id: replyTo.id } : {}),
    },
  });
  const notifyOoc = (data) => {
    const notice = oocWarningNotice(data && data.ooc_warning_info);
    if (!notice) return false;
    if (cb.onNotice) cb.onNotice({ tone: data.ooc_warning_info.banned ? 'danger' : 'warn', ...notice });
    else cb.onError(notice.title);
    return true;
  };
  if (!save.ok) {
    cb.onSaved(temp.client_id, null);
    const replyGone = /^(reply_target_|invalid_reply_to)/.test(String((save.data && save.data.code) || ''));
    if (replyGone) {
      cb.onReplyGone();
      cb.onError(t('chat:reply.gone', 'The message you replied to is gone. Your text is still in the box.'));
    }
    else if (!notifyOoc(save.data)) cb.onError(save.data.error || t('chat:error.saveFailed', 'Your message could not be saved.'));
    return false;
  }
  cb.onSaved(temp.client_id, save.data.data || null);
  if (save.data.ooc_warning && !notifyOoc(save.data)) {
    cb.onError(t('chat:ooc.warningFallback', 'This line reads as in-character. Keep roleplay to the story rooms.'));
  }

  // rollRequests: the structured rolls /api/ai/chat resolved from the sheet (features/dice/rollRequests.js).
  const postAssistant = async (content, kind, rollRequests) => {
    const r = await api(roomPath, {
      method: 'POST',
      body: { content, message_type: roomType, role: 'assistant', ...(kind ? { ai_message_kind: kind } : {}) },
    });
    if (r.ok && r.data.data) {
      const saved = Array.isArray(rollRequests) && rollRequests.length ? { ...r.data.data, roll_requests: rollRequests } : r.data.data;
      cb.onAppend([saved]);
    }
    else cb.onError(r.data.error || t('chat:error.aiSaveFailed', 'The Storyteller’s reply could not be saved.'));
  };

  cb.onAiPending(true);
  try {
    if (slashMatch) {
      const r = await api('/ai/slash', {
        method: 'POST',
        body: { line: text.trim(), campaign_id: campaign.id, location_id: location.id, ...(replyTo ? { reply_to_id: replyTo.id } : {}) },
      });
      const d = r.data || {};
      // /ai explain of a hidden roll: for the requester only, never saved to the room.
      if (r.ok && d.private_markdown) {
        if (cb.onPrivateNotice) {
          cb.onPrivateNotice({ title: t('chat:explain.privateTitle', 'Only you can see this (hidden roll)'), markdown: d.private_markdown });
        }
        return true;
      }
      const content = d.display_markdown || d.llm_acknowledgment || null;
      const hasReply = Boolean(content && String(content).trim());
      if (!r.ok && !hasReply) {
        cb.onError(d.error || t('chat:error.slashFailed', 'Slash command failed'));
        return true;
      }
      if (!r.ok && d.error) cb.onError(d.error);
      if (d.command === 'roll' || d.command === 'roll-hidden') {
        const hidden = d.command === 'roll-hidden';
        const animationId = makeAnimationId();
        const marker = buildDiceMarker(d.roll || {}, { animationId, startedAtMs: Date.now(), durationMs: 3000 });
        cb.onDiceMarker(marker);
        const m1 = await api(roomPath, {
          method: 'POST',
          body: {
            content: JSON.stringify(marker),
            message_type: roomType,
            role: 'assistant',
            ai_message_kind: `${hidden ? 'dice_animation_hidden' : 'dice_animation'}:${animationId}`,
          },
        });
        if (!m1.ok) {
          cb.onError(m1.data.error || t('dice:error.marker', 'Could not post the dice animation.'));
          return true;
        }
        const m2 = await api(roomPath, {
          method: 'POST',
          body: {
            content,
            message_type: roomType,
            role: 'assistant',
            ai_message_kind: `${hidden ? 'dice_roll_hidden' : 'dice_roll'}:${animationId}`,
          },
        });
        if (!m2.ok) {
          cb.onError(m2.data.error || t('dice:error.result', 'Could not post the roll result.'));
          return true;
        }
        cb.onAppend([m1.data.data, m2.data.data].filter(Boolean));
      } else if (hasReply) {
        await postAssistant(content, 'slash_assistant');
      }
      if (d.clean_target === 'ai' && typeof d.deleted_count === 'number') cb.onRoomReload();
      if (d.command === 'dice-diff') cb.onLocationsChanged();
      return true;
    }

    const body = chatMatch
      ? {
          message: (chatMatch[1] || '').trim(),
          campaign_id: campaign.id,
          location: location.id,
          location_type: location.type,
          assistant_direct: true,
        }
      : { message: text, campaign_id: campaign.id, location: location.id, location_type: location.type };
    // The quoted message reaches the Storyteller's prompt (backend services/reply_context.py).
    if (replyTo) body.reply_to_id = replyTo.id;
    // Ask the Storyteller; on failure the room shows one inline notice with a Retry (the player's
    // message is already saved, so a retry only asks again).
    const askAi = async () => {
      const ai = await api('/ai/chat', { method: 'POST', body });
      if (!ai.ok) {
        const reason = ai.status === 503 || ai.status === 429 || ai.status === 0 ? ai.data.error : null;
        const retry = async () => {
          cb.onAiPending(true);
          try {
            await askAi();
          } finally {
            cb.onAiPending(false);
          }
        };
        if (cb.onAiFailed) cb.onAiFailed({ reason: reason || null, retry });
        else cb.onError(ai.data.error || t('chat:error.aiFailed', 'The Storyteller could not answer.'));
        return;
      }
      const raw = ai.data.response != null ? ai.data.response : ai.data.message;
      const reply = raw != null && String(raw).trim() !== '' ? String(raw).trim() : null;
      if (!ai.data.ooc_no_reply && reply) {
        await postAssistant(reply, chatMatch ? 'chat_assistant' : null, ai.data.roll_requests);
      }
    };
    await askAi();
    return true;
  } finally {
    cb.onAiPending(false);
  }
}
