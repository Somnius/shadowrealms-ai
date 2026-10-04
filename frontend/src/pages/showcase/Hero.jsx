import React, { useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Button,
  CandleGlow,
  FogLayer,
  Glyph,
  Grain,
  IconButton,
  SigilReveal,
  Vignette,
  useAmbient,
  useAtmosphere,
} from '../../design';
import { LANGUAGE_NAMES, setLanguage, t, useLanguage } from '../../i18n';
import { PillGroup, useScrollToSection } from './parts';

/* Ember positions (fixed, so a re-render never reshuffles them). */
const EMBERS = [
  [8, 0], [16, 3.2], [24, 7.4], [33, 1.6], [41, 5.1], [52, 2.4], [58, 8.2],
  [66, 4.3], [73, 0.8], [81, 6.1], [88, 2.9], [94, 9.4], [12, 10.8], [47, 11.6],
];

export function AtmosphereControl({ compact = false }) {
  const { level, choice, setLevel, systemReduced } = useAtmosphere();
  const hints = {
    full: t('showcase:atmo.fullHint', 'Fog drifts, candles flicker, dice tumble and blood drips.'),
    subtle: t('showcase:atmo.subtleHint', 'Ambient loops hold still; short effects still play.'),
    off: t('showcase:atmo.offHint', 'No motion at all. Every effect shows its final frame.'),
  };
  return (
    <div className={`sc-atmo${compact ? ' sc-atmo--compact' : ''}`}>
      <PillGroup
        label={t('showcase:atmo.label', 'Atmosphere')}
        name={compact ? 'sc-atmo-compact' : 'sc-atmo'}
        value={systemReduced ? 'off' : choice}
        onChange={setLevel}
        disabled={systemReduced}
        testId={compact ? undefined : 'atmosphere-control'}
        options={[
          { value: 'full', label: t('showcase:atmo.full', 'Full'), hint: hints.full },
          { value: 'subtle', label: t('showcase:atmo.subtle', 'Subtle'), hint: hints.subtle },
          { value: 'off', label: t('showcase:atmo.off', 'Off'), hint: hints.off },
        ]}
      />
      {compact ? null : (
        <p className="sc-atmo__hint" aria-live="polite">
          {systemReduced
            ? t('showcase:atmo.system', 'Your device asks for reduced motion, so the atmosphere stays off.')
            : hints[level]}
        </p>
      )}
    </div>
  );
}

export function LanguagePills({ compact = false }) {
  const lang = useLanguage();
  return (
    <div className={`sc-lang${compact ? ' sc-lang--compact' : ''}`} role="group" aria-label={t('showcase:lang.label', 'Language')}>
      {compact ? null : (
        <span className="sc-pills__label">
          <Glyph name="globe" size={14} /> {t('showcase:lang.label', 'Language')}
        </span>
      )}
      <div className="sc-pills__row">
        {Object.entries(LANGUAGE_NAMES).map(([code, name]) => (
          <button
            key={code}
            type="button"
            lang={code}
            className={`sc-pill sc-pill--btn${lang === code ? ' is-on' : ''}`}
            aria-pressed={lang === code}
            onClick={() => setLanguage(code)}
            data-lang={code}
          >
            {compact ? code.toUpperCase() : name}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function Hero() {
  const ref = useRef(null);
  const { paused, reduced } = useAmbient(ref);
  const [ritual, setRitual] = useState(0);
  const scrollTo = useScrollToSection();
  return (
    <section
      ref={ref}
      className={`sc-hero${reduced ? ' is-static' : ''}`}
      data-paused={paused ? 'true' : undefined}
      aria-labelledby="sc-hero-title"
      data-testid="showcase-section-hero"
    >
      <div className="sc-hero__atmos" aria-hidden="true">
        <FogLayer intensity={0.16} speed={0.7} />
        <FogLayer intensity={0.12} tint="blood" speed={0.45} className="sc-hero__fog-low" />
        <CandleGlow x="50%" y="34%" size={560} />
        <CandleGlow x="12%" y="88%" size={260} />
        <CandleGlow x="90%" y="80%" size={220} />
        <div className="sc-embers">
          {EMBERS.map(([left, delay], i) => (
            <span key={i} className="sc-ember" style={{ left: `${left}%`, '--d': `${delay}s`, '--s': `${0.6 + (i % 4) * 0.25}`, '--y': `${12 + ((i * 37) % 70)}vh` }} />
          ))}
        </div>
        <span className="sc-bat sc-bat--a">
          <Glyph name="bat" size={30} />
        </span>
        <span className="sc-bat sc-bat--b">
          <Glyph name="bat" size={20} />
        </span>
        <Vignette strength={0.8} />
        <Grain opacity={0.05} />
      </div>

      <div className="sc-hero__inner">
        <p className="sc-kicker sc-hero__kicker">{t('showcase:hero.kicker', 'Theme preview · World of Darkness, classic and V5')}</p>
        <div className="sc-hero__sigilwrap">
          <div className="sc-hero__sigil">
            <SigilReveal size={208} title={null} duration={1.6} replayKey={ritual} />
          </div>
          <IconButton
            icon="reroll"
            label={t('showcase:hero.replay', 'Replay the sigil')}
            variant="ghost"
            size="sm"
            onClick={() => setRitual((k) => k + 1)}
            className="sc-hero__replay"
          />
        </div>
        <h1 id="sc-hero-title" className="sc-hero__wordmark" lang="en">
          <span>ShadowRealms</span>
          <span className="sc-hero__ai">AI</span>
        </h1>
        <p className="sc-hero__tagline">{t('showcase:hero.tagline', 'Gothic horror chronicles, told by a Storyteller that never sleeps.')}</p>
        <p className="sc-hero__body">
          {t(
            'showcase:hero.body',
            'Classic and V5 dice, a table chat that feels like Discord, original horror glyphs and an AI Storyteller, in English and Greek. Everything below is the real interface, running live.'
          )}
        </p>
        <div className="sc-hero__cta">
          <Button variant="primary" size="lg" iconEnd="chevron-down" onClick={() => scrollTo('sc-editions')}>
            {t('showcase:hero.tour', 'Begin the tour')}
          </Button>
          <Link to="/login" className="sr-btn sr-btn--ghost sr-btn--lg sc-linkbtn">
            <Glyph name="key" size={18} />
            <span>{t('showcase:hero.signIn', 'Sign in')}</span>
          </Link>
        </div>
        <div className="sc-hero__controls">
          <LanguagePills />
          <AtmosphereControl />
        </div>
        <button type="button" className="sc-hero__cue" onClick={() => scrollTo('sc-editions')}>
          <span className="sr-visually-hidden">{t('showcase:hero.tour', 'Begin the tour')}</span>
          <Glyph name="chevron-down" size={22} />
        </button>
      </div>
    </section>
  );
}
