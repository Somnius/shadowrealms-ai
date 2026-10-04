/**
 * i18n for ShadowRealms (EN / EL), on i18next + react-i18next.
 *
 * Call sites use `t('namespace:key', 'English default', vars)`. The English default is what the
 * code shows if a key is missing from the JSON (and what scripts/i18n-extract.js writes into
 * locales/en). Plurals: pass `{ count }` and an object default `{ one, other }`; the JSON then has
 * `key_one` / `key_other` (Greek and English both use only these two forms).
 *
 * Language order: ?lang= → users.ui_language (after login, see AuthContext) → localStorage
 * `sr_lang` (manual choice) → navigator.languages (any el* → el) → en.
 * World of Darkness game terms stay English; see ./glossary.js.
 */
import i18next from 'i18next';
import { initReactI18next, useTranslation } from 'react-i18next';
import { NAMESPACES, resources } from './locales';

export const LANGUAGES = ['en', 'el'];
/** Each language named in itself (never translated). */
export const LANGUAGE_NAMES = { en: 'English', el: 'Ελληνικά' };
export const STORAGE_KEY = 'sr_lang';
/** Who made the stored choice: a user id, or 'anon' when it was made while signed out. */
export const OWNER_KEY = 'sr_lang_owner';
let languageOwner = null;

export function normalizeLanguage(value) {
  const v = String(value || '').trim().toLowerCase();
  if (v.startsWith('el')) return 'el';
  if (v.startsWith('en')) return 'en';
  return null;
}

function readStored() {
  try {
    return normalizeLanguage(window.localStorage.getItem(STORAGE_KEY));
  } catch (e) {
    return null;
  }
}

function writeStored(lang) {
  try {
    if (lang) {
      window.localStorage.setItem(STORAGE_KEY, lang);
      window.localStorage.setItem(OWNER_KEY, languageOwner || 'anon');
    } else {
      window.localStorage.removeItem(STORAGE_KEY);
      window.localStorage.removeItem(OWNER_KEY);
    }
  } catch (e) {
    /* private mode: the choice lasts for this page only */
  }
}

/** Browser languages in order; the first el* or en* wins. */
export function browserLanguage(list) {
  const langs = list || (typeof navigator !== 'undefined' ? navigator.languages || [navigator.language] : []);
  for (const l of langs) {
    const n = normalizeLanguage(l);
    if (n) return n;
  }
  return 'en';
}

export function detectLanguage() {
  let fromUrl = null;
  try {
    fromUrl = normalizeLanguage(new URLSearchParams(window.location.search).get('lang'));
  } catch (e) {
    fromUrl = null;
  }
  return fromUrl || readStored() || browserLanguage();
}

/** <html lang>, plus portal roots that copied it when they were created. */
function syncDocumentLanguage(lang) {
  if (typeof document === 'undefined') return;
  document.documentElement.setAttribute('lang', lang);
  document.querySelectorAll('.sr-portal[lang], .sr-app[lang]').forEach((n) => n.setAttribute('lang', lang));
}

i18next.use(initReactI18next).init({
  resources,
  lng: detectLanguage(),
  fallbackLng: 'en',
  supportedLngs: LANGUAGES,
  ns: NAMESPACES,
  defaultNS: 'common',
  nsSeparator: ':',
  keySeparator: '.',
  interpolation: { escapeValue: false }, // React escapes
  returnNull: false,
  initAsync: false, // resources are bundled: init synchronously
  react: { useSuspense: false },
});
syncDocumentLanguage(i18next.language);
i18next.on('languageChanged', syncDocumentLanguage);

function pickPlural(def, vars) {
  if (def && typeof def === 'object') {
    const n = vars && typeof vars.count === 'number' ? vars.count : 0;
    let rule = 'other';
    try {
      rule = new Intl.PluralRules(i18next.language || 'en').select(n);
    } catch (e) {
      rule = n === 1 ? 'one' : 'other';
    }
    return def[rule] != null ? def[rule] : def.other;
  }
  return def;
}

/** Fills {{name}} placeholders (used for defaults outside i18next, e.g. tests). */
export function interpolate(text, vars) {
  if (!vars || typeof text !== 'string') return text;
  return text.replace(/\{\{\s*(\w+)\s*\}\}/g, (m, name) =>
    Object.prototype.hasOwnProperty.call(vars, name) && vars[name] != null ? String(vars[name]) : m
  );
}

/** t(key, englishDefault, vars?) → string in the active language. */
export function t(key, def, vars) {
  const fallback = pickPlural(def, vars);
  const opts = { ...(vars || {}) };
  if (fallback != null) opts.defaultValue = fallback;
  const out = i18next.t(key, opts);
  return out == null || out === '' ? interpolate(fallback == null ? key : fallback, vars) : out;
}

export function getLanguage() {
  return normalizeLanguage(i18next.language) || 'en';
}

/** Locale for Intl formatters (dates, numbers, lists). */
export function getLocale(lang = getLanguage()) {
  return lang === 'el' ? 'el-GR' : 'en-GB';
}

/** Number in the active locale (12.345,6 in Greek). */
export function formatNumber(n, opts) {
  try {
    return new Intl.NumberFormat(getLocale(), opts).format(n);
  } catch (e) {
    return String(n);
  }
}

/** "A, B and C" / "Α, Β και Γ". */
export function formatList(items, type = 'conjunction') {
  try {
    return new Intl.ListFormat(getLocale(), { style: 'long', type }).format(items.map(String));
  } catch (e) {
    return items.join(', ');
  }
}

const listeners = new Set();

/**
 * Persisting hook for the server copy (AuthContext registers PUT /users/me/language here so this
 * module doesn't need to know about tokens).
 */
export function onLanguageChosen(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

/**
 * Switch language.
 * - remember: keep it in localStorage (the manual choice, also used on logged-out pages)
 * - save: tell onLanguageChosen listeners (AuthContext saves it on the server)
 * A user's click does both; a value applied from the server only remembers.
 */
export function setLanguage(lang, { remember = true, save = remember } = {}) {
  const next = normalizeLanguage(lang) || 'en';
  if (remember) writeStored(next);
  if (save) {
    listeners.forEach((fn) => {
      try {
        fn(next);
      } catch (e) {
        /* saving is best effort */
      }
    });
  }
  if (next !== i18next.language) return i18next.changeLanguage(next);
  syncDocumentLanguage(next);
  return Promise.resolve();
}

/** The manual choice stored in this browser, or null when the language follows the browser. */
export function storedLanguage() {
  return readStored();
}

/** User id that made the stored choice, 'anon' (made while signed out) or null (unknown/older). */
export function storedLanguageOwner() {
  try {
    return window.localStorage.getItem(OWNER_KEY);
  } catch (e) {
    return null;
  }
}

/** AuthProvider tells us who is signed in, so a stored choice is tagged with its owner. */
export function setLanguageOwner(userId) {
  languageOwner = userId == null ? null : String(userId);
}

/** Forget the stored choice and follow the browser again (used when it belonged to someone else). */
export function forgetStoredLanguage() {
  writeStored(null);
  return setLanguage(browserLanguage(), { remember: false, save: false });
}

/** Re-renders on language change; returns the same t(key, default, vars). */
export function useT() {
  useTranslation(NAMESPACES);
  return t;
}

/** Current language as React state. */
export function useLanguage() {
  const { i18n } = useTranslation(NAMESPACES);
  return normalizeLanguage(i18n.language) || 'en';
}

export { i18next as i18n };
export default t;
