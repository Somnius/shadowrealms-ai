import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useAuth } from './AuthContext';
import { apiFetch } from './http';

const ChroniclesContext = createContext(null);

/**
 * Every chronicle the user belongs to (GET /campaigns/, without the old for_active_character filter:
 * the global "active character" is gone from the UI; each card shows that chronicle's own character).
 * Shared by the rail, the hall and the play view.
 */
export function ChroniclesProvider({ children }) {
  const { token } = useAuth();
  const [chronicles, setChronicles] = useState([]);
  const [loaded, setLoaded] = useState(false);

  const reload = useCallback(async () => {
    if (!token) return [];
    const r = await apiFetch(token, '/campaigns/');
    const list = r.ok && Array.isArray(r.data) ? r.data : [];
    if (r.ok) setChronicles(list);
    setLoaded(true);
    return list;
  }, [token]);

  useEffect(() => {
    if (token) reload();
    else {
      setChronicles([]);
      setLoaded(false);
    }
  }, [token, reload]);

  const byId = useCallback((id) => chronicles.find((c) => String(c.id) === String(id)) || null, [chronicles]);

  const value = useMemo(() => ({ chronicles, loaded, reload, byId }), [chronicles, loaded, reload, byId]);
  return <ChroniclesContext.Provider value={value}>{children}</ChroniclesContext.Provider>;
}

export function useChronicles() {
  const ctx = useContext(ChroniclesContext);
  if (!ctx) throw new Error('useChronicles() needs a <ChroniclesProvider>');
  return ctx;
}
