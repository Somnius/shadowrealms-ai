/**
 * Small Markdown renderer for the in-app README (GitHub-flavoured subset).
 *
 * Supported: fenced code blocks (``` or ~~~, optional language), headings, paragraphs,
 * hard breaks, bold/italic/strikethrough, inline code, links, images, autolinks,
 * horizontal rules, block quotes, nested ordered/unordered lists, task list items,
 * tables with alignment, and raw HTML blocks such as <div align="center">.
 * Not supported: indented code blocks, setext headings, reference-style links,
 * inline raw HTML (it is shown as text).
 *
 * The output is HTML and must still go through sanitizeRichHtml (DOMPurify) before it
 * is rendered: raw HTML blocks from the README are passed through to it unchanged.
 */

const REPO = 'Somnius/shadowrealms-ai';
/** Relative links in the README point at the file on GitHub. */
export const README_LINK_BASE = `https://github.com/${REPO}/blob/main/`;
/** Relative images in the README are loaded from raw.githubusercontent.com (CSP img-src allows https:). */
export const README_IMAGE_BASE = `https://raw.githubusercontent.com/${REPO}/main/`;
/** Heading ids get this prefix so they can't clash with ids in the app. */
export const HEADING_ID_PREFIX = 'readme-';

const escapeHtml = (s) =>
  String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');

