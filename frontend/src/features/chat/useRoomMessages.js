import { useCallback, useEffect, useRef, useState } from 'react';
import { readLocal, writeLocal } from '../../app/hooks';
import { isMarker } from './messageModel';

export const INITIAL_LIMIT = 150;
export const OLDER_LIMIT = 50;

// Per user, so a shared browser doesn't carry one account's read state over to another.
const seenKey = (uid, cid, lid) => `sr_seen_${uid == null ? 'anon' : uid}_${cid}_${lid}`;

export function readSeen(userId, campaignId, locationId) {
  const v = parseInt(readLocal(seenKey(userId, campaignId, locationId), '0'), 10);
  return Number.isFinite(v) ? v : 0;
}

export function writeSeen(userId, campaignId, locationId, id) {
  if (id > readSeen(userId, campaignId, locationId)) writeLocal(seenKey(userId, campaignId, locationId), id);
}

/** "12:340,13:0" for GET /unread?seen= (players without a character keep read state in this browser). */
export function seenParam(userId, campaignId, locations) {
  return (locations || []).map((l) => `${l.id}:${readSeen(userId, campaignId, l.id)}`).join(',');
}

/** Merge server rows into the list: unique by id, ascending, optimistic rows kept at the end. */
export function mergeMessages(prev, incoming) {
  const byId = new Map();
  for (const m of prev) if (m.id != null) byId.set(m.id, m);
  for (const m of incoming || []) if (m && m.id != null) byId.set(m.id, m);
  const core = [...byId.values()].sort((a, b) => a.id - b.id);
  const temps = prev.filter((m) => m.temp && m.id == null);
  return [...core, ...temps];
}

export function firstServerId(messages) {
  let min = 0;
  for (const m of messages) if (m.id != null && !m.temp && (min === 0 || m.id < min)) min = m.id;
  return min;
}

/**
 * A refetched newest page merged with what was loaded before it: rows in the window come from the
 * server (deleted ones drop out), older pages loaded with "Load older" stay unless the page shows
 * the room's beginning, optimistic rows stay at the end.
 */
export function mergeRefresh(prev, fresh, limit = INITIAL_LIMIT) {
  const temps = prev.filter((m) => m.temp && m.id == null);
  const sorted = [...fresh].sort((a, b) => a.id - b.id);
  const oldest = sorted.length ? sorted[0].id : null;
  const keepOlder = sorted.length >= limit && oldest != null;
  const older = keepOlder ? prev.filter((m) => m.id != null && !m.temp && m.id < oldest) : [];
  return [...older, ...sorted, ...temps];
}

export function lastServerId(messages) {
  let max = 0;
  for (const m of messages) if (m.id != null && !m.temp && m.id > max) max = m.id;
  return max;
}

/**
 * Messages of one room + its read state.
 * - status: 'loading' | 'ready' | 'closed' (room sealed for this player) | 'error'
 * - firstUnreadId: fixed when the room is entered (the "new messages" divider stays until you leave)
 */
