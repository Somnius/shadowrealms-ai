import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { overlayFromMarker } from '../../dice/diceMarker';
import { diceAnimationId, isMarker } from '../chat/messageModel';

const randomD10 = () => Math.floor(Math.random() * 10) + 1;

export const MAX_DURATION_MS = 8000;
export const MAX_CLOCK_SKEW_MS = 60000;

/**
 * Marker timing from another client (or a tampered row): the duration is capped at 8 s and the start
 * time must lie within ±60 s of this clock, so a marker can't hide a result or freeze the overlay.
 */
export function clampMarkerTiming(marker, now = Date.now()) {
  let durationMs = Number(marker.duration_ms ?? marker.durationMs);
  if (!Number.isFinite(durationMs) || durationMs <= 0) durationMs = 3000;
  durationMs = Math.min(durationMs, MAX_DURATION_MS);
  let startedAtMs = Number(marker.started_at_ms ?? marker.startedAtMs);
  if (!Number.isFinite(startedAtMs)) startedAtMs = now;
  startedAtMs = Math.min(Math.max(startedAtMs, now - MAX_CLOCK_SKEW_MS), now + MAX_CLOCK_SKEW_MS);
  return { startedAtMs, durationMs };
}

const CLOSED = {
  visible: false,
  animationId: null,
  startedAtMs: 0,
  revealAtMs: 0,
  durationMs: 3000,
  difficulty: 6,
  diceFinal: [],
  diceRolling: [],
  extraDiceCount: 0,
  successes: 0,
  isBotch: false,
  isCritical: false,
  poolSize: 0,
  settled: false,
  rulesEdition: 'classic',
  hungerFlags: [],
  result: {},
};

function parseMarker(msg) {
  try {
    const obj = typeof msg.content === 'string' ? JSON.parse(msg.content) : msg.content;
    if (!obj || typeof obj !== 'object') return null;
    if (!obj.animation_id) obj.animation_id = diceAnimationId(msg);
    return obj;
  } catch {
    return null;
  }
}

/**
 * Shared dice animation (phase 1 behaviour, moved out of SimpleApp): marker rows
 * (dice_animation[_hidden]:<id>) start the overlay on every client; the final roll line stays hidden
 * until the reveal time so nobody sees the result before the dice land.
 *
 * Returns { overlay, dismiss, startFromMarker, hiddenMessageIds:Set<string>, onSettled(cb) }.
 */
export function useDiceOverlay(messages, { onSettle } = {}) {
  const [overlay, setOverlay] = useState(CLOSED);
  const [pending, setPending] = useState({});
  const processed = useRef(new Set());
  const pendingTimers = useRef({});
  const onSettleRef = useRef(onSettle);
  onSettleRef.current = onSettle;

  const startFromMarker = useCallback((marker) => {
    if (!marker || typeof marker !== 'object') return;
    const animId = String(marker.animation_id || marker.animationId || '');
    if (!animId || processed.current.has(animId)) return;
    processed.current.add(animId);
    const { startedAtMs, durationMs } = clampMarkerTiming(marker);
    // A start in the future (clock skew) still never hides the result for more than the duration.
    const revealAtMs = Math.min(startedAtMs + durationMs, Date.now() + durationMs);
    const remaining = revealAtMs - Date.now();
    if (remaining <= 0) return; // missed the window (history load / slow poll): just show the result
    setPending((p) => ({ ...p, [animId]: true }));
    if (pendingTimers.current[animId]) clearTimeout(pendingTimers.current[animId]);
    pendingTimers.current[animId] = setTimeout(() => {
      setPending((p) => {
        const next = { ...p };
        delete next[animId];
        return next;
      });
      delete pendingTimers.current[animId];
    }, remaining);
    const parsed = overlayFromMarker(marker);
    const diceFinal = parsed.diceFinal || [];
    setOverlay({
      ...CLOSED,
      visible: true,
      animationId: animId,
      startedAtMs,
      revealAtMs,
      durationMs,
      ...parsed,
      diceFinal,
      diceRolling: diceFinal.map(() => randomD10()),
      isBotch: parsed.result.is_botch,
      isCritical: parsed.result.is_critical,
    });
  }, []);

  // New marker rows (own rolls are started locally before they're posted; processed ids dedupe).
  useEffect(() => {
    for (const m of messages || []) {
      if (!isMarker(m)) continue;
      const marker = parseMarker(m);
      if (marker) startFromMarker(marker);
    }
  }, [messages, startFromMarker]);

  // Rolling → settle → hide.
  useEffect(() => {
    if (!overlay.visible || !overlay.animationId) return undefined;
    const animId = overlay.animationId;
    const finalValues = Array.isArray(overlay.diceFinal) ? overlay.diceFinal : [];
    const count = Math.max(1, finalValues.length);
    const roll = setInterval(() => {
      setOverlay((prev) => ({ ...prev, diceRolling: Array.from({ length: count }, randomD10) }));
    }, 90);
    let hide;
    const reveal = setTimeout(() => {
      clearInterval(roll);
      setOverlay((prev) => ({ ...prev, settled: true, diceRolling: finalValues }));
      if (onSettleRef.current) onSettleRef.current();
      hide = setTimeout(() => {
        setOverlay((prev) => (prev.animationId === animId ? { ...prev, visible: false } : prev));
      }, 2200);
    }, Math.max(0, overlay.revealAtMs - Date.now()));
    return () => {
      clearInterval(roll);
      clearTimeout(reveal);
      if (hide) clearTimeout(hide);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [overlay.animationId]);

  useEffect(
    () => () => {
      Object.values(pendingTimers.current).forEach(clearTimeout);
    },
    []
  );

  const hiddenMessageIds = useMemo(() => {
    const ids = new Set();
    const keys = Object.keys(pending);
    if (!keys.length) return ids;
    for (const m of messages || []) {
      const id = diceAnimationId(m);
      if (id && pending[id] && m.id != null) ids.add(String(m.id));
    }
    return ids;
  }, [messages, pending]);

  const dismiss = useCallback(() => setOverlay((prev) => ({ ...prev, visible: false })), []);

  return { overlay, dismiss, startFromMarker, hiddenMessageIds };
}