// Like escapeHtml, but keeps entities the author wrote (&mdash;, &#169;) working.
const escapeText = (s) =>
  String(s)
    .replace(/&(?!#?[a-zA-Z0-9]+;)/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

const SCHEME_RE = /^[a-z][a-z0-9+.-]*:/i;
const repoPath = (url) => url.replace(/^(\.\/)+/, '').replace(/^\/+/, '');

/** href for a link, or null when the link must not be clickable (javascript:, data:, …). */
export const resolveLink = (url) => {
  const u = String(url || '').trim();
  if (!u) return null;
  if (u.startsWith('#')) return `#${HEADING_ID_PREFIX}${u.slice(1)}`;
  if (/^(https?:|mailto:)/i.test(u)) return u;
  if (SCHEME_RE.test(u) || u.startsWith('//')) return null;
  return README_LINK_BASE + repoPath(u);
};

/** src for an image, or null when it can't be shown (only https: and repo paths are). */
export const resolveImage = (url) => {
  const u = String(url || '').trim();
  if (!u) return null;
  if (/^https:\/\//i.test(u)) return u;
  if (SCHEME_RE.test(u) || u.startsWith('//') || u.startsWith('#')) return null;
  return README_IMAGE_BASE + repoPath(u);
};

/* ------------------------------------------------------------------ inline */

const AUTOLINK_RE = /<((?:https?:\/\/|mailto:)[^\s<>]+)>/gi;
// URLs can't contain "(" and are length-capped: an unclosed "(" can't make these backtrack for seconds.
const IMAGE_RE = /!\[([^\]]*)\]\(\s*<?([^\s()>]{1,2048})>?(?:\s+"([^"]*)")?\s*\)/g;
const LINK_RE = /\[((?:[^[\]]|\[[^\]]*\])*)\]\(\s*<?([^\s()>]{1,2048})>?(?:\s+"([^"]*)")?\s*\)/g;
const SLOT_RE = /\uE000(\d+)\uE000/g;
const HAS_SLOT_RE = /\uE000\d+\uE000/;
// Slots only belong in text; inside an attribute (href, alt, title) they are dropped.
const noSlots = (s) => (s ? String(s).replace(SLOT_RE, '') : s);

// Code spans: a run of backticks up to the next run of the same length. A linear scan
// instead of a backreference regex, which backtracks for seconds on long backtick runs.
const replaceCodeSpans = (s, onSpan) => {
  const runs = [];
  const runRe = /`+/g;
  let m;
  while ((m = runRe.exec(s))) runs.push({ start: m.index, len: m[0].length });
  const nextSame = new Array(runs.length).fill(-1);
  const lastByLen = new Map();
  for (let j = runs.length - 1; j >= 0; j -= 1) {
    nextSame[j] = lastByLen.has(runs[j].len) ? lastByLen.get(runs[j].len) : -1;
    lastByLen.set(runs[j].len, j);
  }
  let out = '';
  let pos = 0;
  let j = 0;
  while (j < runs.length) {
    const close = nextSame[j];
    if (close < 0) {
      j += 1;
      continue;
    }
    const open = runs[j];
    const end = runs[close];
    out += s.slice(pos, open.start) + onSpan(s.slice(open.start + open.len, end.start));
    pos = end.start + end.len;
    j = close + 1;
  }
  return out + s.slice(pos);
};

const linkHtml = (href, inner, title) => {
  const external = !href.startsWith('#');
  return (
    `<a href="${escapeHtml(href)}"${title ? ` title="${escapeHtml(title)}"` : ''}` +
    `${external ? ' target="_blank" rel="noopener noreferrer"' : ''}>${inner}</a>`
  );
};

const imageHtml = (alt, url, title) => {
  const src = resolveImage(url);
  if (!src) return alt ? `<span class="sr-md-img-missing">${escapeText(alt)}</span>` : '';
  return (
    `<img src="${escapeHtml(src)}" alt="${escapeHtml(alt)}"` +
    `${title ? ` title="${escapeHtml(title)}"` : ''} loading="lazy">`
  );
};

// Escape and apply emphasis to text that has no code spans, links or images left in it.
const formatText = (s) => {
  let t = escapeText(s);
  t = t.replace(/\*\*(?=\S)([\s\S]*?\S)\*\*/g, '<strong>$1</strong>');
  t = t.replace(/(^|[^\w])__(?=\S)([\s\S]*?\S)__(?!\w)/g, '$1<strong>$2</strong>');
  t = t.replace(/(^|[^*\w])\*(?=[^\s*])([^*]*?[^\s*])\*(?!\*)/g, '$1<em>$2</em>');
  t = t.replace(/(^|[^\w])_(?=[^\s_])([^_]*?[^\s_])_(?!\w)/g, '$1<em>$2</em>');
  t = t.replace(/~~(?=\S)([\s\S]*?\S)~~/g, '<del>$1</del>');
  t = t.replace(/(?: {2,}|\\)\n/g, '<br>\n');
  return t;
};

export const renderInline = (src) => {
  const slots = [];
  const keep = (html) => `\uE000${slots.push(html) - 1}\uE000`;
  let s = String(src).replace(/\uE000/g, '');

  s = replaceCodeSpans(s, (code) => {
    const body = /^ [\s\S]* $/.test(code) && code.trim() ? code.slice(1, -1) : code;
    return keep(`<code>${escapeHtml(body.replace(/\n/g, ' '))}</code>`);
  });
  s = s.replace(AUTOLINK_RE, (m, url) => keep(linkHtml(url, escapeText(url))));
  s = s.replace(IMAGE_RE, (m, alt, url, title) =>
    keep(imageHtml(noSlots(alt), noSlots(url), noSlots(title))),
  );
  s = s.replace(LINK_RE, (m, label, url, title) => {
    const inner = formatText(label);
    const href = resolveLink(noSlots(url));
    return keep(href ? linkHtml(href, inner, noSlots(title)) : inner);
  });
  s = formatText(s);

  // Slots can contain other slots (an image inside a link), so restore until none are left.
  for (let n = 0; n < 5 && HAS_SLOT_RE.test(s); n += 1) {
    s = s.replace(SLOT_RE, (m, i) => slots[Number(i)]);
  }
  return s;
};

/* ------------------------------------------------------------------- blocks */

const FENCE_RE = /^( {0,3})(`{3,}|~{3,})\s*([^\s`]*)[^`]*$/;
const HEADING_RE = /^ {0,3}(#{1,6})(?:[ \t]+(.*?))?(?:[ \t]+#+)?[ \t]*$/;
const HR_RE = /^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$/;
const QUOTE_RE = /^ {0,3}> ?/;
const LIST_RE = /^( *)([-*+]|\d{1,9}[.)])(?:[ \t]+(.*))?$/;
const HTML_BLOCK_RE = /^ {0,3}<\/?[a-zA-Z][\w-]*(?:\s[^>]*)?\/?>/;
const COMMENT_RE = /^ {0,3}<!--/;
const TABLE_SEP_RE = /^ {0,3}\|?[ \t]*:?-+:?[ \t]*(?:\|[ \t]*:?-+:?[ \t]*)*\|?[ \t]*$/;

const MAX_NESTING = 32;

const isBlank = (line) => /^\s*$/.test(line);
const indentOf = (line) => line.match(/^ */)[0].length;

const startsBlock = (line) =>
  FENCE_RE.test(line) ||
  HEADING_RE.test(line) ||
  HR_RE.test(line) ||
  QUOTE_RE.test(line) ||
  COMMENT_RE.test(line) ||
  HTML_BLOCK_RE.test(line) ||
  (LIST_RE.test(line) && LIST_RE.exec(line)[3] !== undefined);

const splitRow = (line) => {
  let s = line.trim();
  if (s.startsWith('|')) s = s.slice(1);
  if (s.endsWith('|') && !s.endsWith('\\|')) s = s.slice(0, -1);
  const cells = [];
  let cur = '';
  let inCode = false;
  for (let i = 0; i < s.length; i += 1) {
    const ch = s[i];
    if (ch === '\\' && s[i + 1] === '|') {
      cur += '|';
      i += 1;
    } else if (ch === '`') {
      inCode = !inCode;
      cur += ch;
    } else if (ch === '|' && !inCode) {
      cells.push(cur.trim());
      cur = '';
    } else {
      cur += ch;
    }
  }
  cells.push(cur.trim());
  return cells;
};

const slugify = (text) =>
  text
    .replace(/!?\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/[`*_~]/g, '')
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s-]/gu, '')
    .trim()
    .replace(/\s/g, '-');

class BlockParser {
  constructor() {
    this.slugs = new Map();
    this.depth = 0;
  }

  headingId(text) {
    const base = slugify(text) || 'section';
    const seen = this.slugs.get(base) || 0;
    this.slugs.set(base, seen + 1);
    return HEADING_ID_PREFIX + (seen ? `${base}-${seen}` : base);
  }

  /** Render a list of lines as block HTML. tight: paragraphs without <p> (list items). */
  blocks(lines, tight = false) {
    // Lists and quotes nest by recursion; past this depth the rest is plain text, so a line
    // like "- - - - …" can't overflow the stack.
    if (this.depth >= MAX_NESTING) {
      return `<p>${escapeText(lines.join(' ').trim())}</p>`;
    }
    this.depth += 1;
    try {
      return this.blocksAt(lines, tight);
    } finally {
      this.depth -= 1;
    }
  }

  blocksAt(lines, tight) {
    const out = [];
    let i = 0;
    while (i < lines.length) {
      const line = lines[i];
      if (isBlank(line)) {
        i += 1;
        continue;
      }

      const fence = FENCE_RE.exec(line);
      if (fence) {
        const [, indent, marker, lang] = fence;
        const close = new RegExp(`^ {0,3}${marker[0] === '`' ? '`' : '~'}{${marker.length},}[ \\t]*$`);
        const body = [];
        i += 1;
        while (i < lines.length && !close.test(lines[i])) {
          body.push(lines[i].replace(new RegExp(`^ {0,${indent.length}}`), ''));
          i += 1;
        }
        i += 1; // closing fence (or end of input)
        const cls = lang ? ` class="language-${escapeHtml(lang)}"` : '';
        out.push(`<pre class="sr-md-code"><code${cls}>${escapeHtml(body.join('\n'))}</code></pre>`);
        continue;
      }

      if (COMMENT_RE.test(line)) {
        while (i < lines.length && !lines[i].includes('-->')) i += 1;
        i += 1;
        continue;
      }

      if (HTML_BLOCK_RE.test(line)) {
        // Like GitHub: an HTML block runs to the next blank line; DOMPurify cleans it later.
        const html = [];
        while (i < lines.length && !isBlank(lines[i])) {
          html.push(lines[i]);
          i += 1;
        }
        out.push(html.join('\n'));
        continue;
      }

      const heading = HEADING_RE.exec(line);
      if (heading) {
        const level = heading[1].length;
        const text = heading[2] || '';
        out.push(`<h${level} id="${escapeHtml(this.headingId(text))}">${renderInline(text)}</h${level}>`);
        i += 1;
        continue;
      }

      if (HR_RE.test(line)) {
        out.push('<hr>');
        i += 1;
        continue;
      }

      if (
        line.includes('|') &&
        i + 1 < lines.length &&
        TABLE_SEP_RE.test(lines[i + 1]) &&
        splitRow(lines[i + 1]).length === splitRow(line).length
      ) {
        i = this.table(lines, i, out);
        continue;
      }

      if (QUOTE_RE.test(line)) {
        const quoted = [];
        while (i < lines.length && QUOTE_RE.test(lines[i])) {
          quoted.push(lines[i].replace(QUOTE_RE, ''));
          i += 1;
        }
        out.push(`<blockquote>${this.blocks(quoted)}</blockquote>`);
        continue;
      }

      if (LIST_RE.test(line) && LIST_RE.exec(line)[3] !== undefined) {
        i = this.list(lines, i, out);
        continue;
      }

      const para = [];
      while (i < lines.length && !isBlank(lines[i]) && (para.length === 0 || !startsBlock(lines[i]))) {
        para.push(lines[i].trimStart());
        i += 1;
      }
      const inner = renderInline(para.join('\n'));
      out.push(tight ? inner : `<p>${inner}</p>`);
    }
    return out.join('\n');
  }

  table(lines, start, out) {
    const header = splitRow(lines[start]);
    const aligns = splitRow(lines[start + 1]).map((c) => {
      const left = c.startsWith(':');
      const right = c.endsWith(':');
      if (left && right) return 'center';
      if (right) return 'right';
      if (left) return 'left';
      return '';
    });
    const cell = (tag, text, col) => {
      const align = aligns[col] ? ` style="text-align: ${aligns[col]}"` : '';
      return `<${tag}${align}>${renderInline(text || '')}</${tag}>`;
    };
    let i = start + 2;
    const rows = [];
    while (i < lines.length && !isBlank(lines[i]) && lines[i].includes('|')) {
      const cells = splitRow(lines[i]);
      rows.push(`<tr>${header.map((_, c) => cell('td', cells[c], c)).join('')}</tr>`);
      i += 1;
    }
    out.push(
      '<div class="sr-md-table"><table>' +
        `<thead><tr>${header.map((h, c) => cell('th', h, c)).join('')}</tr></thead>` +
        `<tbody>${rows.join('')}</tbody></table></div>`
    );
    return i;
  }

  list(lines, start, out) {
    const first = LIST_RE.exec(lines[start]);
    const ordered = /\d/.test(first[2]);
    const items = [];
    let loose = false;
    let cur = null;
    let i = start;

    while (i < lines.length) {
      const line = lines[i];
      const m = LIST_RE.exec(line);
      const isItem = m && m[3] !== undefined && (!cur || m[1].length < cur.contentIndent);
      if (isItem) {
        if (/\d/.test(m[2]) !== ordered) break; // a different kind of list starts
        const contentIndent = m[0].length - m[3].length;
        cur = { lines: [m[3]], contentIndent };
        items.push(cur);
        i += 1;
        continue;
      }
      if (isBlank(line)) {
        let j = i + 1;
        while (j < lines.length && isBlank(lines[j])) j += 1;
        if (j >= lines.length) break;
        const next = LIST_RE.exec(lines[j]);
        const sibling = next && next[3] !== undefined && next[1].length < cur.contentIndent && /\d/.test(next[2]) === ordered;
        if (indentOf(lines[j]) >= cur.contentIndent || sibling) {
          loose = loose || sibling || indentOf(lines[j]) >= cur.contentIndent;
          for (let k = i; k < j; k += 1) cur.lines.push('');
          i = j;
          continue;
        }
        break;
      }
      if (indentOf(line) >= cur.contentIndent || indentOf(line) > first[1].length) {
        cur.lines.push(line.slice(Math.min(indentOf(line), cur.contentIndent)));
        i += 1;
        continue;
      }
      if (!startsBlock(line)) {
        cur.lines.push(line.trim()); // lazy continuation of the item's paragraph
        i += 1;
        continue;
      }
      break;
    }

    const lis = items.map((item) => {
      const task = /^\[([ xX])\][ \t]+/.exec(item.lines[0]);
      let box = '';
      if (task) {
        item.lines[0] = item.lines[0].slice(task[0].length);
        box = task[1] === ' ' ? '<span class="sr-md-task">☐</span> ' : '<span class="sr-md-task">☑</span> ';
      }
      return `<li>${box}${this.blocks(item.lines, !loose)}</li>`;
    });
    const n = ordered ? parseInt(first[2], 10) : 1;
    const tag = ordered ? 'ol' : 'ul';
    const startAttr = ordered && n !== 1 ? ` start="${n}"` : '';
    out.push(`<${tag}${startAttr}>${lis.join('')}</${tag}>`);
    return i;
  }
}

/** Markdown → HTML (unsanitized: always pass the result through sanitizeRichHtml). */
export const renderMarkdown = (markdown) => {
  const lines = String(markdown || '')
    .replace(/\r\n?/g, '\n')
    .split('\n');
  return new BlockParser().blocks(lines);
};

export default renderMarkdown;
