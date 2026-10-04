/**
 * Finds t('ns:key', default, vars) calls in src/ with @babel/parser (a react-scripts dependency).
 * Shared by scripts/i18n-extract.js and src/i18n/__tests__/locales.test.js (lives in src/ so the
 * test container, which mounts only src/, can load it). Not imported by the app.
 */
const fs = require('fs');
const path = require('path');
const { parse } = require('@babel/parser');

const SKIP_DIRS = new Set(['__tests__', 'i18n', 'node_modules']);
const FILE_RE = /\.(js|jsx)$/;
const SKIP_FILES = /\.test\.(js|jsx)$/;

function listFiles(dir, out = []) {
  for (const name of fs.readdirSync(dir)) {
    const full = path.join(dir, name);
    if (fs.statSync(full).isDirectory()) {
      if (!SKIP_DIRS.has(name)) listFiles(full, out);
    } else if (FILE_RE.test(name) && !SKIP_FILES.test(name)) {
      out.push(full);
    }
  }
  return out;
}

function literalText(node) {
  if (!node) return null;
  if (node.type === 'StringLiteral') return node.value;
  if (node.type === 'TemplateLiteral' && node.expressions.length === 0) return node.quasis[0].value.cooked;
  return undefined; // not static
}

function walk(node, visit) {
  if (!node || typeof node.type !== 'string') return;
  visit(node);
  for (const key of Object.keys(node)) {
    if (key === 'loc' || key === 'start' || key === 'end' || key === 'leadingComments' || key === 'trailingComments') continue;
    const v = node[key];
    if (Array.isArray(v)) v.forEach((c) => c && typeof c.type === 'string' && walk(c, visit));
    else if (v && typeof v.type === 'string') walk(v, visit);
  }
}

function isT(callee) {
  if (callee.type === 'Identifier') return callee.name === 't';
  return callee.type === 'MemberExpression' && !callee.computed && callee.property.name === 't' && callee.object.type === 'Identifier' && /^(i18n|i18next)$/.test(callee.object.name);
}

function collectCalls(srcDir) {
  const calls = [];
  const dynamic = [];
  for (const file of listFiles(srcDir)) {
    const code = fs.readFileSync(file, 'utf8');
    if (!/\bt\(/.test(code)) continue;
    let ast;
    try {
      ast = parse(code, { sourceType: 'module', plugins: ['jsx', 'classProperties', 'optionalChaining'] });
    } catch (e) {
      throw new Error(`${file}: ${e.message}`);
    }
    const rel = path.relative(srcDir, file);
    walk(ast.program, (node) => {
      if (node.type !== 'CallExpression' || !isT(node.callee) || node.arguments.length === 0) return;
      const [k, d] = node.arguments;
      const key = literalText(k);
      if (typeof key !== 'string') {
        dynamic.push(`${rel}:${node.loc.start.line}`);
        return;
      }
      if (!key.includes(':')) return; // not one of ours
      const [ns, ...rest] = key.split(':');
      const entry = { ns, key: rest.join(':'), file: `${rel}:${node.loc.start.line}`, text: null };
      if (d && d.type === 'ObjectExpression') {
        entry.plural = {};
        d.properties.forEach((p) => {
          const name = p.key && (p.key.name || p.key.value);
          entry.plural[name] = literalText(p.value) ?? null;
        });
      } else {
        const text = literalText(d);
        entry.text = typeof text === 'string' ? text : null;
      }
      calls.push(entry);
    });
  }
  return { calls, dynamic };
}

module.exports = { collectCalls, listFiles };
