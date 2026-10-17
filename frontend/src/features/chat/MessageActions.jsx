/**
 * Copy / Reply / Delete on chat messages (v0.10 phase 3).
 *
 * - Desktop: a small toolbar appears on hover or keyboard focus of a message.
 * - Touch (no hover): a "…" button on each message, or a long press, opens the toolbar (not while
 *   the finger scrolls or selects text).
 * - "Read this" / "Read from here" (read along, 0.22) when the page passes canRead / onRead.
 * - "Session ended here" (0.26): the Storyteller and site admins mark or unmark a message; everyone
 *   sees a thin "— end of session —" line under it (the marks come from a small endpoint).
 * - The page provides MessageActionsContext (PlayPage via useMessageActions); without it (the
 *   showcase preview) messages render without actions.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { Button, Glyph, IconButton, Modal } from '../../design';
import { errorText } from '../../app/http';
import { canDeleteMessage, copyTextOf, copyToClipboard, isActionable, isChronicleStaff, replyTargetOf } from './messageRules';
import { t } from '../../i18n';

export const MessageActionsContext = createContext(null);

export const LONG_PRESS_MS = 500;

/**
 * Long press (touch) on a message opens its toolbar; moving the finger cancels it. The menu opens
 * on touchend, once the timer has fired, and only if the press did not select text (phones make
 * the selection at the end of the gesture, so it is checked then, not when the timer fires).
 */
function useLongPress(onLongPress) {
  const timer = useRef(null);
  const fired = useRef(false);
  const cancel = () => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
    fired.current = false;
  };
  return {
    onTouchStart: () => {
      cancel();
      timer.current = setTimeout(() => {
        timer.current = null;
        fired.current = true;
      }, LONG_PRESS_MS);
    },
    onTouchMove: cancel,
    onTouchEnd: () => {
      const wasLong = fired.current;
      cancel();
      if (!wasLong) return;
      const sel = typeof window !== 'undefined' && window.getSelection ? String(window.getSelection() || '') : '';
      if (!sel.trim()) onLongPress();
    },
    onTouchCancel: cancel,
  };
}

/** Props for a message row: long press opens its actions. {} without actions. */
export function useMessageRowProps(message) {
  const ctx = useContext(MessageActionsContext);
  const press = useLongPress(() => ctx && ctx.setOpenId(message.id));
  if (!ctx || !isActionable(message)) return {};
  return press;
}

export function MessageActions({ message }) {
  const ctx = useContext(MessageActionsContext);
  if (!ctx || !isActionable(message)) return null;
  const open = ctx.openId === message.id;
  const deletable = ctx.canDelete(message);
  const close = () => ctx.setOpenId(null);
  return (
    <div
      className={`sr-msg-actions${open ? ' is-open' : ''}`}
      onKeyDown={(e) => {
        if (e.key === 'Escape' && open) {
          e.stopPropagation();
          close();
        }
      }}
    >
      <button
        type="button"
        className="sr-msg-actions__more"
        aria-label={t('chat:actions.more', 'More actions')}
        aria-expanded={open}
        onClick={() => ctx.setOpenId(open ? null : message.id)}
      >
        <Glyph name="more" size={18} />
      </button>
      <div className="sr-msg-actions__bar" role="toolbar" aria-label={t('chat:actions.label', 'Message actions')}>
        <IconButton
          icon="copy"
          size="sm"
          tooltip={false}
          label={t('chat:actions.copy', 'Copy text')}
          onClick={() => {
            close();
            ctx.onCopy(message);
          }}
        />
        <IconButton
          icon="reply"
          size="sm"
          tooltip={false}
          label={t('chat:actions.reply', 'Reply')}
          onClick={() => {
            close();
            ctx.onReply(message);
          }}
        />
        {ctx.canRead && ctx.canRead(message) ? (
          <>
            <IconButton
              icon="play"
              size="sm"
              tooltip={false}
              label={t('chat:actions.readThis', 'Read this')}
              onClick={() => {
                close();
                ctx.onRead(message, false);
              }}
            />
            <IconButton
              icon="ear"
              size="sm"
              tooltip={false}
              label={t('chat:actions.readFrom', 'Read from here')}
              onClick={() => {
                close();
                ctx.onRead(message, true);
              }}
            />
          </>
        ) : null}
        {ctx.canMarkSession && ctx.canMarkSession(message) ? (
          <IconButton
            icon="moon-new"
            size="sm"
            tooltip={false}
            aria-pressed={ctx.isSessionEnd(message)}
            label={
              ctx.isSessionEnd(message)
                ? t('chat:actions.sessionEndRemove', 'Remove the end of session mark')
                : t('chat:actions.sessionEnd', 'Session ended here')
            }
            onClick={() => {
              close();
              ctx.onToggleSessionEnd(message);
            }}
          />
        ) : null}
        {deletable ? (
          <IconButton
            icon="trash"
            size="sm"
            tooltip={false}
            className="sr-msg-actions__delete"
            label={t('chat:actions.delete', 'Delete message')}
            onClick={() => {
              close();
              ctx.onDelete(message);
            }}
          />
        ) : null}
      </div>
    </div>
  );
}

