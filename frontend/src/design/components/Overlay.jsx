import React, { createContext, useCallback, useContext, useEffect, useId, useMemo, useRef, useState } from 'react';
import { AnimatePresence, LazyMotion, domAnimation, m } from 'framer-motion';
import Glyph from '../glyphs/Glyph';
import { IconButton } from './Button';
import { Portal, cx, useDialog, useScrollLock } from './internal';
import { useReducedMotionPref } from '../motion';
import './overlay.css';

const EASE_OUT = [0.2, 0.8, 0.2, 1];

/**
 * Modal dialog.
 * - role="dialog" aria-modal, labelled by `title`, described by `description`.
 * - Focus moves inside (initialFocusRef or first focusable), Tab is trapped, Esc closes,
 *   focus returns to the opener on close. Body scroll is locked while open.
 * - Clicking the backdrop closes unless closeOnBackdrop={false}.
 * size: 'sm' | 'md' | 'lg' | 'sheet' (bottom sheet on mobile).
 */
export function Modal({
  open,
  onClose,
  title,
  description,
  icon,
  size = 'md',
  initialFocusRef,
  closeOnBackdrop = true,
  closeOnEsc = true,
  closeLabel = 'Close',
  footer,
  className,
  children,
}) {
  const reduced = useReducedMotionPref();
  const panelRef = useRef(null);
  const titleId = useId();
  const descId = useId();
  useDialog({ open, onClose, panelRef, initialFocusRef, closeOnEsc });
  useScrollLock(open);

  return (
    <Portal>
      <LazyMotion features={domAnimation}>
        <AnimatePresence>
          {open ? (
            <div className={cx('sr-overlay', size === 'sheet' && 'sr-overlay--sheet')} key="modal">
              <m.div
                className="sr-overlay__backdrop"
                aria-hidden="true"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: reduced ? 0 : 0.2 }}
                onMouseDown={closeOnBackdrop ? () => onClose && onClose() : undefined}
              />
              <m.div
                ref={panelRef}
                role="dialog"
                aria-modal="true"
                aria-labelledby={title ? titleId : undefined}
                aria-describedby={description ? descId : undefined}
                tabIndex={-1}
                className={cx('sr-modal', `sr-modal--${size}`, className)}
                initial={reduced ? { opacity: 0 } : { opacity: 0, y: 12, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={reduced ? { opacity: 0 } : { opacity: 0, y: 8, scale: 0.98 }}
                transition={{ duration: reduced ? 0 : 0.24, ease: EASE_OUT }}
              >
                <header className="sr-modal__header">
                  {title ? (
                    <h2 id={titleId} className="sr-modal__title">
                      {typeof icon === 'string' ? <Glyph name={icon} size={20} /> : icon}
                      <span>{title}</span>
                    </h2>
                  ) : (
                    <span />
                  )}
                  {onClose ? <IconButton icon="close" label={closeLabel} size="sm" tooltip={false} onClick={onClose} /> : null}
                </header>
                {description ? (
                  <p id={descId} className="sr-modal__description">
                    {description}
                  </p>
                ) : null}
                <div className="sr-modal__body">{children}</div>
                {footer ? <footer className="sr-modal__footer">{footer}</footer> : null}
              </m.div>
            </div>
          ) : null}
        </AnimatePresence>
      </LazyMotion>
    </Portal>
  );
}

/**
 * Drawer (mobile nav, member panel). Same dialog behaviour as Modal.
 * side: 'left' | 'right' | 'bottom'. width defaults to min(85vw, 360px).
 */
export function Drawer({ open, onClose, title, side = 'left', initialFocusRef, closeLabel = 'Close', width, className, children }) {
  const reduced = useReducedMotionPref();
  const panelRef = useRef(null);
  const titleId = useId();
  useDialog({ open, onClose, panelRef, initialFocusRef });
  useScrollLock(open);

  const offset = side === 'left' ? { x: '-100%' } : side === 'right' ? { x: '100%' } : { y: '100%' };
  const enter = side === 'bottom' ? { y: 0 } : { x: 0 };

  return (
    <Portal>
      <LazyMotion features={domAnimation}>
        <AnimatePresence>
          {open ? (
            <div className="sr-overlay sr-overlay--drawer" key="drawer">
              <m.div
                className="sr-overlay__backdrop"
                aria-hidden="true"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: reduced ? 0 : 0.2 }}
                onMouseDown={() => onClose && onClose()}
              />
              <m.div
                ref={panelRef}
                role="dialog"
                aria-modal="true"
                aria-labelledby={title ? titleId : undefined}
                tabIndex={-1}
                className={cx('sr-drawer', `sr-drawer--${side}`, className)}
                style={width ? { width } : undefined}
                initial={reduced ? { opacity: 0 } : offset}
                animate={reduced ? { opacity: 1 } : enter}
                exit={reduced ? { opacity: 0 } : offset}
                transition={{ duration: reduced ? 0 : 0.26, ease: EASE_OUT }}
              >
                <header className="sr-drawer__header">
                  {title ? (
                    <h2 id={titleId} className="sr-drawer__title">
                      {title}
                    </h2>
                  ) : (
                    <span />
                  )}
                  {onClose ? <IconButton icon="close" label={closeLabel} size="sm" tooltip={false} onClick={onClose} /> : null}
                </header>
                <div className="sr-drawer__body">{children}</div>
              </m.div>
            </div>
          ) : null}
        </AnimatePresence>
      </LazyMotion>
    </Portal>
  );
}

