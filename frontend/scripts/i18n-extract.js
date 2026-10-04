#!/usr/bin/env node
/**
 * i18n key extraction for ShadowRealms.
 *
 * Every user-facing string goes through t('ns:key', 'English default', vars) (or a plural object
 * default { one, other }). This script reads those calls and keeps src/i18n/locales/en/*.json in
 * sync with the English defaults in the code, then lists what Greek (el) is missing or stale.
 *
 *   node scripts/i18n-extract.js           # report only
 *   node scripts/i18n-extract.js --write   # add new keys to en/*.json (existing values are kept)
 *
 * Only static keys are seen. Dynamic keys (t(`dice:outcome.${x}`)) must be added by hand.
 */
const fs = require('fs');
const path = require('path');
const { collectCalls } = require('../src/i18n/i18nCalls.node');

const SRC = path.join(__dirname, '..', 'src');
const LOCALES = path.join(SRC, 'i18n', 'locales');
const write = process.argv.includes('--write');

function flatten(obj, prefix = '', out = {}) {
  for (const [k, v] of Object.entries(obj)) {
    const key = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === 'object') flatten(v, key, out);
    else out[key] = v;
  }
  return out;
}

function setPath(obj, dotted, value) {
  const parts = dotted.split('.');
  let cur = obj;
  for (let i = 0; i < parts.length - 1; i += 1) {
    if (cur[parts[i]] == null) cur[parts[i]] = {};
    if (typeof cur[parts[i]] !== 'object') {
      console.log(`KEY CLASH: ${dotted} needs ${parts[i]} to be an object but it is a string (rename one key)`);
      return;
    }
    cur = cur[parts[i]];
  }
  if (cur[parts[parts.length - 1]] && typeof cur[parts[parts.length - 1]] === 'object') {
    console.log(`KEY CLASH: ${dotted} is a string but also a prefix of other keys (rename one key)`);
    return;
  }
  cur[parts[parts.length - 1]] = value;
}

function readNs(lang, ns) {
  const f = path.join(LOCALES, lang, `${ns}.json`);
  return fs.existsSync(f) ? JSON.parse(fs.readFileSync(f, 'utf8')) : {};
}

const { calls, dynamic } = collectCalls(SRC);
const byNs = {};
const clashes = [];
for (const c of calls) {
  const entries = c.plural ? Object.entries(c.plural).map(([form, text]) => [`${c.key}_${form}`, text]) : [[c.key, c.text]];
  for (const [k, text] of entries) {
    byNs[c.ns] = byNs[c.ns] || {};
    const prev = byNs[c.ns][k];
    if (prev && prev.text !== text && text != null) clashes.push(`${c.ns}:${k}  "${prev.text}" (${prev.file}) vs "${text}" (${c.file})`);
    if (!prev || prev.text == null) byNs[c.ns][k] = { text, file: c.file };
  }
}

let added = 0;
const missingEl = [];
for (const ns of Object.keys(byNs).sort()) {
  const en = readNs('en', ns);
  const flatEn = flatten(en);
  for (const [k, { text }] of Object.entries(byNs[ns])) {
    if (!(k in flatEn)) {
      added += 1;
      if (text == null) console.log(`no default text: ${ns}:${k}`);
      setPath(en, k, text == null ? k : text);
    } else if (text != null && flatEn[k] !== text) {
      console.log(`en differs from code default: ${ns}:${k}\n   json: ${JSON.stringify(flatEn[k])}\n   code: ${JSON.stringify(text)}`);
    }
  }
  if (write) {
    fs.mkdirSync(path.join(LOCALES, 'en'), { recursive: true });
    fs.writeFileSync(path.join(LOCALES, 'en', `${ns}.json`), `${JSON.stringify(en, null, 2)}\n`);
  }
}

const langs = fs.existsSync(LOCALES) ? fs.readdirSync(LOCALES).filter((d) => fs.statSync(path.join(LOCALES, d)).isDirectory()) : [];
const enFiles = fs.existsSync(path.join(LOCALES, 'en')) ? fs.readdirSync(path.join(LOCALES, 'en')) : [];
for (const f of enFiles) {
  const flatEn = flatten(JSON.parse(fs.readFileSync(path.join(LOCALES, 'en', f), 'utf8')));
  for (const lang of langs.filter((l) => l !== 'en')) {
    const p = path.join(LOCALES, lang, f);
    const flat = fs.existsSync(p) ? flatten(JSON.parse(fs.readFileSync(p, 'utf8'))) : {};
    for (const k of Object.keys(flatEn)) if (!(k in flat)) missingEl.push(`${lang}/${f}: ${k}`);
  }
}

// en keys no static call uses (may still be used through dynamic keys; check before deleting).
const used = new Set();
calls.forEach((c) => (c.plural ? Object.keys(c.plural).map((f) => `${c.key}_${f}`) : [c.key]).forEach((k) => used.add(`${c.ns}:${k}`)));
const unused = [];
for (const f of enFiles) {
  const ns = f.replace(/\.json$/, '');
  if (ns === 'glossary') continue;
  Object.keys(flatten(JSON.parse(fs.readFileSync(path.join(LOCALES, 'en', f), 'utf8')))).forEach((k) => {
    if (!used.has(`${ns}:${k}`)) unused.push(`${ns}:${k}`);
  });
}
if (unused.length) console.log(`\nen keys without a static t() call (${unused.length}; dynamic use or stale):\n  ${unused.join('\n  ')}`);

if (clashes.length) console.log(`\nSame key, different default text:\n  ${clashes.join('\n  ')}`);
if (dynamic.length) console.log(`\nDynamic keys (maintain by hand):\n  ${dynamic.join('\n  ')}`);
console.log(`\n${calls.length} calls, ${added} new en keys${write ? ' written' : ' (run with --write)'}, ${missingEl.length} missing translations`);
if (missingEl.length) console.log(`  ${missingEl.slice(0, 200).join('\n  ')}`);
