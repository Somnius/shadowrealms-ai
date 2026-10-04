/**
 * Safe chat markdown → React nodes. No HTML is ever parsed or injected (no dangerouslySetInnerHTML):
 * user text only becomes React text nodes and a fixed set of elements.
 *
 * Blocks: ``` fenced code ```, "> " quotes, "- " / "* " lists, paragraphs (newlines kept).
 * Inline: `code`, **bold**, *italic* / _italic_, ~~strike~~, [label](https://…), bare http(s) links.
 * Links: only http:, https: and mailto: are clickable; anything else (javascript:, data:, …) stays text.
 */

const SAFE_PROTOCOLS = new Set(['http:', 'https:', 'mailto:']);

export function safeHref(raw) {
  const s = String(raw || '').trim();
  if (!s) return null;
  // Reject control characters / whitespace tricks ("java\nscript:")
  // eslint-disable-next-line no-control-regex
  if (/[\u0000-\u001f\u007f\s]/.test(s)) return null;
  let url;
  try {
    url = new URL(s);
  } catch {
    return null;
  }
  return SAFE_PROTOCOLS.has(url.protocol) ? url.href : null;
}

const INLINE_RE = new RegExp(
  [
    '(`[^`\\n]+`)', // 1 code
    '(\\*\\*(?=\\S)([\\s\\S]+?)\\*\\*)', // 2,3 bold
    '(~~(?=\\S)([\\s\\S]+?)~~)', // 4,5 strike
    '(\\*(?=[^\\s*])([^*\\n]+?)\\*)', // 6,7 italic *
    '(?:(^|[\\s(])_(?=\\S)([^_\\n]+?)_(?=$|[\\s.,;:!?)]))', // 8 prefix, 9 italic _ (no lookbehind: old Safari)
    '(\\[([^\\]\\n]+)\\]\\(([^)\\s]+)\\))', // 10,11,12 link
    "(https?:\\/\\/[^\\s<>()]+[^\\s<>().,;:!?'\"])", // 13 bare url
  ].join('|'),
  'g'
);

function Link({ href, children }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer nofollow">
      {children}
    </a>
  );
}

export function renderInline(text, keyPrefix = 'i', depth = 0) {
  const out = [];
  const s = String(text == null ? '' : text);
  if (depth > 4) return [s];
  let last = 0;
  let n = 0;
  const re = new RegExp(INLINE_RE.source, 'g');
  let m;
  while ((m = re.exec(s)) !== null) {
    if (m.index > last) out.push(s.slice(last, m.index));
    const key = `${keyPrefix}-${n++}`;
    if (m[1]) {
      out.push(<code key={key} className="sr-md-code">{m[1].slice(1, -1)}</code>);
    } else if (m[2]) {
      out.push(<strong key={key}>{renderInline(m[3], key, depth + 1)}</strong>);
    } else if (m[4]) {
      out.push(<del key={key}>{renderInline(m[5], key, depth + 1)}</del>);
    } else if (m[6]) {
      out.push(<em key={key}>{renderInline(m[7], key, depth + 1)}</em>);
    } else if (m[9] !== undefined) {
      if (m[8]) out.push(m[8]);
      out.push(<em key={key}>{renderInline(m[9], key, depth + 1)}</em>);
    } else if (m[10]) {
      const href = safeHref(m[12]);
      if (href) out.push(<Link key={key} href={href}>{renderInline(m[11], key, depth + 1)}</Link>);
      else out.push(m[10]);
    } else if (m[13]) {
      const href = safeHref(m[13]);
      out.push(href ? <Link key={key} href={href}>{m[13]}</Link> : m[13]);
    }
    last = re.lastIndex;
    if (m[0].length === 0) re.lastIndex += 1;
  }
  if (last < s.length) out.push(s.slice(last));
  return out;
}

function withBreaks(lines, keyPrefix) {
  const out = [];
  lines.forEach((line, i) => {
    if (i > 0) out.push(<br key={`${keyPrefix}-br-${i}`} />);
    out.push(...renderInline(line, `${keyPrefix}-${i}`));
  });
  return out;
}

/** Split into blocks: { type: 'code'|'quote'|'list'|'para', lines|text } */
export function parseBlocks(text) {
  const src = String(text == null ? '' : text).replace(/\r\n?/g, '\n');
  const blocks = [];
  const fence = /```([^\n`]*)\n?([\s\S]*?)```/g;
  let last = 0;
  let m;
  const pushText = (chunk) => {
    const lines = chunk.split('\n');
    let cur = null;
    const flush = () => {
      if (cur && !(cur.type === 'para' && cur.lines.every((l) => l === ''))) blocks.push(cur);
      cur = null;
    };
    for (const line of lines) {
      const quote = /^>\s?(.*)$/.exec(line);
      const item = /^\s*[-*]\s+(.+)$/.exec(line);
      const type = quote ? 'quote' : item ? 'list' : 'para';
      const content = quote ? quote[1] : item ? item[1] : line;
      if (!cur || cur.type !== type) {
        flush();
        cur = { type, lines: [] };
      }
      cur.lines.push(content);
    }
    flush();
  };
  while ((m = fence.exec(src)) !== null) {
    if (m.index > last) pushText(src.slice(last, m.index).replace(/\n$/, ''));
    blocks.push({ type: 'code', lang: m[1].trim(), text: m[2].replace(/\n$/, '') });
    last = fence.lastIndex;
    if (src[last] === '\n') last += 1;
  }
  if (last < src.length) pushText(src.slice(last));
  // Trim leading/trailing empty lines of paragraphs
  return blocks
    .map((b) => {
      if (b.type !== 'para') return b;
      const lines = [...b.lines];
      while (lines.length && lines[0] === '') lines.shift();
      while (lines.length && lines[lines.length - 1] === '') lines.pop();
      return { ...b, lines };
    })
    .filter((b) => b.type !== 'para' || b.lines.length);
}

export function renderMarkdown(text) {
  return parseBlocks(text).map((b, i) => {
    const key = `b${i}`;
    if (b.type === 'code') {
      return (
        <pre key={key} className="sr-md-pre">
          <code>{b.text}</code>
        </pre>
      );
    }
    if (b.type === 'quote') {
      return (
        <blockquote key={key} className="sr-md-quote">
          {withBreaks(b.lines, key)}
        </blockquote>
      );
    }
    if (b.type === 'list') {
      return (
        <ul key={key} className="sr-md-list">
          {b.lines.map((l, j) => (
            <li key={`${key}-${j}`}>{renderInline(l, `${key}-${j}`)}</li>
          ))}
        </ul>
      );
    }
    return (
      <p key={key} className="sr-md-p">
        {withBreaks(b.lines, key)}
      </p>
    );
  });
}

export function Markdown({ text, className }) {
  return <div className={className ? `sr-md ${className}` : 'sr-md'}>{renderMarkdown(text)}</div>;
}

export default Markdown;
