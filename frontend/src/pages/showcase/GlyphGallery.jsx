import React, { useMemo, useRef, useState } from 'react';
import {
  AiSigil,
  AnimatedCandle,
  BlinkingEye,
  Button,
  DrippingBlood,
  EmptyState,
  GLYPHS,
  GLYPH_GROUPS,
  Glyph,
  Input,
  SigilDraw,
  Switch,
  useAmbient,
  useOptionalToast,
} from '../../design';
import { t } from '../../i18n';
import { PillGroup, Section } from './parts';

export const GROUP_ORDER = ['dice', 'horror', 'moon', 'room', 'ui', 'line', 'clan', 'discipline'];
/** Groups whose names are World of Darkness terms: they stay in English. */
export const GAME_TERM_GROUPS = ['line', 'clan', 'discipline'];

const ANIMATED_CLASSES = ['sr-glyph-flame', 'sr-glyph-runes', 'sr-glyph-lid'];
export const ANIMATED = new Set(
  Object.keys(GLYPHS).filter((n) => n === 'eye' || n === 'blood-drop' || GLYPHS[n].shapes.some((s) => ANIMATED_CLASSES.includes(s.cls)))
);

export function groupTitle(group) {
  return {
    dice: t('showcase:glyphs.group.dice', 'Dice'),
    horror: t('showcase:glyphs.group.horror', 'Horror'),
    moon: t('showcase:glyphs.group.moon', 'Moon phases'),
    room: t('showcase:glyphs.group.room', 'Rooms'),
    ui: t('showcase:glyphs.group.ui', 'Interface'),
    line: t('showcase:glyphs.group.line', 'Game lines'),
    clan: t('showcase:glyphs.group.clan', 'Clan sigils'),
    discipline: t('showcase:glyphs.group.discipline', 'Discipline sigils'),
  }[group];
}

/** Display name: translated, except game terms (clans, disciplines, lines). */
export function glyphLabel(name) {
  const def = GLYPHS[name];
  if (!def) return name;
  return GAME_TERM_GROUPS.includes(def.group) ? def.label : t(`showcase:glyph.${name}`, def.label);
}

function Tile({ name, selected, onSelect }) {
  const [pulse, setPulse] = useState(0);
  const [hot, setHot] = useState(false);
  const label = glyphLabel(name);
  const wake = () => {
    setHot(true);
    setPulse((p) => p + 1);
  };
  return (
    <li>
      <button
        type="button"
        className={`sc-glyph${selected ? ' is-selected' : ''}`}
        aria-pressed={selected}
        onClick={() => onSelect(name)}
        onMouseEnter={wake}
        onMouseLeave={() => setHot(false)}
        onFocus={wake}
        onBlur={() => setHot(false)}
        data-glyph-tile={name}
      >
        <span className="sc-glyph__art">
          <Glyph key={pulse} name={name} size={32} draw={pulse > 0} animate={hot && ANIMATED.has(name)} />
        </span>
        <span className="sc-glyph__name" lang={GAME_TERM_GROUPS.includes(GLYPHS[name].group) ? 'en' : undefined}>
          {label}
        </span>
        <code className="sc-glyph__id">{name}</code>
        {ANIMATED.has(name) ? (
          <span className="sc-glyph__live" title={t('showcase:glyphs.animatedTag', 'Animated')}>
            <span className="sr-visually-hidden">{t('showcase:glyphs.animatedTag', 'Animated')}</span>
          </span>
        ) : null}
      </button>
    </li>
  );
}

function Inspector({ name }) {
  const ref = useRef(null);
  const { paused } = useAmbient(ref); // glyph loops pause off-screen
  const toast = useOptionalToast();
  const def = GLYPHS[name];
  const usage = `<Glyph name="${name}" />`;
  const copy = async () => {
    let ok = false;
    try {
      await navigator.clipboard.writeText(usage);
      ok = true;
    } catch (e) {
      ok = false;
    }
    if (toast) {
      toast.toast(
        ok
          ? { tone: 'ok', title: t('showcase:glyphs.copied', 'Copied'), body: usage }
          : { tone: 'warn', title: t('showcase:glyphs.copyFailed', 'Could not copy'), body: usage }
      );
    }
  };
  return (
    <aside ref={ref} data-paused={paused ? 'true' : undefined} className="sc-inspector" aria-label={t('showcase:glyphs.inspector', 'Selected glyph')} data-testid="glyph-inspector">
      <div className="sc-inspector__stage">
        <Glyph key={name} name={name} size={104} strokeWidth={1.4} draw animate={ANIMATED.has(name)} title={glyphLabel(name)} />
      </div>
      <div className="sc-inspector__sizes" aria-hidden="true">
        {[16, 24, 48].map((s) => (
          <span key={s}>
            <Glyph name={name} size={s} />
            <small>{s}px</small>
          </span>
        ))}
      </div>
      <h3 className="sc-inspector__name">{glyphLabel(name)}</h3>
      <p className="sc-inspector__meta">
        {groupTitle(def.group)}
        {ANIMATED.has(name) ? ` · ${t('showcase:glyphs.animatedTag', 'Animated')}` : ''}
      </p>
      <code className="sc-inspector__code">{usage}</code>
      <Button size="sm" variant="secondary" icon="quill" onClick={copy}>
        {t('showcase:glyphs.copy', 'Copy usage')}
      </Button>
    </aside>
  );
}

