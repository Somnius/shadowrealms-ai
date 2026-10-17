import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useAuth } from './AuthContext';
import { apiFetch, getCurrentToken } from './http';

const ChroniclesContext = createContext(null);

/**
 * Every chronicle the user belongs to (GET /campaigns/, without the old for_active_character filter:
 * the global "active character" is gone from the UI; each card shows that chronicle's own character).
 * Shared by the rail, the hall and the play view. Refreshed when the window regains focus and every
 * minute while the tab is visible, so being added to a chronicle shows up without a reload.
 */
export const CHRONICLES_REFRESH_MS = 60000;
const COUNT_KEY = 'sr_chronicle_count';

/** How many chronicles the last visit had (placeholders while loading, no layout shift). */
function rememberedCount() {
  try {
    const n = Number(window.localStorage.getItem(COUNT_KEY));
    return Number.isFinite(n) && n >= 0 ? Math.min(n, 12) : 2;
  } catch {
    return 2;
  }
}

export function ChroniclesProvider({ children }) {
  const { token } = useAuth();
  const authed = !!token;
  const [chronicles, setChronicles] = useState([]);
  const [loaded, setLoaded] = useState(false);
  const lastJson = useRef('');
  const inflight = useRef(null);
  const lastLoadAt = useRef(0);

  // An explicit reload (after creating or changing a chronicle) always asks the server.
  const reload = useCallback(async () => {
    if (!authed) return [];
    const r = await apiFetch(getCurrentToken(), '/campaigns/');
    lastLoadAt.current = Date.now();
    const list = r.ok && Array.isArray(r.data) ? r.data : [];
    if (r.ok) {
      // Background refreshes usually return the same list: keep the old array (no re-render).
      const json = JSON.stringify(list);
      if (json !== lastJson.current) {
        lastJson.current = json;
        setChronicles(list);
      }
      try {
        window.localStorage.setItem(COUNT_KEY, String(list.length));
      } catch {
        /* storage blocked: placeholders fall back to 2 */
      }
    }
    setLoaded(true);
    return list;
  }, [authed]);

  // Background refreshes (mount, focus, the timer) share one request: at page load the mount and
  // the window's first focus event both ask, and one answer serves both.
  const refresh = useCallback(() => {
    if (inflight.current) return inflight.current;
    inflight.current = reload().finally(() => {
      inflight.current = null;
    });
    return inflight.current;
  }, [reload]);

  useEffect(() => {
    if (!authed) return undefined;
    const visible = () => typeof document === 'undefined' || document.visibilityState !== 'hidden';
    const onFocus = () => {
      // A focus right after a load (the page just opened) has nothing new to fetch.
      if (getCurrentToken() && Date.now() - lastLoadAt.current > 5000) refresh();
    };
    const onVisible = () => {
      if (visible()) onFocus();
    };
    window.addEventListener('focus', onFocus);
    document.addEventListener('visibilitychange', onVisible);
    const timer = setInterval(() => {
      if (visible()) onFocus();
    }, CHRONICLES_REFRESH_MS);
    return () => {
      window.removeEventListener('focus', onFocus);
      document.removeEventListener('visibilitychange', onVisible);
      clearInterval(timer);
    };
  }, [authed, refresh]);

  useEffect(() => {
    if (authed) refresh();
    else {
      lastJson.current = '';
      setChronicles([]);
      setLoaded(false);
    }
  }, [authed, refresh]);

  const byId = useCallback((id) => chronicles.find((c) => String(c.id) === String(id)) || null, [chronicles]);

  const [expectedCount] = useState(rememberedCount);
  const value = useMemo(() => ({ chronicles, loaded, reload, refresh, byId, expectedCount }), [chronicles, loaded, reload, refresh, byId, expectedCount]);
  return <ChroniclesContext.Provider value={value}>{children}</ChroniclesContext.Provider>;
}

export function useChronicles() {
  const ctx = useContext(ChroniclesContext);
  if (!ctx) throw new Error('useChronicles() needs a <ChroniclesProvider>');
  return ctx;
}
