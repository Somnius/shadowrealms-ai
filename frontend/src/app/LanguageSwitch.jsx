import { Glyph } from '../design';
import { LANGUAGE_NAMES, setLanguage, t, useLanguage } from '../i18n';

/** EN / EL toggle for pages without the user menu (login). Each name is written in its own language. */
export default function LanguageSwitch({ className = '' }) {
  const lang = useLanguage();
  return (
    <div className={`sr-langswitch ${className}`.trim()} role="group" aria-label={t('shell:language.label', 'Language')}>
      <Glyph name="globe" size={18} />
      {Object.entries(LANGUAGE_NAMES).map(([code, name]) => (
        <button
          key={code}
          type="button"
          lang={code}
          className="sr-langswitch__btn"
          aria-pressed={lang === code}
          onClick={() => setLanguage(code)}
        >
          {name}
        </button>
      ))}
    </div>
  );
}