/** The compact quote above a reply. Clicking it scrolls to the original when it is loaded. */
export function ReplyQuote({ reply }) {
  const ctx = useContext(MessageActionsContext);
  if (!reply || reply.id == null) return null;
  const author = reply.role === 'assistant' ? t('chat:speaker.ai', 'Storyteller') : reply.author || '';
  const text = reply.hidden ? t('chat:reply.hidden', 'Hidden roll') : reply.excerpt || '';
  const label = t('chat:reply.jump', 'Replying to {{name}}: {{text}}. Show the original message', { name: author, text });
  const body = (
    <>
      <Glyph name="reply" size={14} className="sr-reply-quote__glyph" />
      {author ? <span className="sr-reply-quote__author">{author}</span> : null}
      <span className="sr-reply-quote__text">{text}</span>
    </>
  );
  if (!ctx || reply.hidden) return <div className="sr-reply-quote">{body}</div>;
  return (
    <button type="button" className="sr-reply-quote" aria-label={label} onClick={() => ctx.onJump(reply.id)}>
      {body}
    </button>
  );
}

/** "Replying to X" bar above the composer, with cancel. */
export function ReplyBar({ reply, onCancel }) {
  if (!reply) return null;
  const author = reply.role === 'assistant' ? t('chat:speaker.ai', 'Storyteller') : reply.author || '';
  return (
    <div className="sr-replybar" role="status">
      <Glyph name="reply" size={16} className="sr-replybar__glyph" />
      <div className="sr-replybar__text">
        <span className="sr-replybar__title">{t('chat:reply.replyingTo', 'Replying to {{name}}', { name: author })}</span>
        <span className="sr-replybar__excerpt">{reply.excerpt}</span>
      </div>
      <IconButton icon="close" size="sm" label={t('chat:reply.cancel', 'Cancel reply')} onClick={onCancel} />
    </div>
  );
}

/** Translated reason for a refused delete (codes from backend services/message_actions.py). */
export function deleteErrorText(r) {
  const code = r && r.data && r.data.code;
  if (code === 'message_not_yours') return t('chat:delete.notYours', 'You can only delete your own messages.');
  if (code === 'dice_message_staff_only') return t('chat:delete.diceStaffOnly', 'Only the Storyteller or an admin can delete dice rolls.');
  if (code === 'ai_message_staff_only') return t('chat:delete.aiStaffOnly', 'Only the Storyteller or an admin can delete Storyteller messages.');
  return errorText(r && r.data, t('chat:delete.failed', 'Could not delete the message.'));
}

/** Scroll a loaded message into view and flash it; false when it isn't in the list. */
export function jumpToMessage(id, { reduced = false, doc = typeof document !== 'undefined' ? document : null } = {}) {
  if (!doc) return false;
  const el = doc.getElementById(`msg-${id}`);
  if (!el) return false;
  if (typeof el.scrollIntoView === 'function') el.scrollIntoView({ block: 'center', behavior: reduced ? 'auto' : 'smooth' });
  if (!el.hasAttribute('tabindex')) el.setAttribute('tabindex', '-1');
  if (typeof el.focus === 'function') el.focus({ preventScroll: true });
  el.classList.remove('is-flash');
  // restart the highlight (reflow between remove and add)
  void el.offsetWidth;
  el.classList.add('is-flash');
  setTimeout(() => el.classList.remove('is-flash'), 1600);
  return true;
}

/**
 * Wires the actions for a room: who may delete, copy, reply state, the delete confirm dialog with
 * optimistic removal (rows come back if the server refuses). Returns { value, dialog, replyTo,
 * clearReply } — value goes into MessageActionsContext, dialog is rendered by the page.
 */
