/**
 * Listen mode for a room (docs/VOICE.md): the ear button turns it on (that tap unlocks speech on
 * phones), new messages that pass the read-out rules are queued and spoken with the phone's own
 * voices or the server's. Going to the background pauses; only a tap resumes (never from
 * visibilitychange). Read along (0.22): lines are said chunk by chunk, the message being read is
 * highlighted and followed, "Read this" / "Read from here" from the message menu, and a catch-up
 * choice when listening starts.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { readoutKind, shouldRead, spokenParts } from './readout';
import { createSpeechQueue } from './speechQueue';
import { hasPhoneVoices, phoneEngine, unlockPhoneVoice } from './phoneVoice';
import { makeRoomAudio, serverEngine, switchingEngine, unlockRoomAudio } from './serverVoice';
import { diceAnimationId, markersById, presentSpeaker } from '../chat/messageModel';
import { hearText } from './translations';
import { getLanguage } from '../../i18n';

export const CATCH_UP = 3;
export const CATCH_UP_CHOICES = ['last3', 'last10', 'resume', 'none'];
export const CHOICE_KEY = 'sr_voice_catchup';
export const LAST_READ_KEY = 'sr_voice_last_read:';
export const READING_CLASS = 'sr-msg--reading';

const idNum = (m) => Number(m && m.id) || 0;
const maxId = (messages) => (messages || []).reduce((a, m) => Math.max(a, idNum(m)), 0);

const store = {
  get(k) {
    try {
      return window.localStorage.getItem(k);
    } catch {
      return null;
    }
  },
  set(k, v) {
    try {
      window.localStorage.setItem(k, String(v));
    } catch {
      /* private mode: not remembered */
    }
  },
};

export const rememberedChoice = () => {
  const c = store.get(CHOICE_KEY);
  return CATCH_UP_CHOICES.includes(c) ? c : 'last3';
};
export const lastReadId = (roomKey) => Number(store.get(LAST_READ_KEY + roomKey)) || 0;

/** The readable messages a catch-up choice reads, oldest first. */
export function catchUpList(readable, choice, lastRead) {
  if (choice === 'last10') return readable.slice(-10);
  if (choice === 'resume') return readable.filter((m) => idNum(m) > (Number(lastRead) || 0));
  if (choice === 'none') return [];
  return readable.slice(-CATCH_UP);
}

/**
 * A queue item. getHeard(msg) -> {content, lang} | null is the translation in the player's
 * hear-in language (docs/VOICE.md §8); it is read when the line is spoken, so a translation that
 * arrives while the line waits in the queue is used. Server voices ask the server instead.
 * opts: { listenLang, getMarker(msg) } (dice and roll requests in the listener's language).
 */
export function toItem(msg, getHeard, opts = {}) {
  const heard = () => (getHeard && getHeard(msg)) || null;
  const parts = (useHeard = true) => {
    const h = useHeard ? heard() : null;
    const said = h ? { ...msg, content: h.content, lang: h.lang } : msg;
    const listenLang = typeof opts.listenLang === 'function' ? opts.listenLang() : opts.listenLang;
    return spokenParts(said, { listenLang, marker: opts.getMarker ? opts.getMarker(msg) : null, rollSource: msg.content });
  };
  return {
    id: msg.id,
    get parts() {
      return parts();
    },
    // the line without the translation: the phone falls back to this when the server spoke the original
    get originalParts() {
      return parts(false);
    },
    get text() {
      return parts().map((p) => p.text).join(' ');
    },
    get lang() {
      const p = parts();
      return p.length ? p[0].lang : 'en';
    },
    get listenLang() {
      return typeof opts.listenLang === 'function' ? opts.listenLang() : opts.listenLang;
    },
    speaker: presentSpeaker(msg).name,
  };
}

const reducedMotion = () => {
  try {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  } catch {
    return false;
  }
};

