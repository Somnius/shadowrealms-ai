import { useEffect, useState } from 'react';
import { t } from '../../i18n';
import { contrastRatio, formatRatio, readToken, wcagLevel } from './contrast';
import { Section } from './parts';

const PAGE = ['--sr-night-900', '#0f0f1e'];
const PANEL = ['--sr-night-800', '#16213e'];
const TEXT = ['--sr-bone-100', '#e0e0e0'];
const MUTED = ['--sr-bone-500', '#8b8b9f'];

export const PALETTE = [
  {
    id: 'night',
    tokens: [
      ['--sr-night-950', '#07070f'],
      ['--sr-night-900', '#0f0f1e'],
      ['--sr-night-850', '#0f1729'],
      ['--sr-night-800', '#16213e'],
      ['--sr-night-750', '#1a2547'],
      ['--sr-night-700', '#2a2a4e'],
    ],
  },
  {
    id: 'bone',
    tokens: [
      ['--sr-bone-50', '#f5f2ea'],
      ['--sr-bone-100', '#e0e0e0'],
      ['--sr-bone-300', '#b5b5c3'],
      ['--sr-bone-500', '#8b8b9f'],
    ],
  },
  {
    id: 'blood',
    tokens: [
      ['--sr-blood-300', '#fda4af'],
      ['--sr-blood-400', '#ff6b81'],
      ['--sr-blood-500', '#e94560'],
      ['--sr-blood-600', '#c2334d'],
      ['--sr-blood-700', '#8b0000'],
      ['--sr-blood-900', '#3b0a14'],
    ],
  },
  {
    id: 'arcane',
    tokens: [
      ['--sr-arcane-300', '#c4b5fd'],
      ['--sr-arcane-400', '#b794f6'],
      ['--sr-arcane-500', '#9d4edd'],
      ['--sr-gold-300', '#fde68a'],
      ['--sr-gold-400', '#fbbf24'],
      ['--sr-ember-500', '#ff9500'],
    ],
  },
  {
    id: 'status',
    tokens: [
      ['--sr-ok-400', '#4ade80'],
      ['--sr-warn-400', '#fbbf24'],
      ['--sr-danger-400', '#f87171'],
      ['--sr-info-400', '#7dd3fc'],
    ],
  },
];

function paletteTitle(id) {
  return {
    night: t('showcase:tokens.night', 'Night (surfaces)'),
    bone: t('showcase:tokens.bone', 'Bone (text)'),
    blood: t('showcase:tokens.blood', 'Blood (brand)'),
    arcane: t('showcase:tokens.arcane', 'Arcane, gold and ember'),
    status: t('showcase:tokens.status', 'Status'),
  }[id];
}

/** Token values read from the stylesheet once mounted (so the ratios follow the real CSS). */
function useTokenValues() {
  const [values, setValues] = useState(null);
  useEffect(() => {
    const all = [PAGE, PANEL, TEXT, MUTED, ...PALETTE.flatMap((g) => g.tokens)];
    setValues(Object.fromEntries(all.map(([name, hex]) => [name, readToken(name, hex)])));
  }, []);
  return (name, hex) => (values && values[name]) || hex;
}

function Ratio({ fg, bg, label }) {
  const r = contrastRatio(fg, bg);
  const level = wcagLevel(r);
  return (
    <span className={`sc-ratio sc-ratio--${level.replace(' ', '-').toLowerCase()}`} title={label}>
      <span className="sr-visually-hidden">{label}: </span>
      {formatRatio(r)}
      <small>{level === 'decor' ? t('showcase:tokens.decor', 'decor') : level}</small>
    </span>
  );
}