function Featured() {
  const ref = useRef(null);
  const { paused } = useAmbient(ref);
  const [draw, setDraw] = useState(0);
  const items = [
    { el: <AnimatedCandle size={56} />, label: t('showcase:glyphs.f.candle', 'Candle flicker') },
    { el: <BlinkingEye size={56} />, label: t('showcase:glyphs.f.eye', 'Watching eye') },
    { el: <AiSigil size={56} />, label: t('showcase:glyphs.f.ai', 'AI Storyteller sigil') },
    { el: <DrippingBlood size={56} />, label: t('showcase:glyphs.f.blood', 'Falling drop') },
    { el: <SigilDraw key={draw} name="clan-tzimisce" size={56} />, label: t('showcase:glyphs.f.draw', 'Ink draw-on'), replay: true },
  ];
  return (
    <ul ref={ref} data-paused={paused ? 'true' : undefined} className="sc-featured" aria-label={t('showcase:glyphs.featured', 'Animated glyphs')}>
      {items.map((it) => (
        <li key={it.label} className="sc-featured__item" onMouseEnter={it.replay ? () => setDraw((d) => d + 1) : undefined}>
          <span className="sc-featured__art">{it.el}</span>
          <span className="sc-featured__label">{it.label}</span>
        </li>
      ))}
    </ul>
  );
}

export default function GlyphGallery() {
  const [query, setQuery] = useState('');
  const [group, setGroup] = useState('all');
  const [accent, setAccent] = useState(true);
  const [selected, setSelected] = useState('candle');

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase();
    return GROUP_ORDER.filter((g) => GLYPH_GROUPS[g] && (group === 'all' || group === g))
      .map((g) => ({
        id: g,
        names: GLYPH_GROUPS[g].filter((n) => !q || n.includes(q) || glyphLabel(n).toLowerCase().includes(q) || GLYPHS[n].label.toLowerCase().includes(q)),
      }))
      .filter((g) => g.names.length);
  }, [query, group]);
  const shown = groups.reduce((n, g) => n + g.names.length, 0);
  const total = Object.keys(GLYPHS).length;

  return (
    <Section
      id="glyphs"
      numeral="II"
      kicker={t('showcase:glyphs.kicker', 'Drawn by hand, for this table')}
      title={t('showcase:glyphs.title', 'A grimoire of {{count}} glyphs', { count: total })}
      lede={t(
        'showcase:glyphs.lede',
        'No emoji and no borrowed icon font: every mark here is an original drawing on a 24px grid. Clan and discipline sigils are abstract designs of our own, not copies of official logos. Hover a glyph to watch it drawn again; pick one to inspect it.'
      )}
    >
      <Featured />
      <div className={`sc-glyphs${accent ? '' : ' sc-glyphs--mono'}`}>
        <div className="sc-glyphs__toolbar">
          <Input
            label={t('showcase:glyphs.search', 'Search glyphs')}
            icon="search"
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t('showcase:glyphs.searchPlaceholder', 'candle, moon, fangs…')}
            data-testid="glyph-search"
          />
          <Switch label={t('showcase:glyphs.accent', 'Blood accents')} checked={accent} onChange={setAccent} />
          <PillGroup
            label={t('showcase:glyphs.filter', 'Group')}
            name="sc-glyph-group"
            value={group}
            onChange={setGroup}
            options={[{ value: 'all', label: t('showcase:glyphs.all', 'All') }, ...GROUP_ORDER.map((g) => ({ value: g, label: groupTitle(g) }))]}
            className="sc-pills--wrap"
          />
          <p className="sc-glyphs__count" aria-live="polite" data-testid="glyph-count">
            {t('showcase:glyphs.count', 'Showing {{shown}} of {{total}}', { shown, total })}
          </p>
        </div>
        <div className="sc-glyphs__body">
          <div className="sc-glyphs__groups">
            {groups.length === 0 ? (
              <EmptyState glyph="web" title={t('showcase:glyphs.none', 'Nothing in the dark matches “{{q}}”', { q: query })} />
            ) : (
              groups.map((g) => (
                <section key={g.id} className="sc-glyphs__group" aria-label={groupTitle(g.id)}>
                  <h3 className="sc-glyphs__group-title">
                    {groupTitle(g.id)} <span className="sc-glyphs__group-count">{g.names.length}</span>
                    {GAME_TERM_GROUPS.includes(g.id) && g.id !== 'line' ? (
                      <span className="sc-glyphs__original">{t('showcase:glyphs.original', 'original art')}</span>
                    ) : null}
                  </h3>
                  <ul className="sc-glyphs__grid">
                    {g.names.map((n) => (
                      <Tile key={n} name={n} selected={selected === n} onSelect={setSelected} />
                    ))}
                  </ul>
                </section>
              ))
            )}
          </div>
          <Inspector name={selected} />
        </div>
      </div>
    </Section>
  );
}
