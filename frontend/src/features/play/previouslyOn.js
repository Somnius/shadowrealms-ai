/**
 * "Previously on…" (0.27, docs/CHRONICLE.md): the recap of a room after 12 hours or more away.
 * The server keeps when each user was last in a room (…/chronicle/recap/visit) and builds the recap
 * from the stored player view only (…/chronicle/recap). Closing the card is remembered per room
 * here, until the next absence (a new `since`).
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { jumpToMessage } from '../chat/MessageActions';
import { splitChunks } from '../voice/readout';
import { getLanguage, t } from '../../i18n';

export const VISIT_EVERY_MS = 10 * 60 * 1000; // while the room stays open
const CLOSED_KEY = 'sr_recap_closed:';

const closedKey = (userId, campaignId, locationId) => `${CLOSED_KEY}${userId || 'anon'}:${campaignId}:${locationId}`;

export function readClosed(userId, campaignId, locationId) {
  try {
    return window.localStorage.getItem(closedKey(userId, campaignId, locationId));
  } catch {
    return null;
  }
}

export function writeClosed(userId, campaignId, locationId, since) {
  try {
    window.localStorage.setItem(closedKey(userId, campaignId, locationId), String(since || ''));
  } catch {
    /* private mode: not remembered */
  }
}

/** A recap worth showing: a stored digest (so_far) and at least one night. */
export const hasRecap = (r) => !!(r && r.so_far && Array.isArray(r.nights) && r.nights.length);

/** [{text, lang}] the phone voice reads: the heading, each night, then the story so far. */
export function recapParts(recap) {
  if (!hasRecap(recap)) return [];
  const lang = recap.lang === 'el' ? 'el' : 'en';
  const opts = { lng: lang };
  const texts = [t('play:recap.title', 'Previously on…', opts)];
  recap.nights.forEach((n) => {
    const head = n.title
      ? t('play:recap.nightTitled', 'Night {{n}}: {{title}}', { ...opts, n: n.night, title: n.title })
      : t('play:recap.night', 'Night {{n}}', { ...opts, n: n.night });
    texts.push([`${head.replace(/[.!?…]$/, '')}.`, ...(n.summary || [])].join(' '));
  });
  texts.push(`${t('play:recap.soFar', 'The story so far', opts)}. ${recap.so_far}`);
  return texts.flatMap((x) => splitChunks(x)).map((text) => ({ text, lang }));
}

/**
 * Scroll to a message, loading older history until it is there (the reply-quote jump, with paging).
 * loadOlder() loads a page; hasMore() -> more history on the server; isLoading() -> a page is on its
 * way (then wait and look again). It gives up only when there is no more history once loads settle.
 */
export async function jumpLoadingOlder(
  id,
  { loadOlder, hasMore, isLoading = () => false, jump = jumpToMessage, tick = () => new Promise((r) => setTimeout(r, 60)), maxTries = 80 },
) {
  if (id == null) return false;
  if (jump(id)) return true;
  for (let i = 0; i < maxTries; i += 1) {
    if (isLoading()) {
      await tick();
    } else {
      if (!hasMore()) break;
      await loadOlder();
      await tick();
    }
    if (jump(id)) return true;
  }
  return jump(id);
}

/**
 * The card's state for the open room. On opening a room: record the visit; when the server says an
 * absence of 12 hours or more began at `away_since` and the card wasn't closed for that absence,
 * load the recap and open the card if there is one. showNow() (the header button) loads the room's
 * recent nights when nothing is new.
 */
export function usePreviouslyOn({ api, campaignId, locationId, userId, enabled }) {
  const [recap, setRecap] = useState(null);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  // a token refresh gives api a new identity: kept in a ref so the room isn't "opened" again
  const apiRef = useRef(api);
  apiRef.current = api;
  const base = `/campaigns/${campaignId}/chronicle/recap`;

  const load = useCallback(
    async (recent) => {
      const r = await apiRef.current(`${base}?location_id=${locationId}&lang=${getLanguage()}${recent ? '&recent=1' : ''}`);
      return r.ok && r.data ? r.data : null;
    },
    [base, locationId],
  );

  useEffect(() => {
    setRecap(null);
    setOpen(false);
    if (!enabled || !campaignId || !locationId) return undefined;
    let live = true;
    let lastAway = null;
    const hidden = () => typeof document !== 'undefined' && document.visibilityState === 'hidden';
    // Each visit: when the server says a (new) absence of 12 hours or more began and the card wasn't
    // closed for it, load the recap and open the card. Also after a laptop wakes in a visible tab.
    const visit = async () => {
      const v = await apiRef.current(`${base}/visit`, { method: 'POST', body: { location_id: Number(locationId) } });
      const away = v && v.ok && v.data ? v.data.away_since : null;
      if (!live || !away || away === lastAway) return;
      lastAway = away;
      if (readClosed(userId, campaignId, locationId) === String(away)) return;
      const r = await load(false);
      if (!live || !hasRecap(r)) return;
      setRecap(r);
      setOpen(true);
    };
    visit();
    // a hidden tab sends no heartbeat, so the player can be away while it sits in the background
    const timer = setInterval(() => {
      if (!hidden()) visit();
    }, VISIT_EVERY_MS);
    const onVis = () => {
      if (!hidden()) visit();
    };
    if (typeof document !== 'undefined') document.addEventListener('visibilitychange', onVis);
    return () => {
      live = false;
      clearInterval(timer);
      if (typeof document !== 'undefined') document.removeEventListener('visibilitychange', onVis);
    };
  }, [campaignId, locationId, userId, enabled]); // eslint-disable-line react-hooks/exhaustive-deps

  const close = useCallback(() => {
    setOpen(false);
    if (recap && recap.since) writeClosed(userId, campaignId, locationId, recap.since);
  }, [recap, userId, campaignId, locationId]);

  /** Hide without remembering it as closed (a jump on phones): the header button brings it back. */
  const hide = useCallback(() => setOpen(false), []);

  /** The header button: true when there was something to show. */
  const showNow = useCallback(async () => {
    setLoading(true);
    try {
      const r = await load(true);
      if (!hasRecap(r)) return false;
      setRecap(r);
      setOpen(true);
      return true;
    } finally {
      setLoading(false);
    }
  }, [load]);

  /** startJob(chunk) for server voices: the server builds the text from the same recap. */
  const startJob = useCallback(
    (chunk) =>
      apiRef.current(`${base}/tts?lang=${getLanguage()}`, {
        method: 'POST',
        body: { location_id: Number(locationId), chunk, recent: !!(recap && recap.recent), recap_hash: recap ? recap.recap_hash : undefined },
      }),
    [base, locationId, recap],
  );

  return { recap, open, loading, close, hide, showNow, startJob };
}
