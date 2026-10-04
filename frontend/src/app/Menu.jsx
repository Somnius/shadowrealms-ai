import { useCallback, useEffect, useId, useRef, useState } from 'react';
import { Glyph } from '../design';

/**
 * Accessible menu button (WAI-ARIA menu pattern, no extra dependency):
 * - button aria-haspopup="menu" / aria-expanded; Enter, Space or ↓ opens and focuses the first item, ↑ the last
 * - ↑/↓/Home/End move, Esc closes and returns focus, Tab closes, click outside closes
 *
 * items: [{ id, label, icon, onSelect, danger, checked (for toggles), radio (with checked: one of a group),
 *          lang (label language), hint, divider, heading (non-interactive group title) }]
 */
export default function MenuButton({ label, renderButton, items, placement = 'bottom-end', className = '', menuLabel }) {
  const [open, setOpen] = useState(false);
  const btnRef = useRef(null);
  const menuRef = useRef(null);
  const id = useId();
  const focusIndex = useRef(0);

  const realItems = items.filter((i) => !i.divider && !i.heading && !i.render);

  const focusItem = useCallback((idx) => {
    const nodes = menuRef.current ? menuRef.current.querySelectorAll('[role^="menuitem"]') : [];
    if (!nodes.length) return;
    const i = (idx + nodes.length) % nodes.length;
    focusIndex.current = i;
    nodes[i].focus();
  }, []);

  const close = useCallback((returnFocus = true) => {
    setOpen(false);
    if (returnFocus && btnRef.current) btnRef.current.focus();
  }, []);

  useEffect(() => {
    if (!open) return undefined;
    const onDown = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target) && btnRef.current && !btnRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('touchstart', onDown);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('touchstart', onDown);
    };
  }, [open]);

  useEffect(() => {
    if (open) requestAnimationFrame(() => focusItem(focusIndex.current));
  }, [open, focusItem]);

  const onButtonKey = (e) => {
    if (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      focusIndex.current = 0;
      setOpen(true);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      focusIndex.current = realItems.length - 1;
      setOpen(true);
    }
  };

  const onMenuKey = (e) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      close(true);
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      focusItem(focusIndex.current + 1);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      focusItem(focusIndex.current - 1);
    } else if (e.key === 'Home') {
      e.preventDefault();
      focusItem(0);
    } else if (e.key === 'End') {
      e.preventDefault();
      focusItem(realItems.length - 1);
    } else if (e.key === 'Tab') {
      setOpen(false);
    }
  };

  const buttonProps = {
    ref: btnRef,
    type: 'button',
    'aria-haspopup': 'menu',
    'aria-expanded': open,
    'aria-controls': open ? `${id}-menu` : undefined,
    'aria-label': label,
    onClick: () => {
      focusIndex.current = 0;
      setOpen((o) => !o);
    },
    onKeyDown: onButtonKey,
  };

  let itemIdx = -1;
  return (
    <div className={`sr-menu ${className}`.trim()}>
      {renderButton(buttonProps, open)}
      {open ? (
        <div
          ref={menuRef}
          id={`${id}-menu`}
          role="menu"
          aria-label={menuLabel || label}
          className={`sr-menu__list sr-menu__list--${placement}`}
          onKeyDown={onMenuKey}
        >
          {items.map((item, i) => {
            if (item.divider) return <div key={`d-${i}`} role="separator" className="sr-menu__sep" />;
            if (item.render) return <div key={item.id || i}>{item.render()}</div>;
            if (item.heading) {
              return (
                <div key={item.id || i} role="presentation" className="sr-menu__heading">
                  {item.icon ? <Glyph name={item.icon} size={16} /> : null}
                  {item.heading}
                </div>
              );
            }
            itemIdx += 1;
            const myIdx = itemIdx;
            const isToggle = typeof item.checked === 'boolean';
            const role = item.radio ? 'menuitemradio' : isToggle ? 'menuitemcheckbox' : 'menuitem';
            return (
              <button
                key={item.id || i}
                type="button"
                role={role}
                lang={item.lang}
                aria-checked={isToggle ? item.checked : undefined}
                tabIndex={-1}
                aria-disabled={item.disabled || undefined}
                className={`sr-menu__item${item.danger ? ' is-danger' : ''}`}
                onFocus={() => {
                  focusIndex.current = myIdx;
                }}
                onClick={() => {
                  if (item.disabled) return;
                  if (!isToggle || item.radio) close(!item.keepFocus);
                  if (item.onSelect) item.onSelect();
                }}
              >
                {item.icon ? <Glyph name={item.icon} size={18} /> : <span className="sr-menu__noicon" />}
                <span className="sr-menu__label">
                  {item.label}
                  {item.hint ? <span className="sr-menu__hint">{item.hint}</span> : null}
                </span>
                {isToggle ? (
                  <span className={`sr-menu__check${item.checked ? ' is-on' : ''}`} aria-hidden="true">
                    {item.checked ? <Glyph name="check" size={16} strokeWidth={2.4} /> : null}
                  </span>
                ) : null}
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
