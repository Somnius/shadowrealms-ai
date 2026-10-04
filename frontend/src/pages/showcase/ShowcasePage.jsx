/**
 * Public theme preview (/showcase): a guided tour of the design system with live components and
 * sample data only (no API calls), so it works signed out. Lazy-loaded from app/App.jsx.
 */
import { useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router';
import { Button, Card, Glyph, useAmbient, useAtmosphere } from '../../design';
import { useT } from '../../i18n';
import ChatPreview from './ChatPreview';
import ComponentsSection from './ComponentsSection';
import Editions from './Editions';
import GlyphGallery from './GlyphGallery';
import Hero, { AtmosphereControl, LanguagePills } from './Hero';
import Tokens from './Tokens';
import { useScrollToSection } from './parts';
import './showcase.css';

function TopBar() {
  const t = useT();
  const scrollTo = useScrollToSection();
  const links = [
    ['editions', t('showcase:nav.editions', 'Dice')],
    ['glyphs', t('showcase:nav.glyphs', 'Glyphs')],
    ['chat', t('showcase:nav.chat', 'Chat')],
    ['components', t('showcase:nav.components', 'Components')],
    ['tokens', t('showcase:nav.tokens', 'Palette')],
  ];
  return (
    <header className="sc-top">
      <a className="sc-top__brand" href="#sc-top" lang="en" onClick={(e) => {
        e.preventDefault();
        window.scrollTo({ top: 0 });
      }}>
        <Glyph name="logo-mark" size={22} />
        <span>ShadowRealms</span>
      </a>
      <nav className="sc-top__nav" aria-label={t('showcase:nav.label', 'Tour')}>
        <ul>
          {links.map(([id, label]) => (
            <li key={id}>
              <a
                href={`#sc-${id}`}
                onClick={(e) => {
                  e.preventDefault();
                  scrollTo(`sc-${id}`);
                }}
              >
                {label}
              </a>
            </li>
          ))}
        </ul>
      </nav>
      <div className="sc-top__tools">
        <LanguagePills compact />
        <div className="sc-top__atmo">
          <AtmosphereControl compact />
        </div>
        <Link to="/login" className="sr-btn sr-btn--primary sr-btn--sm sc-linkbtn">
          <span>{t('showcase:hero.signIn', 'Sign in')}</span>
        </Link>
      </div>
    </header>
  );
}

function FooterCta({ onBack }) {
  const t = useT();
  const ref = useRef(null);
  const { paused } = useAmbient(ref); // the candle flickers only while on screen
  return (
    <footer className="sc-end" data-testid="showcase-section-cta" ref={ref} data-paused={paused ? 'true' : undefined}>
      <Card ornate glow className="sc-end__card">
        <Glyph name="candle" animate size={40} className="sc-end__candle" />
        <h2 className="sc-end__title">{t('showcase:cta.title', 'The night is young.')}</h2>
        <p className="sc-end__body">{t('showcase:cta.body', 'Your chronicle is waiting. Sign in with your account, or ask an admin for an invite code.')}</p>
        <div className="sc-end__actions">
          <Link to="/login" className="sr-btn sr-btn--primary sr-btn--lg sc-linkbtn" data-testid="cta-login">
            <Glyph name="key" size={18} />
            <span>{t('showcase:cta.login', 'Enter ShadowRealms')}</span>
          </Link>
          <Button variant="ghost" size="lg" icon="chevron-left" onClick={onBack}>
            {t('showcase:cta.back', 'Go back')}
          </Button>
        </div>
      </Card>
      <div className="sc-credits">
        <p>
          {t(
            'showcase:cta.credits',
            'Fonts: Cinzel, Alegreya, EB Garamond, Inter and JetBrains Mono (SIL Open Font License). Charts: d3 (ISC). Animation: Motion (MIT). Every glyph and sigil is original artwork.'
          )}
        </p>
        <p>
          <Link to="/showcase/design">{t('showcase:cta.playground', 'Developer style guide')}</Link>
        </p>
      </div>
    </footer>
  );
}

export default function ShowcasePage({ onBack }) {
  const t = useT();
  const navigate = useNavigate();
  const { level } = useAtmosphere();
  const back = onBack || (() => (window.history.length > 1 ? navigate(-1) : navigate('/login')));

  useEffect(() => {
    const prev = document.title;
    document.title = t('showcase:docTitle', 'Theme preview · ShadowRealms AI');
    return () => {
      document.title = prev;
    };
  }, [t]);

  return (
    <div className="sc-page" id="sc-top" data-atmo={level} data-testid="showcase">
      <a
        className="sc-skip"
        href="#sc-main"
        onClick={(e) => {
          // Move focus, not just the scroll position, so the next Tab starts inside the tour.
          const main = document.getElementById('sc-main');
          if (!main) return;
          e.preventDefault();
          main.focus({ preventScroll: true });
          main.scrollIntoView({ block: 'start' });
        }}
      >
        {t('showcase:skip', 'Skip to the tour')}
      </a>
      <TopBar />
      <main id="sc-main" tabIndex={-1}>
        <Hero />
        <div className="sc-chapters">
          <Editions />
          <GlyphGallery />
          <ChatPreview />
          <ComponentsSection />
          <Tokens />
        </div>
      </main>
      <FooterCta onBack={back} />
    </div>
  );
}