export function useRoomMessages({ api, campaignId, locationId, characterId, userId, enabled = true }) {
  const [messages, setMessages] = useState([]);
  const [status, setStatus] = useState('loading');
  const [closedInfo, setClosedInfo] = useState(null);
  const [firstUnreadId, setFirstUnreadId] = useState(null);
  // Older history: true while there may be rows before the oldest loaded one.
  const [hasMore, setHasMore] = useState(false);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const olderInflight = useRef(false);
  // Ids removed optimistically (delete pending): a refetch must not bring them back meanwhile.
  const removing = useRef(new Set());
  const messagesRef = useRef(messages);
  messagesRef.current = messages;
  const roomRef = useRef(`${campaignId}:${locationId}`);
  const inflight = useRef(false);
  const again = useRef(false);
  const lastMarked = useRef(0);

  const roomPath = `/campaigns/${campaignId}/locations/${locationId}`;

  const load = useCallback(async () => {
    const key = `${campaignId}:${locationId}`;
    roomRef.current = key;
    setStatus('loading');
    setClosedInfo(null);
    setFirstUnreadId(null);
    setHasMore(false);
    lastMarked.current = 0;
    const r = await api(`${roomPath}?recent=1&limit=${INITIAL_LIMIT}`);
    if (roomRef.current !== key) return;
    if (!r.ok) {
      setMessages([]);
      if (r.status === 403 && r.data.error === 'location_closed') {
        setClosedInfo({ message: r.data.message, flavor: r.data.flavor });
        setStatus('closed');
      } else setStatus('error');
      return;
    }
    const list = Array.isArray(r.data) ? r.data : [];
    let firstUnread = null;
    if (characterId) {
      const rs = await api(`${roomPath}/read-state?character_id=${characterId}`);
      if (roomRef.current !== key) return;
      if (rs.ok) {
        firstUnread = rs.data.first_unread_message_id || null;
        lastMarked.current = rs.data.last_read_message_id || 0;
      }
    } else {
      const seen = readSeen(userId, campaignId, locationId);
      lastMarked.current = seen;
      if (seen > 0) {
        const next = list.find((m) => m.id > seen && !isMarker(m) && String(m.user_id) !== String(userId));
        firstUnread = next ? next.id : null;
      }
    }
    // Only show the divider if there's something after it in what we loaded
    if (firstUnread && !list.some((m) => m.id >= firstUnread)) firstUnread = null;
    setFirstUnreadId(firstUnread);
    setMessages(list);
    // A full first page may have more before it (the server filters hidden rolls before LIMIT).
    setHasMore(list.length >= INITIAL_LIMIT);
    setStatus('ready');
  }, [api, roomPath, campaignId, locationId, characterId, userId]);

  useEffect(() => {
    setMessages([]);
    if (enabled && locationId) load();
    else setStatus('loading');
  }, [load, enabled, locationId]);

  /**
   * Fetch rows newer than what we have (SSE "changed" / poll tick). A call that arrives while a
   * fetch is running isn't dropped: it marks a re-run, done once the current fetch finishes (so a
   * message saved during the fetch still shows up without waiting for the next event).
   */
  const fetchSince = useCallback(async () => {
    if (!enabled) return;
    if (inflight.current) {
      again.current = true;
      return;
    }
    inflight.current = true;
    try {
      do {
        again.current = false;
        const key = roomRef.current;
        const since = lastServerId(messagesRef.current);
        const r = await api(since > 0 ? `${roomPath}?since_id=${since}&limit=200` : `${roomPath}?recent=1&limit=${INITIAL_LIMIT}`);
        if (roomRef.current !== key) break;
        if (r.ok && Array.isArray(r.data) && r.data.length > 0) {
          // Update the ref now so a re-run asks only for what came after these rows.
          const rows = r.data.filter((m) => !removing.current.has(m.id));
          messagesRef.current = mergeMessages(messagesRef.current, rows);
          setMessages((prev) => mergeMessages(prev, rows));
        }
      } while (again.current);
    } finally {
      inflight.current = false;
      again.current = false;
    }
  }, [api, roomPath, enabled]);

  /** Full reload without resetting the divider (deletes / /ai clean). */
  const refresh = useCallback(async () => {
    const key = roomRef.current;
    const r = await api(`${roomPath}?recent=1&limit=${INITIAL_LIMIT}`);
    if (roomRef.current !== key || !r.ok || !Array.isArray(r.data)) return;
    const fresh = r.data.filter((m) => !removing.current.has(m.id));
    setMessages((prev) => mergeRefresh(prev, fresh, INITIAL_LIMIT));
    if (r.data.length < INITIAL_LIMIT) setHasMore(false);
  }, [api, roomPath]);

  /**
   * The page before the oldest loaded row (GET ?before_id=&limit=). Returns the number of rows
   * added; the list keeps its scroll position (MessageList anchors it).
   */
  const loadOlder = useCallback(async () => {
    if (!enabled || olderInflight.current) return 0;
    const before = firstServerId(messagesRef.current);
    if (!before) {
      setHasMore(false);
      return 0;
    }
    const key = roomRef.current;
    olderInflight.current = true;
    setLoadingOlder(true);
    try {
      const r = await api(`${roomPath}?before_id=${before}&limit=${OLDER_LIMIT}`);
      if (roomRef.current !== key) return 0;
      if (!r.ok || !r.data || !Array.isArray(r.data.messages)) return 0;
      const rows = r.data.messages.filter((m) => !removing.current.has(m.id));
      messagesRef.current = mergeMessages(messagesRef.current, rows);
      setMessages((prev) => mergeMessages(prev, rows));
      setHasMore(!!r.data.has_more);
      return rows.length;
    } finally {
      olderInflight.current = false;
      if (roomRef.current === key) setLoadingOlder(false);
    }
  }, [api, roomPath, enabled]);

  /** Optimistic delete: drop rows now, returns them so a failed delete can put them back. */
  const removeMessages = useCallback((ids) => {
    const set = new Set((ids || []).map(Number));
    set.forEach((id) => removing.current.add(id));
    const removed = messagesRef.current.filter((m) => m.id != null && set.has(Number(m.id)));
    messagesRef.current = messagesRef.current.filter((m) => !(m.id != null && set.has(Number(m.id))));
    setMessages((prev) => prev.filter((m) => !(m.id != null && set.has(Number(m.id)))));
    return removed;
  }, []);

  /** The delete settled: ids stop being filtered (rollback passes the rows to restore). */
  const settleRemoval = useCallback((ids, restore) => {
    (ids || []).forEach((id) => removing.current.delete(Number(id)));
    if (restore && restore.length) {
      messagesRef.current = mergeMessages(messagesRef.current, restore);
      setMessages((prev) => mergeMessages(prev, restore));
    }
  }, []);

  const addOptimistic = useCallback((msg) => setMessages((prev) => [...prev, msg]), []);
  const resolveOptimistic = useCallback((clientId, saved) => {
    setMessages((prev) => {
      const rest = prev.filter((m) => m.client_id !== clientId);
      return saved ? mergeMessages(rest, [saved]) : rest;
    });
  }, []);
  const appendMessages = useCallback((list) => setMessages((prev) => mergeMessages(prev, list)), []);

  /** Persist "read up to the newest message". Returns true when something was written. */
  const markRead = useCallback(async () => {
    const last = lastServerId(messagesRef.current);
    if (!last || last <= lastMarked.current) return false;
    lastMarked.current = last;
    if (characterId) {
      await api(`${roomPath}/read-state`, { method: 'POST', body: { character_id: characterId, last_read_message_id: last } });
    } else {
      writeSeen(userId, campaignId, locationId, last);
    }
    return true;
  }, [api, roomPath, characterId, campaignId, locationId, userId]);

  return {
    messages,
    status,
    closedInfo,
    firstUnreadId,
    hasMore,
    loadingOlder,
    loadOlder,
    removeMessages,
    settleRemoval,
    reload: load,
    refresh,
    fetchSince,
    addOptimistic,
    resolveOptimistic,
    appendMessages,
    markRead,
  };
}
