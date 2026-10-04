import { useEffect, useState } from 'react';

/** Live media query (false when matchMedia is missing, e.g. jsdom). */
export function useMediaQuery(query) {
  const get = () =>
    typeof window !== 'undefined' && typeof window.matchMedia === 'function'
      ? !!window.matchMedia(query).matches
      : false;
  const [matches, setMatches] = useState(get);
  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return undefined;
    const mql = window.matchMedia(query);
    const on = () => setMatches(!!mql.matches);
    on();
    if (mql.addEventListener) mql.addEventListener('change', on);
    else if (mql.addListener) mql.addListener(on);
    return () => {
      if (mql.removeEventListener) mql.removeEventListener('change', on);
      else if (mql.removeListener) mql.removeListener(on);
    };
  }, [query]);
  return matches;
}

/** < 768 px: rail + channels and the member panel move into drawers. */
export function useIsMobile() {
  return useMediaQuery('(max-width: 767px)');
}

/** Right panel docks from 1024 px; between 768 and 1024 it is a drawer. */
export function useIsWide() {
  return useMediaQuery('(min-width: 1024px)');
}

/** Best-effort localStorage helpers (private mode, quota). */
export function readLocal(key, fallback = null) {
  try {
    const v = window.localStorage.getItem(key);
    return v == null ? fallback : v;
  } catch {
    return fallback;
  }
}

export function writeLocal(key, value) {
  try {
    if (value == null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, String(value));
  } catch {
    /* ignore */
  }
}

/** 'vampire' | 'werewolf' | 'mage' | 'wraith' | 'changeling' | null from a game_system string. */
export function lineOf(gameSystem) {
  const gs = String(gameSystem || '').toLowerCase();
  if (/vampire|masquerade|vtm/.test(gs)) return 'vampire';
  if (/werewolf|apocalypse|garou|wta/.test(gs)) return 'werewolf';
  if (/mage|ascension|mta/.test(gs)) return 'mage';
  if (/wraith|oblivion/.test(gs)) return 'wraith';
  if (/changeling|dreaming/.test(gs)) return 'changeling';
  return null;
}

const LINE_TITLES = {
  vampire: 'Vampire: The Masquerade',
  werewolf: 'Werewolf: The Apocalypse',
  mage: 'Mage: The Ascension',
  wraith: 'Wraith: The Oblivion',
  changeling: 'Changeling: The Dreaming',
};

/** Game line title for a game_system value ("vampire" → "Vampire: The Masquerade"; titles stay English). */
export function gameSystemTitle(gameSystem) {
  const line = lineOf(gameSystem);
  return line ? LINE_TITLES[line] : String(gameSystem || '');
}

export function lineGlyph(gameSystem) {
  const line = lineOf(gameSystem);
  return line ? `line-${line}` : 'logo-mark';
}

/** Storyteller of a chronicle = its creator. Site admins/helpers count as staff. */
export function isStoryteller(user, campaign) {
  return !!user && !!campaign && campaign.created_by != null && String(campaign.created_by) === String(user.id);
}

export function canUseStaffVoice(user, campaign) {
  return !!user && (user.role === 'admin' || user.role === 'helper' || isStoryteller(user, campaign));
}

/** Best-effort sessionStorage helpers (this tab only; survives remounts and reloads). */
export function readSession(key, fallback = null) {
  try {
    const v = window.sessionStorage.getItem(key);
    return v == null ? fallback : v;
  } catch {
    return fallback;
  }
}

export function writeSession(key, value) {
  try {
    if (value == null || value === '') window.sessionStorage.removeItem(key);
    else window.sessionStorage.setItem(key, String(value));
  } catch {
    /* ignore */
  }
}

/** Removes every sessionStorage key starting with `prefix` (e.g. drafts at logout). */
export function clearSessionPrefix(prefix) {
  try {
    const keys = [];
    for (let i = 0; i < window.sessionStorage.length; i += 1) {
      const k = window.sessionStorage.key(i);
      if (k && k.startsWith(prefix)) keys.push(k);
    }
    keys.forEach((k) => window.sessionStorage.removeItem(k));
  } catch {
    /* ignore */
  }
}

/** Composer drafts: one per user and room, in this tab only. */
export const DRAFT_PREFIX = 'sr_draft_';
