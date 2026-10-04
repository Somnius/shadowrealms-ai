/** Every showcase key exists in English and Greek, including the dynamic glyph names. */
import path from 'path';
import { NAMESPACES, resources } from '../../../i18n/locales';
import { GLYPHS } from '../../../design/glyphs/glyphData';
import { GAME_TERM_GROUPS } from '../GlyphGallery';

const { collectCalls } = require('../../../i18n/i18nCalls.node');

function flatten(obj, prefix = '', out = {}) {
  Object.entries(obj).forEach(([k, v]) => {
    const key = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === 'object') flatten(v, key, out);
    else out[key] = v;
  });
  return out;
}

const en = flatten(resources.en.showcase || {});
const el = flatten(resources.el.showcase || {});

test('the showcase namespace is registered', () => {
  expect(NAMESPACES).toContain('showcase');
});

test('English and Greek have the same keys, none empty', () => {
  expect(Object.keys(en).sort()).toEqual(Object.keys(el).sort());
  expect(Object.entries(el).filter(([, v]) => !String(v).trim())).toEqual([]);
});

test('every static showcase t() call has an English and a Greek string', () => {
  const { calls } = collectCalls(path.join(__dirname, '..'));
  const used = calls.filter((c) => c.ns === 'showcase').map((c) => c.key);
  expect(used.length).toBeGreaterThan(100);
  expect(used.filter((k) => !(k in en))).toEqual([]);
  expect(used.filter((k) => !(k in el))).toEqual([]);
});

test('every glyph outside the game-term groups has a translated name', () => {
  const names = Object.keys(GLYPHS).filter((n) => !GAME_TERM_GROUPS.includes(GLYPHS[n].group));
  expect(names.filter((n) => !(`glyph.${n}` in en))).toEqual([]);
  expect(names.filter((n) => !(`glyph.${n}` in el))).toEqual([]);
});

test('Greek strings are actually Greek (not copied English)', () => {
  const copied = Object.keys(en).filter((k) => en[k] === el[k] && /[a-z]{4,}\s+[a-z]{4,}/i.test(en[k]));
  // allowed: edition titles and game terms, which stay English
  expect(copied.filter((k) => !/^(editions\.(v5Title|classicTitle)|comp\.bloodPotency)$/.test(k))).toEqual([]);
});