export function useMessageActions({ api, user, campaign, room, toast, reduced = false, onReplyStart }) {
  const [openId, setOpenId] = useState(null);
  const [replyTo, setReplyTo] = useState(null);
  const [confirming, setConfirming] = useState(null);
  const say = useCallback((opts) => toast && toast(opts), [toast]);
  const campaignId = campaign ? campaign.id : null;
  const [sessionEnds, setSessionEnds] = useState(() => new Set());

  // Session-end marks of the chronicle (they cut every room): one small request per chronicle, apart
  // from the room's messages so the chat never waits for it.
  useEffect(() => {
    let live = true;
    setSessionEnds(new Set());
    if (campaignId == null || !api) return undefined;
    (async () => {
      const r = await api(`/campaigns/${campaignId}/chronicle/session-marks`);
      if (live && r && r.ok && r.data && Array.isArray(r.data.message_ids)) setSessionEnds(new Set(r.data.message_ids.map(String)));
    })();
    return () => {
      live = false;
    };
  }, [api, campaignId]);

  const onToggleSessionEnd = useCallback(
    async (msg) => {
      const key = String(msg.id);
      const was = sessionEnds.has(key);
      const flip = (on) =>
        setSessionEnds((prev) => {
          const next = new Set(prev);
          if (on) next.add(key);
          else next.delete(key);
          return next;
        });
      flip(!was);
      const r = was
        ? await api(`/campaigns/${campaignId}/chronicle/session-marks/${msg.id}`, { method: 'DELETE' })
        : await api(`/campaigns/${campaignId}/chronicle/session-marks`, { method: 'POST', body: { message_id: msg.id } });
      if (r && r.ok) {
        say({
          tone: 'ok',
          title: was
            ? t('chat:sessionEnd.removed', 'End of session mark removed. The next Update of the chronicle so far rewrites those nights.')
            : t('chat:sessionEnd.added', 'Marked as the end of the session. The next Update of the chronicle so far rewrites those nights.'),
        });
        return true;
      }
      flip(was);
      say({ tone: 'danger', title: errorText(r && r.data, t('chat:sessionEnd.failed', 'Could not change the end of session mark.')) });
      return false;
    },
    [api, campaignId, sessionEnds, say]
  );

  const onCopy = useCallback(
    async (msg) => {
      const ok = await copyToClipboard(copyTextOf(msg));
      say(ok ? { tone: 'ok', title: t('chat:actions.copied', 'Copied to the clipboard.') } : { tone: 'danger', title: t('chat:actions.copyFailed', 'Could not copy the text.') });
    },
    [say]
  );

  const onReply = useCallback(
    (msg) => {
      setReplyTo(replyTargetOf(msg));
      if (onReplyStart) onReplyStart();
    },
    [onReplyStart]
  );

  const onJump = useCallback(
    (id) => {
      if (!jumpToMessage(id, { reduced })) say({ tone: 'info', title: t('chat:reply.notLoaded', 'The original message is further back. Load older messages to see it.') });
    },
    [reduced, say]
  );

  const deleteNow = useCallback(
    async (msg) => {
      const removed = room.removeMessages([msg.id]);
      const ids = removed.map((m) => m.id);
      const r = await api(`/messages/${msg.id}`, { method: 'DELETE' });
      if (r.ok) {
        // A roll's marker row goes with its result line.
        const extra = Array.isArray(r.data && r.data.deleted_ids) ? r.data.deleted_ids.filter((id) => !ids.includes(id)) : [];
        if (extra.length) room.removeMessages(extra);
        room.settleRemoval([...ids, ...extra]);
        if (replyTo && replyTo.id === msg.id) setReplyTo(null);
        return true;
      }
      if (r.status === 404) {
        room.settleRemoval(ids); // already gone
        return true;
      }
      room.settleRemoval(ids, removed);
      say({ tone: 'danger', title: deleteErrorText(r) });
      return false;
    },
    [api, room, replyTo, say]
  );

  const value = useMemo(
    () => ({
      openId,
      setOpenId,
      canDelete: (msg) => canDeleteMessage(msg, { user, campaign }),
      onCopy,
      onReply,
      onJump,
      onDelete: (msg) => setConfirming(msg),
      canMarkSession: (msg) => isChronicleStaff(user, campaign) && msg && typeof msg.id === 'number' && !msg.temp,
      isSessionEnd: (msg) => !!msg && sessionEnds.has(String(msg.id)),
      onToggleSessionEnd,
    }),
    [openId, user, campaign, onCopy, onReply, onJump, sessionEnds, onToggleSessionEnd]
  );

  const dialog = (
    <Modal
      open={!!confirming}
      onClose={() => setConfirming(null)}
      title={t('chat:delete.title', 'Delete this message?')}
      icon="trash"
      size="sm"
      footer={
        <>
          <Button variant="secondary" onClick={() => setConfirming(null)}>
            {t('chat:delete.cancel', 'Keep it')}
          </Button>
          <Button
            variant="danger"
            icon="trash"
            onClick={() => {
              const msg = confirming;
              setConfirming(null);
              // Optimistic: the row disappears now and comes back if the server refuses.
              deleteNow(msg);
              // The delete button is gone with its row: keep keyboard focus in the message list.
              requestAnimationFrame(() => {
                const list = document.querySelector('.sr-chat__list');
                if (list && (!document.activeElement || document.activeElement === document.body)) list.focus();
              });
            }}
          >
            {t('chat:delete.confirm', 'Delete')}
          </Button>
        </>
      }
    >
      <p>{t('chat:delete.body', 'It is removed for everyone in the room. This can’t be undone.')}</p>
      {confirming ? <blockquote className="sr-delete-preview">{replyTargetOf(confirming).excerpt}</blockquote> : null}
    </Modal>
  );

  return { value, dialog, replyTo, clearReply: () => setReplyTo(null), deleteNow, sessionEnds };
}
