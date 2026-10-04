import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { EmptyState, Glyph, Spinner, useReducedMotionPref } from '../../design';
import { buildTimeline } from './grouping';
import { markersById, messageKind } from './messageModel';
import { anchoredScrollTop } from './messageRules';
import { MessageGroup, cardFor } from './Messages';
import { formatDay } from './timeFormat';
import { t } from '../../i18n';

/** Distance (px) from the bottom that still counts as "at the bottom". */
export const NEAR_BOTTOM_PX = 120;

/** Scrolling within this many px of the top loads the older page. */
export const NEAR_TOP_PX = 160;

function firstRealId(messages) {
  for (const m of messages || []) if (m.id != null && !m.temp) return m.id;
  return null;
}

export function distanceFromBottom(el) {
  return el ? el.scrollHeight - el.scrollTop - el.clientHeight : 0;
}

/**
 * Message list with chat-app scrolling:
 * - entering a room scrolls to the "new" divider when there is one, else to the bottom
 * - new messages keep you at the bottom only if you were near it; otherwise a "jump to latest" pill counts them
 * - End (while the list has focus) jumps to the present
 * - older history (onLoadOlder): scrolling near the top, or the button there, loads the page
 *   before the oldest row; the reader's position stays put; "beginning of the room" when done
 */
