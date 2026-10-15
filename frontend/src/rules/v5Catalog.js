/**
 * Loads the V5 creation catalog (GET /api/rules/v5/catalog) once per page load and hands it to
 * the rules registry (characterSheet/v5/rulesData.js). Without it the forge keeps working on
 * src/rules/v5.json.
 */
import { useEffect, useState } from 'react';
import { apiFetch, getCurrentToken } from '../app/http';
import { applyV5Catalog, getV5Rules, v5RulesVersion } from '../characterSheet/v5/rulesData';

let pending = null;

/** Fetch the catalog and apply it (once; later calls share the same promise). */
export function loadV5Catalog(token = getCurrentToken()) {
  if (getV5Rules().source === 'catalog') return Promise.resolve(true);
  if (!pending) {
    pending = apiFetch(token, '/rules/v5/catalog')
      .then((r) => {
        if (r.ok && Array.isArray(r.data.clans) && r.data.clans.length) {
          applyV5Catalog(r.data);
          return true;
        }
        pending = null; // try again next time
        return false;
      })
      .catch(() => {
        pending = null;
        return false;
      });
  }
  return pending;
}

/** Loads the catalog and re-renders the caller when it arrives. Returns the rules version. */
export function useV5Catalog(token) {
  const [version, setVersion] = useState(v5RulesVersion());
  useEffect(() => {
    let alive = true;
    loadV5Catalog(token).then(() => {
      if (alive) setVersion(v5RulesVersion());
    });
    return () => {
      alive = false;
    };
  }, [token]);
  return version;
}
