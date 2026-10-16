/**
 * Language override (docs/VOICE.md §8): captions for a room. Translations are made on the server
 * ahead of time; this asks for the room's visible messages that need one (or carry the speaker's
 * original) and asks again while some are still being translated.
 */
import { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { guessLang } from './readout';

export const POLL_MS = 3000;
export const MAX_ROUNDS = 8; // every 3 s for ~24 s, then slower while the translator is behind
export const SLOW_POLL_MS = 15000;
export const MAX_SLOW_ROUNDS = 40; // ~10 min more, then wait for the next message
const WINDOW = 60;

export const TranslationsContext = createContext(null);
export const useTranslationsContext = () => useContext(TranslationsContext);

const skip = (m) => {
  const k = String(m.ai_message_kind || '').toLowerCase();
  return m.temp || m.id == null || k.startsWith('dice_') || k.startsWith('slash_') || m.message_type === 'system';
};

export const msgLang = (m) => m.lang || guessLang(m.content);

/** Ids of messages to ask about: in another language than the player hears, or with an original. */
export function wantedIds(messages, hearLang, have) {
  const hear = hearLang === 'en' || hearLang === 'el' ? hearLang : null;
  return (messages || [])
    .filter((m) => !skip(m))
    .filter((m) => (m.orig_lang || (hear && msgLang(m) !== hear)) && !(have && have[m.id]))
    .map((m) => Number(m.id))
    .slice(-WINDOW);
}

/**
 * {id: {lang: {text, kind}}} for the room. hearLang: the player's hear_lang ('written'|'en'|'el').
 */
export function useRoomTranslations({ api, campaignId, locationId, messages, hearLang }) {
  const [map, setMap] = useState({});
  const mapRef = useRef(map);
  mapRef.current = map;
  const rounds = useRef(0);
  const ids = useMemo(() => wantedIds(messages, hearLang, map), [messages, hearLang, map]);
  const key = ids.join(',');

  useEffect(() => {
    setMap({});
  }, [campaignId, locationId, hearLang]);

  useEffect(() => {
    rounds.current = 0;
  }, [key]);

  useEffect(() => {
    if (!api || !campaignId || !locationId || !key) return undefined;
    let live = true;
    let timer = null;
    const lang = hearLang === 'en' || hearLang === 'el' ? hearLang : '';
    const ask = async () => {
      const r = await api(`/voice/translations?campaign_id=${campaignId}&location_id=${locationId}&ids=${key}${lang ? `&lang=${lang}` : ''}`);
      if (!live || !r.ok) return;
      const got = (r.data && r.data.translations) || {};
      const done = {};
      key.split(',').forEach((id) => {
        if (got[id]) done[id] = got[id];
        // nothing to wait for: remember it so it is not asked again
        else if (!((r.data && r.data.pending) || []).map(String).includes(id)) done[id] = {};
      });
      if (Object.keys(done).length) setMap((prev) => ({ ...prev, ...done }));
      rounds.current += 1;
      if ((r.data.pending || []).length && rounds.current < MAX_ROUNDS + MAX_SLOW_ROUNDS) {
        timer = setTimeout(ask, rounds.current < MAX_ROUNDS ? POLL_MS : SLOW_POLL_MS);
      }
    };
    ask();
    return () => {
      live = false;
      if (timer) clearTimeout(timer);
    };
  }, [api, campaignId, locationId, key, hearLang]);

  return map;
}

/**
 * What a row shows: null when there is nothing to swap, else {body, bodyLang, caption,
 * captionLang, label}. The body is in the player's hear-in language (or, "as written", the
 * message as sent); the caption is the other text. label: 'original' (the caption is what the
 * speaker wrote or said), 'yourOriginal' (the same, for your own line) or 'sent' (the caption is
 * the line as it was sent, the body being the speaker's own original words).
 */
export function captionView(message, rows, hearLang, userId) {
  if (!rows) return null;
  const lang = msgLang(message);
  const own = userId != null && String(message.user_id) === String(userId);
  const hear = hearLang === 'en' || hearLang === 'el' ? hearLang : null;
  if (hear && hear !== lang && rows[hear]) {
    const label = rows[hear].kind === 'original' ? 'sent' : 'original';
    return { body: rows[hear].text, bodyLang: hear, caption: message.content, captionLang: lang, label };
  }
  const orig = message.orig_lang && rows[message.orig_lang];
  if (orig && orig.kind === 'original') {
    return { body: message.content, bodyLang: lang, caption: orig.text, captionLang: message.orig_lang, label: own ? 'yourOriginal' : 'original' };
  }
  return null;
}

/** Text a listener hears for a message: the translation in hear_lang when there is one. */
export function hearText(message, rows, hearLang) {
  const hear = hearLang === 'en' || hearLang === 'el' ? hearLang : null;
  if (hear && rows && rows[hear] && hear !== msgLang(message)) return { content: rows[hear].text, lang: hear };
  return null;
}
