import { useMemo, useRef, useState } from 'react';
import { Glyph, Modal } from '../../design';
import { roomGlyph } from './ChannelList';
import { lineGlyph } from '../../app/hooks';
import { t } from '../../i18n';

/** Rank: prefix match first, then substring. */
export function filterTargets(targets, query) {
  const q = String(query || '').trim().toLowerCase();
  if (!q) return targets;
  const scored = [];
  for (const tg of targets) {
    const name = `${tg.name} ${tg.keywords || ''}`.toLowerCase();
    const i = name.indexOf(q);
    if (i === -1) continue;
    scored.push([i === 0 ? 0 : 1, tg]);
  }
  return scored.sort((a, b) => a[0] - b[0]).map((x) => x[1]);
}

/** Ctrl/⌘+K: jump to a room of this chronicle or to another chronicle. */
export default function QuickSwitcher({ open, onClose, rooms, chronicles, onPick }) {
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const inputRef = useRef(null);
  const targets = useMemo(
    () => [
      ...rooms.map((r) => ({ key: `r${r.id}`, kind: 'room', id: r.id, name: r.name, keywords: r.type, glyph: roomGlyph(r.type) })),
      ...chronicles.map((c) => ({ key: `c${c.id}`, kind: 'chronicle', id: c.id, name: c.name, glyph: lineGlyph(c.game_system) })),
    ],
    [rooms, chronicles]
  );
  const results = filterTargets(targets, query).slice(0, 12);

  const pick = (tg) => {
    if (!tg) return;
    setQuery('');
    onPick(tg);
  };

  return (
    <Modal open={open} onClose={onClose} title={t('play:switcher.title', 'Jump to…')} icon="search" size="sm" initialFocusRef={inputRef}>
      <input
        ref={inputRef}
        className="sr-input"
        value={query}
        placeholder={t('play:switcher.placeholder', 'Room or chronicle name')}
        aria-label={t('play:switcher.placeholder', 'Room or chronicle name')}
        role="combobox"
        aria-expanded="true"
        aria-controls="sr-switcher-list"
        aria-activedescendant={results[active] ? `sr-switch-${results[active].key}` : undefined}
        onChange={(e) => {
          setQuery(e.target.value);
          setActive(0);
        }}
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown') {
            e.preventDefault();
            setActive((i) => Math.min(results.length - 1, i + 1));
          } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            setActive((i) => Math.max(0, i - 1));
          } else if (e.key === 'Enter') {
            e.preventDefault();
            pick(results[active]);
          }
        }}
      />
      <ul id="sr-switcher-list" role="listbox" className="sr-switcher" aria-label={t('play:switcher.results', 'Results')}>
        {results.map((r, i) => (
          <li
            key={r.key}
            id={`sr-switch-${r.key}`}
            role="option"
            aria-selected={i === active}
            className={`sr-switcher__item${i === active ? ' is-active' : ''}`}
            onMouseDown={(e) => {
              e.preventDefault();
              pick(r);
            }}
            onMouseEnter={() => setActive(i)}
          >
            <Glyph name={r.glyph} size={18} />
            <span className="sr-switcher__name">{r.name}</span>
            <span className="sr-muted sr-small">{r.kind === 'room' ? t('play:switcher.room', 'room') : t('play:switcher.chronicle', 'chronicle')}</span>
          </li>
        ))}
        {!results.length ? <li className="sr-muted">{t('play:switcher.none', 'Nothing matches.')}</li> : null}
      </ul>
    </Modal>
  );
}