function Swatches() {
  const value = useTokenValues();
  const page = value(...PAGE);
  const panel = value(...PANEL);
  const text = value(...TEXT);
  const muted = value(...MUTED);
  return (
    <div className="sc-palette">
      {PALETTE.map((g) => (
        <section key={g.id} className="sc-palette__group" aria-label={paletteTitle(g.id)}>
          <h3 className="sc-sub">{paletteTitle(g.id)}</h3>
          <ul className="sc-swatches">
            {g.tokens.map(([name, hex]) => {
              const v = value(name, hex);
              return (
                <li key={name} className="sc-swatch" data-token={name}>
                  <span className="sc-swatch__chip" style={{ background: `var(${name}, ${hex})` }}>
                    <span style={{ color: `var(${name}, ${hex})` }} aria-hidden="true">
                      Aa
                    </span>
                  </span>
                  <code className="sc-swatch__name">{name.replace('--sr-', '')}</code>
                  <span className="sc-swatch__hex">{v}</span>
                  {g.id === 'night' ? (
                    <span className="sc-swatch__ratios">
                      <Ratio fg={text} bg={v} label={t('showcase:tokens.textOn', 'Primary text on this surface')} />
                      <Ratio fg={muted} bg={v} label={t('showcase:tokens.mutedOn', 'Muted text on this surface')} />
                    </span>
                  ) : (
                    <span className="sc-swatch__ratios">
                      <Ratio fg={v} bg={page} label={t('showcase:tokens.onPage', 'Contrast on the page background')} />
                      <Ratio fg={v} bg={panel} label={t('showcase:tokens.onPanel', 'Contrast on a panel')} />
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      ))}
      <p className="sc-hint">
        {t(
          'showcase:tokens.ratioHint',
          'Ratios are computed live from the stylesheet. Surfaces show primary and muted text on them; every other colour is measured on the page background, then on a panel. 4.5 and up passes AA for body text, 7 and up AAA.'
        )}
      </p>
    </div>
  );
}

const SCALE = [
  ['3xl', 38],
  ['2xl', 30],
  ['xl', 24],
  ['lg', 20],
  ['chat', 17],
  ['base', 16],
  ['md', 14],
  ['sm', 13],
  ['xs', 12],
];

function Typography() {
  const greek = 'Η νύχτα είναι νέα και η πόλη πεινά';
  return (
    <div className="sc-type">
      <div className="sc-type__faces">
        {[
          ['display', t('showcase:tokens.display', 'Display'), 'Cinzel · Alegreya (Ελληνικά)'],
          ['body', t('showcase:tokens.body', 'Prose and chat'), 'EB Garamond'],
          ['ui', t('showcase:tokens.ui', 'Interface'), 'Inter'],
          ['mono', t('showcase:tokens.mono', 'Dice and keys'), 'JetBrains Mono'],
        ].map(([face, role, font]) => (
          <div key={face} className={`sc-face sc-face--${face}`}>
            <p className="sc-face__meta">
              <strong>{role}</strong> <span>{font}</span>
            </p>
            <p className="sc-face__sample" lang="en">
              The night is young.
            </p>
            <p className="sc-face__sample" lang="el">
              Η νύχτα είναι νέα.
            </p>
          </div>
        ))}
      </div>

      <div className="sc-greek" data-testid="greek-caps">
        <h3 className="sc-sub">{t('showcase:tokens.greekTitle', 'Greek capitals, done right')}</h3>
        <p className="sc-hint">
          {t(
            'showcase:tokens.greekHint',
            'Greek capitals drop their accents. The browser does this for us when the text is marked as Greek, so headings never show stray tonos marks.'
          )}
        </p>
        <div className="sc-greek__rows">
          <div className="sc-greek__row">
            <span className="sc-greek__tag">{t('showcase:tokens.source', 'Source text')}</span>
            <span className="sc-greek__text" lang="el">
              {greek}
            </span>
          </div>
          <div className="sc-greek__row is-wrong">
            <span className="sc-greek__tag">{t('showcase:tokens.wrong', 'Marked as English (wrong)')}</span>
            <span className="sc-greek__text sr-caps" lang="en">
              {greek}
            </span>
          </div>
          <div className="sc-greek__row is-right">
            <span className="sc-greek__tag">{t('showcase:tokens.right', 'Marked as Greek (right)')}</span>
            <span className="sc-greek__text sr-caps" lang="el" data-testid="greek-caps-right">
              {greek}
            </span>
          </div>
        </div>
      </div>

      <div className="sc-scale" aria-label={t('showcase:tokens.scale', 'Type scale')}>
        <h3 className="sc-sub">{t('showcase:tokens.scale', 'Type scale')}</h3>
        <ul>
          {SCALE.map(([name, px]) => (
            <li key={name}>
              <code>
                {name} · {px}px
              </code>
              <span style={{ fontSize: `var(--sr-text-${name}, ${px}px)` }}>{t('showcase:tokens.scaleSample', 'Blood remembers')}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export default function Tokens() {
  return (
    <Section
      id="tokens"
      numeral="V"
      kicker={t('showcase:tokens.kicker', 'The ink and the paper')}
      title={t('showcase:tokens.title', 'Palette and type')}
      lede={t(
        'showcase:tokens.lede',
        'Night blues, bone whites and one red that means blood. Every text colour is checked against the surfaces it sits on, and every font covers Greek.'
      )}
    >
      <Swatches />
      <Typography />
    </Section>
  );
}