/* ------------------------------------------------------------------ */
/* Toasts                                                              */
/* ------------------------------------------------------------------ */

const ToastContext = createContext(null);
let toastSeq = 0;

const TONE_GLYPH = { info: 'raven', ok: 'check', warn: 'warning', danger: 'skull', blood: 'blood-drop', arcane: 'ai-sigil' };

/**
 * <ToastProvider> + useToast().
 * toast({ title, body, tone: 'info'|'ok'|'warn'|'danger'|'blood'|'arcane', duration: ms (0 = sticky) })
 * returns the id; dismiss(id) closes one.
 * Errors (tone 'danger') are announced assertively (role="alert"), the rest politely (role="status").
 * Timers pause while the pointer is over / focus is inside the region.
 */
export function ToastProvider({ children, label = 'Notifications', closeLabel = 'Dismiss', max = 4 }) {
  const [toasts, setToasts] = useState([]);
  const timers = useRef(new Map());
  const paused = useRef(false);

  const dismiss = useCallback((id) => {
    const t = timers.current.get(id);
    if (t) window.clearTimeout(t.handle);
    timers.current.delete(id);
    setToasts((list) => list.filter((x) => x.id !== id));
  }, []);

  const schedule = useCallback(
    (id, ms) => {
      if (!ms) return;
      const handle = window.setTimeout(() => dismiss(id), ms);
      timers.current.set(id, { handle, ms, start: Date.now() });
    },
    [dismiss]
  );

  const toast = useCallback(
    (opts) => {
      toastSeq += 1;
      const id = opts.id || `sr-toast-${toastSeq}`;
      const tone = opts.tone || 'info';
      const duration = opts.duration != null ? opts.duration : tone === 'danger' ? 8000 : 5000;
      setToasts((list) => [...list.filter((x) => x.id !== id), { ...opts, id, tone, duration }].slice(-max));
      if (!paused.current) schedule(id, duration);
      else timers.current.set(id, { handle: null, ms: duration, start: 0 });
      return id;
    },
    [max, schedule]
  );

  const pause = () => {
    if (paused.current) return;
    paused.current = true;
    timers.current.forEach((t, id) => {
      if (t.handle) {
        window.clearTimeout(t.handle);
        const left = Math.max(1000, t.ms - (Date.now() - t.start));
        timers.current.set(id, { handle: null, ms: left, start: 0 });
      }
    });
  };
  const resume = () => {
    if (!paused.current) return;
    paused.current = false;
    timers.current.forEach((t, id) => schedule(id, t.ms));
  };

  useEffect(() => {
    const map = timers.current;
    return () => map.forEach((t) => t.handle && window.clearTimeout(t.handle));
  }, []);

  const api = useMemo(() => ({ toast, dismiss }), [toast, dismiss]);

  return (
    <ToastContext.Provider value={api}>
      {children}
      <Portal>
        <ToastRegion toasts={toasts} dismiss={dismiss} label={label} closeLabel={closeLabel} onPause={pause} onResume={resume} />
      </Portal>
    </ToastContext.Provider>
  );
}

function ToastRegion({ toasts, dismiss, label, closeLabel, onPause, onResume }) {
  const reduced = useReducedMotionPref();
  return (
    <section
      className="sr-toasts"
      aria-label={label}
      onMouseEnter={onPause}
      onMouseLeave={onResume}
      onFocus={onPause}
      onBlur={onResume}
    >
      <LazyMotion features={domAnimation}>
        <ol className="sr-toasts__list">
          <AnimatePresence initial={false}>
            {toasts.map((t) => (
              <m.li
                key={t.id}
                layout={!reduced}
                className={cx('sr-toast', `sr-toast--${t.tone}`)}
                role={t.tone === 'danger' ? 'alert' : 'status'}
                initial={reduced ? { opacity: 0 } : { opacity: 0, x: 24 }}
                animate={{ opacity: 1, x: 0 }}
                exit={reduced ? { opacity: 0 } : { opacity: 0, x: 24 }}
                transition={{ duration: reduced ? 0 : 0.2, ease: EASE_OUT }}
              >
                <Glyph name={t.icon || TONE_GLYPH[t.tone] || 'raven'} size={20} className="sr-toast__glyph" />
                <div className="sr-toast__text">
                  {t.title ? <div className="sr-toast__title">{t.title}</div> : null}
                  {t.body ? <div className="sr-toast__body">{t.body}</div> : null}
                </div>
                <IconButton icon="close" label={closeLabel} size="sm" tooltip={false} onClick={() => dismiss(t.id)} />
              </m.li>
            ))}
          </AnimatePresence>
        </ol>
      </LazyMotion>
    </section>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast() needs a <ToastProvider> above it');
  return ctx;
}