export default function MessageList({
  roomKey,
  roomName,
  messages,
  status,
  firstUnreadId,
  hiddenIds,
  timeZone,
  onAtBottomChange,
  userId,
  hasMore = false,
  loadingOlder = false,
  onLoadOlder,
}) {
  const ref = useRef(null);
  const reduced = useReducedMotionPref();
  const [atBottom, setAtBottom] = useState(true);
  const [farUp, setFarUp] = useState(false);
  const [newCount, setNewCount] = useState(0);
  const atBottomRef = useRef(true);
  const appliedKey = useRef('');
  const lastIdRef = useRef(null);
  // Set right before older rows are requested: {height, top} of the list, to keep the reader's place.
  const olderAnchor = useRef(null);
  const messagesRef = useRef(messages);
  messagesRef.current = messages;
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 60000);
    return () => clearInterval(id);
  }, []);

  const rows = useMemo(
    () => buildTimeline(messages, { firstUnreadId, hiddenIds, timeZone }),
    [messages, firstUnreadId, hiddenIds, timeZone]
  );
  const markers = useMemo(() => markersById(messages), [messages]);

  const updateBottom = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    const d = distanceFromBottom(el);
    const bottom = d < NEAR_BOTTOM_PX;
    atBottomRef.current = bottom;
    setAtBottom(bottom);
    setFarUp(d > el.clientHeight);
    if (bottom) setNewCount(0);
    if (onAtBottomChange) onAtBottomChange(bottom);
  }, [onAtBottomChange]);

  const loadOlder = useCallback(async () => {
    const el = ref.current;
    if (!onLoadOlder || !el || olderAnchor.current) return;
    const anchor = { height: el.scrollHeight, top: el.scrollTop, firstId: firstRealId(messagesRef.current) };
    olderAnchor.current = anchor;
    let added = 0;
    try {
      added = await onLoadOlder();
    } finally {
      // Nothing added: no layout change to compensate. Otherwise the anchor effect consumes it;
      // the timer only guards against rows that render nothing (markers, hidden rows).
      if (!added) olderAnchor.current = null;
      else
        setTimeout(() => {
          if (olderAnchor.current === anchor) olderAnchor.current = null;
        }, 1000);
    }
  }, [onLoadOlder]);

  const onScroll = useCallback(() => {
    updateBottom();
    const el = ref.current;
    if (el && hasMore && !loadingOlder && status === 'ready' && el.scrollTop < NEAR_TOP_PX && el.scrollHeight > el.clientHeight) {
      loadOlder();
    }
  }, [updateBottom, hasMore, loadingOlder, status, loadOlder]);

  const scrollToBottom = useCallback(
    (smooth) => {
      const el = ref.current;
      if (!el) return;
      if (smooth && !reduced && typeof el.scrollTo === 'function') el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
      else el.scrollTop = el.scrollHeight;
      setNewCount(0);
    },
    [reduced]
  );

  // Entering a room (once its messages are in): divider or bottom.
  useLayoutEffect(() => {
    if (status !== 'ready') return;
    const key = `${roomKey}`;
    if (appliedKey.current === key) return;
    appliedKey.current = key;
    const el = ref.current;
    if (!el) return;
    const divider = el.querySelector('[data-unread-divider]');
    if (divider) el.scrollTop = Math.max(0, divider.offsetTop - 24);
    else el.scrollTop = el.scrollHeight;
    const real = messages.filter((m) => m.id != null);
    lastIdRef.current = real.length ? real[real.length - 1].id : null;
    setNewCount(0);
    updateBottom();
  }, [status, roomKey, messages, updateBottom]);

  // New rows: stick to the bottom when the reader was there (or it's their own line), else count them.
  useLayoutEffect(() => {
    if (status !== 'ready' || appliedKey.current !== `${roomKey}`) return;
    const el = ref.current;
    if (!el) return;
    const prevLast = lastIdRef.current;
    const fresh = messages.filter((m) => m.id != null && (prevLast == null || m.id > prevLast) && messageKind(m) !== 'marker');
    const real = messages.filter((m) => m.id != null);
    lastIdRef.current = real.length ? real[real.length - 1].id : prevLast;
    const ownTemp = messages.some((m) => m.temp);
    const own = fresh.some((m) => String(m.user_id) === String(userId));
    if (olderAnchor.current) {
      // An older page is landing; the anchor effect below places the scroll.
    } else if (atBottomRef.current || ownTemp || own) {
      el.scrollTop = el.scrollHeight;
    } else if (fresh.length) {
      setNewCount((n) => n + fresh.length);
    }
  }, [messages, rows.length, status, roomKey, userId]);

  // Older rows were added above: keep what the reader was looking at in place (no jump).
  useLayoutEffect(() => {
    const el = ref.current;
    const a = olderAnchor.current;
    if (!el || !a) return;
    const first = firstRealId(messages);
    if (!(first && a.firstId && first < a.firstId)) return; // the older page isn't in yet
    olderAnchor.current = null;
    el.scrollTop = anchoredScrollTop(a.height, a.top, el.scrollHeight);
    updateBottom();
  }, [messages, rows.length, updateBottom]);

  // Content that grows after layout (images, dice reveal) keeps a bottom-anchored reader at the bottom.
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof window.ResizeObserver !== 'function') return undefined;
    const inner = el.firstElementChild;
    if (!inner) return undefined;
    const ro = new window.ResizeObserver(() => {
      if (atBottomRef.current) el.scrollTop = el.scrollHeight;
    });
    ro.observe(inner);
    return () => ro.disconnect();
  }, [status]);

  const onKeyDown = (e) => {
    if (e.key === 'End' && !e.altKey && !e.ctrlKey && !e.metaKey) {
      e.preventDefault();
      scrollToBottom(false);
    }
  };

  const showPill = !atBottom && (newCount > 0 || farUp);

  return (
    <div className="sr-chat__listwrap">
      <div
        ref={ref}
        className="sr-chat__list"
        role="log"
        aria-live="polite"
        aria-relevant="additions"
        aria-label={t('chat:list.label', 'Messages in {{room}}', { room: roomName || '' })}
        tabIndex={0}
        onScroll={onScroll}
        onKeyDown={onKeyDown}
      >
        <div className="sr-chat__rows">
          {status === 'loading' ? (
            <div className="sr-chat__loading">
              <Spinner variant="candle" label={t('chat:loading', 'Unsealing the room…')} />
            </div>
          ) : null}
          {status === 'error' ? (
            <EmptyState glyph="warning" title={t('chat:loadFailed', 'Could not load this room')} />
          ) : null}
          {status === 'ready' && rows.length > 0 && onLoadOlder ? (
            hasMore ? (
              <div className="sr-chat__older">
                <button type="button" className="sr-chat__older-btn" onClick={loadOlder} disabled={loadingOlder} aria-busy={loadingOlder || undefined}>
                  {loadingOlder ? <Spinner size={16} decorative /> : <Glyph name="chevron-up" size={16} />}
                  <span>{loadingOlder ? t('chat:older.loading', 'Loading older messages…') : t('chat:older.load', 'Load older messages')}</span>
                </button>
              </div>
            ) : (
              <div className="sr-chat__beginning" role="note">
                <Glyph name="moon-new" size={18} />
                <span>{t('chat:older.beginning', 'The beginning of {{room}}', { room: roomName || '' })}</span>
              </div>
            )
          ) : null}
          {status === 'ready' && rows.length === 0 ? (
            <EmptyState glyph="moon-crescent" title={t('chat:empty.title', 'No whispers yet')} ambient className="sr-chat__empty">
              {t('chat:empty.body', 'Start the conversation in {{room}}.', { room: roomName || '' })}
            </EmptyState>
          ) : null}
          {status === 'ready'
            ? rows.map((row) => {
                if (row.type === 'day') {
                  return (
                    <div key={row.key} className="sr-chat__day" role="separator">
                      <span>{formatDay(row.time, now, timeZone)}</span>
                    </div>
                  );
                }
                if (row.type === 'unread') {
                  return (
                    <div key={row.key} className="sr-chat__new" role="separator" aria-label={t('chat:newMessages', 'New messages')} data-unread-divider>
                      <span>{t('chat:new', 'New')}</span>
                    </div>
                  );
                }
                if (row.type === 'card') return cardFor(row, markers, timeZone, now);
                return <MessageGroup key={row.key} group={row} timeZone={timeZone} now={now} />;
              })
            : null}
        </div>
      </div>
      {showPill ? (
        <button type="button" className="sr-chat__jump" onClick={() => scrollToBottom(true)}>
          <Glyph name="chevron-down" size={16} />
          {newCount > 0
            ? t('chat:jump.new', { one: '{{count}} new message', other: '{{count}} new messages' }, { count: newCount })
            : t('chat:jump.present', 'Jump to present')}
        </button>
      ) : null}
    </div>
  );
}
