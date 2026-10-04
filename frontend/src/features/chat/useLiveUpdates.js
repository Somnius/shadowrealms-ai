import { useEffect, useRef, useState } from 'react';
import { API_URL } from '../../app/http';
import { LiveConnection } from './liveConnection';

/**
 * One live connection per open chronicle. Handlers are read through a ref, so changing them never
 * reconnects. Returns the mode: 'connecting' | 'live' | 'polling' | 'closed'.
 */
export function useLiveUpdates({ api, campaignId, onChanged, onPoll, enabled = true }) {
  const handlers = useRef({ onChanged, onPoll });
  handlers.current = { onChanged, onPoll };
  const [mode, setMode] = useState('connecting');

  useEffect(() => {
    if (!enabled || !campaignId) return undefined;
    const conn = new LiveConnection({
      getTicket: async () => {
        const r = await api(`/campaigns/${campaignId}/events/ticket`, { method: 'POST' });
        return r.ok ? r.data.ticket : null;
      },
      makeUrl: (ticket) => `${API_URL}/campaigns/${campaignId}/events?ticket=${encodeURIComponent(ticket)}`,
      onChanged: (ev) => handlers.current.onChanged && handlers.current.onChanged(ev),
      onHello: () => handlers.current.onPoll && handlers.current.onPoll(),
      onPoll: () => handlers.current.onPoll && handlers.current.onPoll(),
      onModeChange: setMode,
    });
    conn.start();
    return () => conn.stop();
  }, [api, campaignId, enabled]);

  return mode;
}
