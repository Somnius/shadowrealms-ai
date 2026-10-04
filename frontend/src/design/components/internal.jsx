import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useMotionPreference } from '../motion';

export const cx = (...parts) => parts.filter(Boolean).join(' ');

const FOCUSABLE = [
  'a[href]',
  'area[href]',
  'button:not([disabled])',
  'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  'iframe',
  'audio[controls]',
  'video[controls]',
  '[contenteditable]:not([contenteditable="false"])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

export function getFocusable(root) {
  if (!root) return [];
  return Array.from(root.querySelectorAll(FOCUSABLE)).filter(
    (el) => !el.hasAttribute('inert') && el.getAttribute('aria-hidden') !== 'true'
  );
}

const useIsoLayoutEffect = typeof window !== 'undefined' ? useLayoutEffect : useEffect;

/**
 * Renders children into a fresh `.sr-app.sr-portal` container on document.body so overlays
 * get the design tokens/base styles even though they live outside the shell's DOM tree.
 */
export function Portal({ children }) {
  const { reduced } = useMotionPreference();
  // Created during render so children (and their refs) exist on the first commit;
  // attached in a layout effect, i.e. before any passive effect (focus management) runs.
  const [node] = useState(() => {
    if (typeof document === 'undefined') return null;
    const el = document.createElement('div');
    el.className = 'sr-app sr-portal';
    return el;
  });
  useIsoLayoutEffect(() => {
    if (!node) return undefined;
    const lang = document.documentElement.getAttribute('lang');
    if (lang) node.setAttribute('lang', lang);
    document.body.appendChild(node);
    return () => {
      if (node.parentNode) node.parentNode.removeChild(node);
    };
  }, [node]);
  useIsoLayoutEffect(() => {
    if (node) node.setAttribute('data-motion', reduced ? 'reduced' : 'full');
  }, [node, reduced]);
  return node ? createPortal(children, node) : null;
}

let scrollLocks = 0;
let savedOverflow = '';

/** Lock body scroll while `active` (ref-counted for stacked overlays). */
export function useScrollLock(active) {
  useEffect(() => {
    if (!active) return undefined;
    if (scrollLocks === 0) {
      savedOverflow = document.body.style.overflow;
      document.body.style.overflow = 'hidden';
    }
    scrollLocks += 1;
    return () => {
      scrollLocks -= 1;
      if (scrollLocks === 0) document.body.style.overflow = savedOverflow;
    };
  }, [active]);
}

/**
 * Dialog behaviour shared by Modal and Drawer:
 * - moves focus into the panel on open (initialFocusRef, first focusable, or the panel),
 * - traps Tab / Shift+Tab inside,
 * - Esc calls onClose (unless closeOnEsc is false),
 * - restores focus to the previously focused element on close.
 */
const dialogStack = [];

export function useDialog({ open, onClose, panelRef, initialFocusRef, closeOnEsc = true }) {
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!open) return undefined;
    const previously = document.activeElement;
    const panel = panelRef.current;
    const target =
      (initialFocusRef && initialFocusRef.current) || getFocusable(panel)[0] || panel;
    if (target && typeof target.focus === 'function') target.focus();
    const token = {};
    dialogStack.push(token);

    function onKeyDown(event) {
      // Only the top-most open dialog reacts (stacked modals / drawer + modal).
      if (!panelRef.current || dialogStack[dialogStack.length - 1] !== token) return;
      if (event.key === 'Escape' && closeOnEsc) {
        event.stopPropagation();
        if (onCloseRef.current) onCloseRef.current();
        return;
      }
      if (event.key !== 'Tab') return;
      const items = getFocusable(panelRef.current);
      if (items.length === 0) {
        event.preventDefault();
        panelRef.current.focus();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement;
      const inside = panelRef.current.contains(active);
      if (event.shiftKey && (active === first || !inside)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (active === last || !inside)) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener('keydown', onKeyDown, true);
    return () => {
      document.removeEventListener('keydown', onKeyDown, true);
      const idx = dialogStack.indexOf(token);
      if (idx !== -1) dialogStack.splice(idx, 1);
      if (previously && typeof previously.focus === 'function' && document.contains(previously)) {
        previously.focus();
      }
    };
  }, [open, panelRef, initialFocusRef, closeOnEsc]);
}
