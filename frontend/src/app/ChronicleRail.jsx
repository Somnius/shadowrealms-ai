import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { Glyph, Tooltip } from '../design';
import { useChronicles } from './ChroniclesContext';
import { lineGlyph, lineOf } from './hooks';
import { t } from '../i18n';

function initials(name) {
  const parts = String(name || '').trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return '?';
  return (parts.length > 1 ? parts[0][0] + parts[1][0] : parts[0].slice(0, 2)).toLocaleUpperCase();
}

function RailItem({ to, label, active, children, expanded, onNavigate }) {
  const link = (
    <NavLink
      to={to}
      className={`sr-rail__item${active ? ' is-active' : ''}`}
      aria-current={active ? 'page' : undefined}
      aria-label={expanded ? undefined : label}
      onClick={onNavigate}
    >
      <span className="sr-rail__pill" aria-hidden="true" />
      <span className="sr-rail__icon">{children}</span>
      {expanded ? <span className="sr-rail__name">{label}</span> : null}
    </NavLink>
  );
  if (expanded) return link;
  return (
    <Tooltip content={label} placement="right" describe={false}>
      {link}
    </Tooltip>
  );
}

/**
 * Chronicle rail (Discord server list): Hall, one sigil per chronicle, create.
 * `expanded` renders names next to the icons (mobile drawer).
 */
export default function ChronicleRail({ expanded = false, onNavigate }) {
  const { chronicles } = useChronicles();
  const loc = useLocation();
  const path = loc.pathname;
  const activeId = (/^\/(?:c|chronicles)\/(\d+)/.exec(path) || [])[1];

  return (
    <nav className={`sr-rail${expanded ? ' sr-rail--expanded' : ''}`} aria-label={t('shell:rail.label', 'Chronicles')}>
      <RailItem
        to="/chronicles"
        label={t('shell:rail.hall', 'Chronicle hall')}
        active={path === '/chronicles'}
        expanded={expanded}
        onNavigate={onNavigate}
      >
        <Glyph name="logo-mark" size={26} />
      </RailItem>
      <div className="sr-rail__sep" role="separator" />
      <ul className="sr-rail__list">
        {chronicles.map((c) => {
          const line = lineOf(c.game_system);
          return (
            <li key={c.id} data-line={line || undefined}>
              <RailItem
                to={`/c/${c.id}`}
                label={c.name}
                active={String(activeId) === String(c.id)}
                expanded={expanded}
                onNavigate={onNavigate}
              >
                <span className="sr-rail__sigil">
                  <Glyph name={lineGlyph(c.game_system)} size={22} />
                  <span className="sr-rail__initials" aria-hidden="true">
                    {initials(c.name)}
                  </span>
                </span>
              </RailItem>
            </li>
          );
        })}
      </ul>
      <RailItem
        to="/chronicles/new"
        label={t('shell:rail.create', 'Create a chronicle')}
        active={path === '/chronicles/new'}
        expanded={expanded}
        onNavigate={onNavigate}
      >
        <Glyph name="plus" size={22} />
      </RailItem>
    </nav>
  );
}
