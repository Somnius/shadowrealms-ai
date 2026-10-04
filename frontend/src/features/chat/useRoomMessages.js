import { useCallback, useEffect, useRef, useState } from 'react';
import { readLocal, writeLocal } from '../../app/hooks';
import { isMarker } from './messageModel';

export const INITIAL_LIMIT = 150;

const seenKey = (cid, lid) => `sr_seen_${cid}_${lid}`;

export function readSeen(campaignId, locationId) {
  const v = parseInt(readLocal(seenKey(campaignId, locationId), '0'), 10);
  return Number.isFinite(v) ? v : 0;
}

export function writeSeen(campaignId, locationId, id) {
  if (id > readSeen(campaignId, locationId)) writeLocal(seenKey(campaignId, locationId), id);
}

/** "12:340,13:0" for GET /unread?seen= (players without a character keep read state in this browser). */
export function seenParam(campaignId, locations) {
  return (locations || []).map((l) => `${l.id}:${readSeen(campaignId, l.id)}`).join(',');
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
  const messagesRef = useRef(messages);
  messagesRef.current = messages;
  const roomRef = useRef(`${campaignId}:${locationId}`);
  const inflight = useRef(false);
  const lastMarked = useRef(0);

  const roomPath = `/campaigns/${campaignId}/locations/${locationId}`;

  const load = useCallback(async () => {
    const key = `${campaignId}:${locationId}`;
    roomRef.current = key;
    setStatus('loading');
    setClosedInfo(null);
    setFirstUnreadId(null);
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
      const seen = readSeen(campaignId, locationId);
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
    setStatus('ready');
  }, [api, roomPath, campaignId, locationId, characterId, userId]);

  useEffect(() => {
    setMessages([]);
    if (enabled && locationId) load();
    else setStatus('loading');
  }, [load, enabled, locationId]);

  /** Fetch rows newer than what we have (SSE "changed" / poll tick). */
  const fetchSince = useCallback(async () => {
    if (inflight.current || !enabled) return;
    const key = roomRef.current;
    const since = lastServerId(messagesRef.current);
    inflight.current = true;
    try {
      const r = await api(since > 0 ? `${roomPath}?since_id=${since}&limit=200` : `${roomPath}?recent=1&limit=${INITIAL_LIMIT}`);
      if (roomRef.current !== key || !r.ok || !Array.isArray(r.data) || r.data.length === 0) return;
      setMessages((prev) => mergeMessages(prev, r.data));
    } finally {
      inflight.current = false;
    }
  }, [api, roomPath, enabled]);

  /** Full reload without resetting the divider (deletes / /ai clean). */
  const refresh = useCallback(async () => {
    const key = roomRef.current;
    const r = await api(`${roomPath}?recent=1&limit=${INITIAL_LIMIT}`);
    if (roomRef.current !== key || !r.ok || !Array.isArray(r.data)) return;
    setMessages((prev) => [...r.data, ...prev.filter((m) => m.temp && m.id == null)]);
  }, [api, roomPath]);

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
      writeSeen(campaignId, locationId, last);
    }
    return true;
  }, [api, roomPath, characterId, campaignId, locationId]);

  return {
    messages,
    status,
    closedInfo,
    firstUnreadId,
    reload: load,
    refresh,
    fetchSince,
    addOptimistic,
    resolveOptimistic,
    appendMessages,
    markRead,
  };
}
