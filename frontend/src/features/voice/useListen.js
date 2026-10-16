/**
 * Listen mode for a room (docs/VOICE.md): the ear button turns it on (that tap unlocks speech on
 * phones), new messages that pass the read-out rules are queued and spoken with the phone's own
 * voices. Going to the background pauses; only a tap resumes (never from visibilitychange).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { guessLang, shouldRead, spokenText } from './readout';
import { createSpeechQueue } from './speechQueue';
import { hasPhoneVoices, phoneEngine, unlockPhoneVoice } from './phoneVoice';
import { makeRoomAudio, serverEngine, switchingEngine } from './serverVoice';
import { presentSpeaker } from '../chat/messageModel';
import { hearText } from './translations';

export const CATCH_UP = 3;

const idNum = (m) => Number(m && m.id) || 0;
const maxId = (messages) => (messages || []).reduce((a, m) => Math.max(a, idNum(m)), 0);

/**
 * A queue item. getHeard(msg) -> {content, lang} | null is the translation in the player's
 * hear-in language (docs/VOICE.md §8); it is read when the line is spoken, so a translation that
 * arrives while the line waits in the queue is used. Server voices ask the server instead.
 */
export function toItem(msg, getHeard) {
  const heard = () => (getHeard && getHeard(msg)) || null;
  const said = () => {
    const h = heard();
    return h ? { ...msg, content: h.content, lang: h.lang } : msg;
  };
  return {
    id: msg.id,
    get text() {
      return spokenText(said());
    },
    get lang() {
      const m = said();
      return m.lang || guessLang(m.content);
    },
    speaker: presentSpeaker(msg).name,
  };
}

export function useListen({ api, campaignId, roomKey, messages, status, userId, engine, onFallback, translationsRef }) {
  const [settings, setSettings] = useState(null);
  const [chronicle, setChronicle] = useState(null);
  const [rules, setRules] = useState(null);
  const [on, setOn] = useState(false);
  const [catchUp, setCatchUp] = useState(0);
  const settingsRef = useRef(null);
  settingsRef.current = settings;
  const audioRef = useRef(null);
  const getHeard = useCallback(
    (msg) => hearText(msg, translationsRef && translationsRef.current ? translationsRef.current[msg.id] : null, (settingsRef.current || {}).hear_lang),
    [translationsRef],
  );
  const fallbackRef = useRef(onFallback);
  fallbackRef.current = onFallback;
  const queue = useMemo(() => {
    if (engine) return createSpeechQueue(engine);
    const getSettings = () => settingsRef.current;
    const phone = phoneEngine(getSettings);
    const server = serverEngine({
      api,
      getAudio: () => audioRef.current || (audioRef.current = makeRoomAudio()),
      getSettings,
      fallback: phone,
      onFallback: (e) => fallbackRef.current && fallbackRef.current(e),
    });
    return createSpeechQueue(switchingEngine(getSettings, server, phone));
  }, [engine, api]);
  const [qs, setQs] = useState(queue.state());
  const lastId = useRef(0);
  const primed = useRef(null);
  const lastRoom = useRef(null);

  useEffect(() => queue.subscribe(setQs), [queue]);
  useEffect(() => () => queue.stop(), [queue]);

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
    queue.enqueue(fresh.filter((m) => shouldRead(m, rules, userId)).map((m) => toItem(m, getHeard)));
  }, [messages, on, rules, userId, queue, roomKey, getHeard]);

  useEffect(() => {
    if (!on || typeof document === 'undefined') return undefined;
    const onVis = () => {
      if (document.visibilityState === 'hidden') queue.hide();
    };
    document.addEventListener('visibilitychange', onVis);
    return () => document.removeEventListener('visibilitychange', onVis);
  }, [on, queue]);

  const readable = useCallback(() => (messages || []).filter((m) => shouldRead(m, rules, userId)), [messages, rules, userId]);

  const toggle = useCallback(() => {
    if (on) {
      queue.stop();
      setCatchUp(0);
      setOn(false);
      return;
    }
    unlockPhoneVoice(); // inside the tap
    if (settingsRef.current && settingsRef.current.tts_source === 'server') {
      // the room's <audio> may only start from a tap on iOS: touch it now, inside this one
      const el = audioRef.current || (audioRef.current = makeRoomAudio());
      try {
        const p = el && el.play();
        if (p && p.catch) p.catch(() => {});
      } catch {
        /* nothing loaded yet */
      }
    }
    lastId.current = maxId(messages);
    setCatchUp(Math.min(CATCH_UP, readable().length));
    setOn(true);
  }, [on, queue, messages, readable]);

  const acceptCatchUp = useCallback(() => {
    queue.enqueue(readable().slice(-CATCH_UP).map((m) => toItem(m, getHeard)));
    setCatchUp(0);
  }, [queue, readable, getHeard]);

  const source = settings ? settings.tts_source : 'phone';
  const available = source !== 'off' && (source === 'server' || hasPhoneVoices());
  return {
    settings,
    chronicle,
    available,
    on,
    toggle,
    catchUp,
    acceptCatchUp,
    declineCatchUp: () => setCatchUp(0),
    state: qs,
    pause: queue.pause,
    resume: queue.resume,
    skip: queue.skip,
    stop: queue.stop,
  };
}
