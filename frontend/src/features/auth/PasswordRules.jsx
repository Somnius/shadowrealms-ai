import React from 'react';
import { Glyph } from '../../design';
import { t } from '../../i18n';
import './auth.css';

export const MIN_PASSWORD = 12;
export const MAX_PASSWORD_BYTES = 72;

/** UTF-8 length (bcrypt counts bytes: a Greek letter is 2). */
export function byteLength(s) {
  const str = String(s || '');
  if (typeof TextEncoder !== 'undefined') return new TextEncoder().encode(str).length;
  return unescape(encodeURIComponent(str)).length;
}

/**
 * The server's policy (backend/services/auth_security.py) as far as the browser can check it.
 * "Not a common password" is only known to the server; it is listed but never marked as met.
 */
export function passwordChecks(password, { username = '', email = '' } = {}) {
  const pw = String(password || '');
  const low = pw.toLowerCase();
  const idents = [username, String(email || '').split('@')[0]].map((x) => String(x || '').trim().toLowerCase()).filter((x) => x.length >= 3);
  return {
    length: pw.length >= MIN_PASSWORD,
    bytes: pw.length > 0 && byteLength(pw) <= MAX_PASSWORD_BYTES,
    name: pw.length > 0 && !idents.some((x) => low.includes(x)),
  };
}

/** First rule the browser can see is broken, as a translated message (null when none). */
export function passwordProblem(password, ctx) {
  const c = passwordChecks(password, ctx);
  const pw = String(password || '');
  if (!pw) return t('auth:pw.required', 'Enter a password.');
  if (!c.length) return t('auth:pw.tooShort', 'The password must be at least 12 characters long.');
  if (!c.bytes) return t('auth:pw.tooLong', 'The password is too long: at most 72 bytes (72 Latin or about 36 Greek characters).');
  if (!c.name) return t('auth:pw.containsName', 'The password must not contain your username or email.');
  return null;
}

/** The rules under a new-password field; met rules get a check mark as the user types. */
export default function PasswordRules({ password, username, email }) {
  const c = passwordChecks(password, { username, email });
  const typed = !!password;
  const rules = [
    ['length', t('auth:pw.ruleLength', 'At least 12 characters'), c.length],
    ['bytes', t('auth:pw.ruleBytes', 'At most 72 bytes (about 36 Greek letters)'), c.bytes],
    ['common', t('auth:pw.ruleCommon', 'Not a common password'), null],
    ['name', t('auth:pw.ruleName', 'Does not contain your username or email'), c.name],
  ];
  return (
    <div className="sr-pwrules">
      <span className="sr-pwrules__title">{t('auth:pw.rulesTitle', 'Password rules:')}</span>
      <ul className="sr-pwrules__list">
        {rules.map(([id, label, ok]) => {
          const met = typed && ok === true;
          return (
            <li key={id} className={met ? 'is-met' : undefined}>
              <Glyph name={met ? 'check' : 'minus'} size={12} />
              <span>{label}</span>
              {met ? <span className="sr-visually-hidden"> ({t('auth:pw.ruleMet', 'met')})</span> : null}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