export function useListen({ api, campaignId, roomKey, messages, status, userId, engine, onFallback, translationsRef }) {
  const [settings, setSettings] = useState(null);
  const [chronicle, setChronicle] = useState(null);
  const [rules, setRules] = useState(null);
  const [on, setOn] = useState(false);
  const [catchUp, setCatchUp] = useState(0); // > 0: the catch-up choice is shown
  const [follow, setFollow] = useState(true);
  const settingsRef = useRef(null);
  settingsRef.current = settings;
  const roomRef = useRef(roomKey);
  roomRef.current = roomKey;
  const messagesRef = useRef(messages);
  messagesRef.current = messages;
  const audioRef = useRef(null);
  const getHeard = useCallback(
    (msg) => hearText(msg, translationsRef && translationsRef.current ? translationsRef.current[msg.id] : null, (settingsRef.current || {}).hear_lang),
    [translationsRef],
  );
  const itemOpts = useMemo(
    () => ({
      listenLang: () => {
        const h = (settingsRef.current || {}).hear_lang;
        return h === 'en' || h === 'el' ? h : getLanguage();
      },
      getMarker: (msg) => {
        const id = diceAnimationId(msg);
        return id ? markersById(messagesRef.current)[id] || null : null;
      },
    }),
    [],
  );
  const item = useCallback((m) => toItem(m, getHeard, itemOpts), [getHeard, itemOpts]);
  const fallbackRef = useRef(onFallback);
  fallbackRef.current = onFallback;
  const queue = useMemo(() => {
    const onDone = (it) => {
      if (Number(it.id) > lastReadId(roomRef.current)) store.set(LAST_READ_KEY + roomRef.current, it.id);
    };
    if (engine) return createSpeechQueue(engine, { onDone });
    const getSettings = () => settingsRef.current;
    let server = null;
    const phone = phoneEngine(getSettings, () => server);
    server = serverEngine({
      api,
      getAudio: () => audioRef.current || (audioRef.current = makeRoomAudio()),
      getSettings,
      fallback: phone,
      onFallback: (e) => fallbackRef.current && fallbackRef.current(e),
    });
    return createSpeechQueue(switchingEngine(getSettings, server, phone), { onDone });
  }, [engine, api]);
  const [qs, setQs] = useState(queue.state());
  const lastId = useRef(0);
  const primed = useRef(null);
  const lastRoom = useRef(null);

  useEffect(() => queue.subscribe(setQs), [queue]);
  useEffect(() => () => queue.stop(), [queue]);
  useEffect(
    () => () => {
      const el = audioRef.current;
      audioRef.current = null;
      if (el && el.parentNode) el.parentNode.removeChild(el);
    },
    [],
  );

  useEffect(() => {
    let live = true;
    if (!campaignId) return undefined;
    Promise.all([api('/voice/settings'), api(`/campaigns/${campaignId}/voice-settings`)]).then(([u, c]) => {
      if (!live) return;
      if (u.ok) setSettings(u.data);
      if (c.ok) {
        setRules(c.data.effective);
        setChronicle(c.data.settings || null);
      }
    });
    return () => {
      live = false;
    };
  }, [api, campaignId]);

  // A new room: what is already there is not news. Listening carries on into the new room.
  useEffect(() => {
    if (status !== 'ready') {
      primed.current = null; // re-prime when the (new) room has loaded
      return;
    }
    if (primed.current === roomKey) return;
    const moved = lastRoom.current !== null && lastRoom.current !== roomKey;
    primed.current = roomKey;
    lastRoom.current = roomKey;
    lastId.current = maxId(messages);
    if (moved) {
      queue.stop();
      setCatchUp(0);
    }
  }, [status, roomKey, messages, queue]);

  useEffect(() => {
    if (primed.current !== roomKey) return;
    const fresh = (messages || []).filter((m) => idNum(m) > lastId.current);
    if (!fresh.length) return;
    if (on && !rules) return; // wait for the read-out rules, so opt-outs apply from the first line
    lastId.current = maxId(messages);
    if (!on) return;
    queue.enqueue(fresh.filter((m) => shouldRead(m, rules, userId)).map(item));
  }, [messages, on, rules, userId, queue, roomKey, item]);


  // Read along: the message being read is marked (CSS class) and, while following, scrolled to.
  const readingId = qs.current ? qs.current.id : null;
  useEffect(() => {
    if (readingId == null || typeof document === 'undefined') return undefined;
    const el = document.getElementById(`msg-${readingId}`);
    if (!el) return undefined;
    el.classList.add(READING_CLASS);
    return () => el.classList.remove(READING_CLASS);
  }, [readingId, messages]);
  const partIndex = qs.part ? qs.part.index : -1;
  useEffect(() => {
    if (readingId == null || !follow || typeof document === 'undefined') return;
    const el = document.getElementById(`msg-${readingId}`);
    if (el && typeof el.scrollIntoView === 'function') el.scrollIntoView({ block: 'nearest', behavior: reducedMotion() ? 'auto' : 'smooth' });
  }, [readingId, partIndex, follow]);
  // Scrolling by hand (wheel, finger, keys) pauses follow until "Follow" is tapped.
  const active = on || !!qs.current || qs.queued > 0;
  useEffect(() => {
    if (!active || typeof document === 'undefined') return undefined;
    const onVis = () => {
      if (document.visibilityState === 'hidden') queue.hide();
    };
    document.addEventListener('visibilitychange', onVis);
    return () => document.removeEventListener('visibilitychange', onVis);
  }, [active, queue]);
  useEffect(() => {
    if (!active || typeof document === 'undefined') return undefined;
    const list = document.querySelector('.sr-chat__list');
    if (!list) return undefined;
    const stop = () => setFollow(false);
    const onKey = (e) => {
      if (['PageUp', 'PageDown', 'ArrowUp', 'ArrowDown', 'Home', 'End'].includes(e.key)) stop();
    };
    list.addEventListener('wheel', stop, { passive: true });
    list.addEventListener('touchmove', stop, { passive: true });
    list.addEventListener('keydown', onKey);
    return () => {
      list.removeEventListener('wheel', stop);
      list.removeEventListener('touchmove', stop);
      list.removeEventListener('keydown', onKey);
    };
  }, [active]);

  const readable = useCallback(() => (messages || []).filter((m) => shouldRead(m, rules, userId)), [messages, rules, userId]);

  const unlock = useCallback(() => {
    unlockPhoneVoice(); // inside the tap
    if (settingsRef.current && settingsRef.current.tts_source === 'server') {
      // the room's <audio> may only start from a tap on iOS: touch it now, inside this one
      unlockRoomAudio(audioRef.current || (audioRef.current = makeRoomAudio()));
    }
  }, []);

  const toggle = useCallback(() => {
    if (on) {
      queue.stop();
      setCatchUp(0);
      setOn(false);
      return;
    }
    unlock();
    lastId.current = maxId(messages);
    setCatchUp(readable().length);
    setFollow(true);
    setOn(true);
  }, [on, queue, messages, readable, unlock]);

  /** The catch-up choice: 'last3' | 'last10' | 'resume' | 'none'; remembered for next time. */
  const chooseCatchUp = useCallback(
    (choice) => {
      const c = CATCH_UP_CHOICES.includes(choice) ? choice : 'last3';
      store.set(CHOICE_KEY, c);
      queue.enqueue(catchUpList(readable(), c, lastReadId(roomKey)).map(item));
      setCatchUp(0);
    },
    [queue, readable, item, roomKey],
  );

  /** "Read this" / "Read from here" (message menu): works with listening off too. */
  const readFrom = useCallback(
    (msg, onwards = false) => {
      if (!msg || !readoutKind(msg)) return;
      unlock();
      const later = onwards ? readable().filter((m) => idNum(m) > idNum(msg)) : [];
      setCatchUp(0);
      setFollow(true);
      queue.play([msg, ...later].map(item));
    },
    [queue, readable, item, unlock],
  );

  const source = settings ? settings.tts_source : 'phone';
  const available = source !== 'off' && (source === 'server' || hasPhoneVoices());
  return {
    settings,
    chronicle,
    available,
    on,
    active,
    toggle,
    catchUp,
    catchUpChoice: rememberedChoice(),
    chooseCatchUp,
    acceptCatchUp: () => chooseCatchUp(rememberedChoice()),
    declineCatchUp: () => setCatchUp(0),
    readFrom,
    canRead: (msg) => available && !!msg && msg.id != null && !msg.temp && !!readoutKind(msg) && !!String(msg.content || '').trim(),
    follow,
    resumeFollow: () => setFollow(true),
    state: qs,
    pause: queue.pause,
    resume: queue.resume,
    skip: queue.skip,
    stop: queue.stop,
  };
}
