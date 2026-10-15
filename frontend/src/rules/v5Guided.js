/**
 * Loads the guided-mode questions (GET /api/rules/v5/guided, docs/rules/v5/guided/questions.json)
 * together with the V5 catalog, since the guide suggests catalog clans and predator types.
 * No module cache: the server sends an ETag, so the browser revalidates instead of downloading.
 */
import { useEffect, useState } from 'react';
import { apiFetch, getCurrentToken } from '../app/http';
import { loadV5Catalog } from './v5Catalog';

/** The question set, or null when the server has none (or can't be reached). */
export async function fetchV5Guided(token = getCurrentToken()) {
  try {
    const r = await apiFetch(token, '/rules/v5/guided');
    return r.ok && Array.isArray(r.data?.questions) && r.data.questions.length ? r.data : null;
  } catch {
    return null;
  }
}

/** { status: 'loading' | 'ready' | 'error', set }: ready once the questions and the catalog are in. */
export function useV5Guided(token) {
  const [state, setState] = useState({ status: 'loading', set: null });
  useEffect(() => {
    let alive = true;
    // Without the catalog the guide still works on the rules fallback (fewer clans).
    Promise.all([fetchV5Guided(token), loadV5Catalog(token)]).then(([set]) => {
      if (alive) setState(set ? { status: 'ready', set } : { status: 'error', set: null });
    });
    return () => {
      alive = false;
    };
  }, [token]);
  return state;
}
