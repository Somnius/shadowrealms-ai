/**
 * Translation completeness: every key in en exists in el and vice versa (same plural forms, same
 * {{placeholders}}), and every static t('ns:key') in the code exists in the English JSON.
 */
import path from 'path';
import { NAMESPACES, resources } from '../locales';

const { collectCalls } = require('../i18nCalls.node');

function flatten(obj, prefix = '', out = {}) {
  Object.entries(obj).forEach(([k, v]) => {
    const key = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === 'object') flatten(v, key, out);
    else out[key] = v;
  });
  return out;
}

const placeholders = (s) => (String(s).match(/\{\{\s*\w+\s*\}\}/g) || []).map((p) => p.replace(/\s/g, '')).sort();

describe.each(NAMESPACES)('namespace %s', (ns) => {
  const en = flatten(resources.en[ns]);
  const el = flatten(resources.el[ns]);

  test('every English key has a Greek translation', () => {
    expect(Object.keys(en).filter((k) => !(k in el))).toEqual([]);
  });

  test('Greek has no keys that English lacks', () => {
    expect(Object.keys(el).filter((k) => !(k in en))).toEqual([]);
  });

  test('translations keep the same {{placeholders}} and are not empty', () => {
    const bad = Object.keys(en)
      .filter((k) => k in el)
      .filter((k) => JSON.stringify(placeholders(en[k])) !== JSON.stringify(placeholders(el[k])) || (en[k] !== '' && el[k] === ''));
    expect(bad).toEqual([]);
  });
});

test('every static t() key used in the code exists in the English JSON', () => {
  const { calls } = collectCalls(path.join(__dirname, '..', '..'));
  const missing = [];
  calls.forEach((c) => {
    const flat = resources.en[c.ns] ? flatten(resources.en[c.ns]) : null;
    if (!flat) {
      missing.push(`${c.ns} (unknown namespace) ${c.file}`);
      return;
    }
    const keys = c.plural ? Object.keys(c.plural).map((f) => `${c.key}_${f}`) : [c.key];
    keys.forEach((k) => {
      if (!(k in flat)) missing.push(`${c.ns}:${k} ${c.file}`);
    });
  });
  expect(missing).toEqual([]);
});
