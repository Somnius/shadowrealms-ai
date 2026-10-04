/**
 * Motion preferences + small runtime hooks shared by the design system.
 *
 * - DesignProvider renders the opt-in `.sr-app` root with data-motion / data-line / lang,
 *   and a framer-motion MotionConfig so JS animations follow the same preference.
 * - Preference is 'system' (follow prefers-reduced-motion), 'reduced' or 'full'.
 *   The OS setting always wins: 'full' only means "don't add a reduction on top of the OS".
 *   A manual choice is remembered in localStorage (best effort).
 */
import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { MotionConfig } from 'framer-motion';
import './components/forms.css'; // MotionToggle reuses the Switch styles

const STORAGE_KEY = 'sr_motion';
const QUERY = '(prefers-reduced-motion: reduce)';

function readStored() {
  try {
    const v = window.localStorage.getItem(STORAGE_KEY);
    return v === 'reduced' || v === 'full' || v === 'system' ? v : null;
  } catch (e) {
    return null;
  }
}

function writeStored(value) {
  try {
    window.localStorage.setItem(STORAGE_KEY, value);
  } catch (e) {
    /* private mode etc. */
  }
}

/** True when the OS asks for reduced motion. Live-updates. */
export function useSystemReducedMotion() {
  const get = () =>
    typeof window !== 'undefined' && typeof window.matchMedia === 'function'
      ? !!window.matchMedia(QUERY).matches
      : false;
  const [reduced, setReduced] = useState(get);
  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return undefined;
    const mql = window.matchMedia(QUERY);
    const onChange = () => setReduced(!!mql.matches);
    if (mql.addEventListener) mql.addEventListener('change', onChange);
    else if (mql.addListener) mql.addListener(onChange);
    return () => {
      if (mql.removeEventListener) mql.removeEventListener('change', onChange);
      else if (mql.removeListener) mql.removeListener(onChange);
    };
  }, []);
  return reduced;
}

const MotionContext = createContext(null);

/**
 * Root wrapper. Props:
 * - motion: controlled preference ('system' | 'reduced' | 'full'); omit to let the provider own it.
 * - onMotionChange: called with the new preference (controlled mode).
 * - line: game line accent ('vampire' | 'werewolf' | 'mage' | ...), written to data-line.
 * - lang: optional lang attribute (set it to 'el' for Greek so uppercase drops accents).
 * - as: element to render (default 'div').
 */
export function DesignProvider({
  children,
  motion,
  onMotionChange,
  line,
  lang,
  as: Tag = 'div',
  className = '',
  ...rest
}) {
  const system = useSystemReducedMotion();
  const [own, setOwn] = useState(() => readStored() || 'system');
  const preference = motion || own;
  const reduced = system || preference === 'reduced';

  const setPreference = useCallback(
    (next) => {
      if (onMotionChange) onMotionChange(next);
      if (!motion) setOwn(next);
      writeStored(next);
    },
    [motion, onMotionChange]
  );

  const value = useMemo(
    () => ({ reduced, preference, systemReduced: system, setPreference }),
    [reduced, preference, system, setPreference]
  );

  return (
    <MotionContext.Provider value={value}>
      <MotionConfig reducedMotion={reduced ? 'always' : 'never'}>
        <Tag
          className={`sr-app ${className}`.trim()}
          data-motion={reduced ? 'reduced' : 'full'}
          data-line={line || undefined}
          lang={lang}
          {...rest}
        >
          {children}
        </Tag>
      </MotionConfig>
    </MotionContext.Provider>
  );
}

/**
 * { reduced, preference, systemReduced, setPreference }.
 * Works without a provider too (falls back to the OS setting; setPreference is a no-op).
 */
export function useMotionPreference() {
  const ctx = useContext(MotionContext);
  const system = useSystemReducedMotion();
  if (ctx) return ctx;
  return { reduced: system, preference: 'system', systemReduced: system, setPreference: () => {} };
}

/** Shortcut: should animations be reduced right now? */
export function useReducedMotionPref() {
  return useMotionPreference().reduced;
}

/** false while the tab is hidden (ambient loops pause). */
export function useDocumentVisible() {
  const [visible, setVisible] = useState(
    () => typeof document === 'undefined' || document.visibilityState !== 'hidden'
  );
  useEffect(() => {
    if (typeof document === 'undefined') return undefined;
    const onChange = () => setVisible(document.visibilityState !== 'hidden');
    document.addEventListener('visibilitychange', onChange);
    return () => document.removeEventListener('visibilitychange', onChange);
  }, []);
  return visible;
}

/** true while the element intersects the viewport (true when IntersectionObserver is missing). */
export function useInView(ref, rootMargin = '0px') {
  const [inView, setInView] = useState(true);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof window === 'undefined' || typeof window.IntersectionObserver !== 'function') {
      return undefined;
    }
    const io = new window.IntersectionObserver(
      (entries) => {
        const entry = entries[entries.length - 1];
        if (entry) setInView(entry.isIntersecting);
      },
      { rootMargin }
    );
    io.observe(el);
    return () => io.disconnect();
  }, [ref, rootMargin]);
  return inView;
}

/**
 * Should an ambient loop run? (motion allowed, tab visible, element on screen)
 * Returns { active, reduced, paused } — use `paused` for data-paused.
 */
export function useAmbient(ref) {
  const reduced = useReducedMotionPref();
  const visible = useDocumentVisible();
  const inView = useInView(ref);
  const active = !reduced && visible && inView;
  return { active, reduced, paused: !reduced && !active };
}

/** Tiny segmented control for the manual reduce-motion toggle (for a user menu / settings). */
export function MotionToggle({ label = 'Reduce motion', className = '' }) {
  const { reduced, preference, systemReduced, setPreference } = useMotionPreference();
  return (
    <button
      type="button"
      role="switch"
      aria-checked={reduced}
      aria-disabled={systemReduced || undefined}
      title={systemReduced ? 'Reduced motion is on in your system settings' : undefined}
      className={`sr-switch ${className}`.trim()}
      onClick={() => {
        if (!systemReduced) setPreference(reduced ? 'full' : 'reduced');
      }}
      data-preference={preference}
    >
      <span className="sr-switch__track" aria-hidden="true">
        <span className="sr-switch__thumb" />
      </span>
      <span className="sr-switch__label">{label}</span>
    </button>
  );
}
