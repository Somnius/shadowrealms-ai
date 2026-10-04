import React, { useId, useRef, useState } from 'react';
import Glyph from '../glyphs/Glyph';
import { cx } from './internal';
import './display.css';

/**
 * Tabs with roving tabindex (WAI-ARIA tabs pattern, automatic activation).
 *
 * tabs: [{ id, label, icon?, content, disabled? }]
 * value / onChange for controlled use, or defaultValue.
 * label: accessible name of the tab list.
 * Keys: Left/Right (Up/Down when orientation="vertical"), Home, End.
 */
export default function Tabs({ tabs, value, defaultValue, onChange, label, orientation = 'horizontal', className }) {
  const baseId = useId();
  const [own, setOwn] = useState(defaultValue != null ? defaultValue : tabs[0] && tabs[0].id);
  const current = value != null ? value : own;
  const refs = useRef({});

  const enabled = tabs.filter((t) => !t.disabled);
  const select = (id, focus) => {
    if (value == null) setOwn(id);
    if (onChange) onChange(id);
    if (focus && refs.current[id]) refs.current[id].focus();
  };

  const onKeyDown = (event) => {
    const idx = enabled.findIndex((t) => t.id === current);
    const prevKey = orientation === 'vertical' ? 'ArrowUp' : 'ArrowLeft';
    const nextKey = orientation === 'vertical' ? 'ArrowDown' : 'ArrowRight';
    let next = null;
    if (event.key === nextKey) next = enabled[(idx + 1) % enabled.length];
    else if (event.key === prevKey) next = enabled[(idx - 1 + enabled.length) % enabled.length];
    else if (event.key === 'Home') next = enabled[0];
    else if (event.key === 'End') next = enabled[enabled.length - 1];
    if (next) {
      event.preventDefault();
      select(next.id, true);
    }
  };

  const tabId = (id) => `${baseId}-tab-${id}`;
  const panelId = (id) => `${baseId}-panel-${id}`;
  const active = tabs.find((t) => t.id === current);

  return (
    <div className={cx('sr-tabs', `sr-tabs--${orientation}`, className)}>
      <div className="sr-tabs__list" role="tablist" aria-label={label} aria-orientation={orientation} onKeyDown={onKeyDown}>
        {tabs.map((t) => {
          const selected = t.id === current;
          return (
            <button
              key={t.id}
              ref={(el) => {
                refs.current[t.id] = el;
              }}
              type="button"
              role="tab"
              id={tabId(t.id)}
              aria-selected={selected}
              aria-controls={panelId(t.id)}
              tabIndex={selected ? 0 : -1}
              disabled={t.disabled}
              className="sr-tabs__tab"
              onClick={() => select(t.id, false)}
            >
              {typeof t.icon === 'string' ? <Glyph name={t.icon} size={16} /> : t.icon}
              <span>{t.label}</span>
            </button>
          );
        })}
      </div>
      {active ? (
        <div className="sr-tabs__panel" role="tabpanel" id={panelId(active.id)} aria-labelledby={tabId(active.id)} tabIndex={0}>
          {active.content}
        </div>
      ) : null}
    </div>
  );
}
