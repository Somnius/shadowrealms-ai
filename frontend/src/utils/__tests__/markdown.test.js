import { renderMarkdown, renderInline, resolveLink, resolveImage } from '../markdown';
import { sanitizeRichHtml } from '../security';

// An excerpt of the real README.md (top block, screenshot table, a list with code blocks
// between its items, a models table, links). Keep it in sync loosely; the point is the shapes.
const README_EXCERPT = [
  '<div align="center">',
  '',
  '# ShadowRealms AI',
  '',
  '![ShadowRealms AI](assets/logos/shadowrealms-banner.png)',
  '',
  '### Self-hosted AI Storyteller for World of Darkness chronicles',
  '',
  '[![Version](https://img.shields.io/badge/version-0.9.1-blue.svg)](docs/CHANGELOG.md)',
  '[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)',
  '',
  '</div>',
  '',
  '| Sign-in | Chronicle hall | Bestial failure |',
  '|---|---|---|',
  '| ![Sign-in page with the animated sigil](assets/screenshots/v0.9/login-desktop.webp) | ![Chronicle hall](assets/screenshots/v0.9/hall.webp) | ![A V5 bestial failure](assets/screenshots/v0.9/dice-bestial-failure.webp) |',
  '',
  '---',
  '',
  '## Quick start',
  '',
  '1. Clone the repository and create your config:',
  '',
  '```bash',
  'git clone https://github.com/Somnius/shadowrealms-ai.git',
  'cd shadowrealms-ai',
  'cp env.template .env',
  'cp backend/invites.template.json backend/invites.json',
  'python3 scripts/generate_secret_key.py',
  '```',
  '',
  '2. Edit `.env`: put your own keys in `FLASK_SECRET_KEY` and `JWT_SECRET_KEY` ([how](docs/POSTGRESQL_ENV_SETUP.md)).',
  '3. Edit `backend/invites.json`: replace the example codes.',
  '',
  '```bash',
  'lms server start',
  'lms load llama-krikri-8b-instruct -y    # Storyteller, English and Greek',
  'ollama pull llama3.2:3b                 # utility model',
  '```',
  '',
  '## Models and hardware',
  '',
  '| Role | Default | Where to change it |',
  '|---|---|---|',
  '| Utility | `llama3.2:3b` (Ollama) | Admin, AI system, or `UTILITY_PROVIDER` and `UTILITY_MODEL` |',
  '| Classifier | Laya if its model is in `data/laya/model` | Admin, AI system |',
  '',
  '- It\'s developed on Linux with a 16 GB NVIDIA GPU. Krikri needs about 5 GB of VRAM.',
  '- More in the wiki\'s [AI Models](https://github.com/Somnius/shadowrealms-ai/wiki/AI-Models) page.',
  '',
  '> **Version 0.7.0 Preview:** This demo showcases the frontend interface.',
  '',
].join('\n');

const render = (md) => {
  const div = document.createElement('div');
  div.innerHTML = sanitizeRichHtml(renderMarkdown(md));
  return div;
};

describe('renderMarkdown with the README', () => {
  const root = render(README_EXCERPT);

  test('fenced code blocks keep every line and their spacing', () => {
    const blocks = root.querySelectorAll('pre > code');
    expect(blocks).toHaveLength(2);
    expect(blocks[0].className).toBe('language-bash');
    expect(blocks[0].textContent).toBe(
      [
        'git clone https://github.com/Somnius/shadowrealms-ai.git',
        'cd shadowrealms-ai',
        'cp env.template .env',
        'cp backend/invites.template.json backend/invites.json',
        'python3 scripts/generate_secret_key.py',
      ].join('\n')
    );
    expect(blocks[1].textContent.split('\n')).toEqual([
      'lms server start',
      'lms load llama-krikri-8b-instruct -y    # Storyteller, English and Greek',
      'ollama pull llama3.2:3b                 # utility model',
    ]);
    // Nothing inside a code block is treated as markdown.
    expect(blocks[1].innerHTML).not.toMatch(/<(h1|em|strong|a)\b/);
  });

  test('headings, centered block and badges', () => {
    const h1 = root.querySelector('h1');
    expect(h1.textContent).toBe('ShadowRealms AI');
    expect(h1.id).toBe('readme-shadowrealms-ai');
    expect(h1.closest('div[align="center"]')).not.toBeNull();
    expect([...root.querySelectorAll('h2')].map((h) => h.textContent)).toEqual([
      'Quick start',
      'Models and hardware',
    ]);
    const badge = root.querySelector('a[href="https://github.com/Somnius/shadowrealms-ai/blob/main/docs/CHANGELOG.md"] > img');
    expect(badge.getAttribute('src')).toBe('https://img.shields.io/badge/version-0.9.1-blue.svg');
  });

  test('relative images load from raw.githubusercontent.com', () => {
    const banner = root.querySelector('img[alt="ShadowRealms AI"]');
    expect(banner.getAttribute('src')).toBe(
      'https://raw.githubusercontent.com/Somnius/shadowrealms-ai/main/assets/logos/shadowrealms-banner.png'
    );
    const shots = root.querySelectorAll('table img');
    expect(shots).toHaveLength(3);
    shots.forEach((img) => expect(img.getAttribute('src')).toMatch(/^https:\/\/raw\.githubusercontent\.com\/Somnius\/shadowrealms-ai\/main\/assets\/screenshots\/v0\.9\//));
  });

  test('tables keep every cell, including inline code', () => {
    const tables = root.querySelectorAll('table');
    expect(tables).toHaveLength(2);
    const models = tables[1];
    expect([...models.querySelectorAll('th')].map((c) => c.textContent)).toEqual(['Role', 'Default', 'Where to change it']);
    const rows = models.querySelectorAll('tbody tr');
    expect(rows).toHaveLength(2);
    expect(rows[0].querySelectorAll('td')[1].innerHTML).toBe('<code>llama3.2:3b</code> (Ollama)');
  });

  test('ordered list numbering continues after a code block, inline code and links render', () => {
    const lists = root.querySelectorAll('ol');
    expect(lists).toHaveLength(2);
    expect(lists[0].getAttribute('start')).toBeNull();
    expect(lists[1].getAttribute('start')).toBe('2');
    expect(lists[1].querySelectorAll('li')).toHaveLength(2);
    expect(lists[1].querySelector('li code').textContent).toBe('.env');
    const how = lists[1].querySelector('a');
    expect(how.getAttribute('href')).toBe('https://github.com/Somnius/shadowrealms-ai/blob/main/docs/POSTGRESQL_ENV_SETUP.md');
    expect(how.getAttribute('target')).toBe('_blank');
  });

  test('bullets, hr, blockquote', () => {
    const ul = root.querySelector('ul');
    expect(ul.querySelectorAll('li')).toHaveLength(2);
    expect(ul.querySelector('a').getAttribute('href')).toBe('https://github.com/Somnius/shadowrealms-ai/wiki/AI-Models');
    expect(root.querySelectorAll('hr')).toHaveLength(1);
    expect(root.querySelector('blockquote strong').textContent).toBe('Version 0.7.0 Preview:');
  });
});

describe('renderMarkdown details', () => {
  test('code blocks escape HTML, keep blank lines and support ~~~ and no language', () => {
    const md = ['~~~', '<script>alert(1)</script>', '', 'a && b', '~~~'].join('\n');
    const html = renderMarkdown(md);
    expect(html).toBe('<pre class="sr-md-code"><code>&lt;script&gt;alert(1)&lt;/script&gt;\n\na &amp;&amp; b</code></pre>');
    const root = render(md);
    expect(root.querySelector('code').textContent).toBe('<script>alert(1)</script>\n\na && b');
  });

  test('fence inside a list item stays inside it', () => {
    const root = render(['- step one:', '', '  ```sh', '  echo one', '  echo two', '  ```', '- step two'].join('\n'));
    const items = root.querySelectorAll('ul > li');
    expect(items).toHaveLength(2);
    expect(items[0].querySelector('pre code').textContent).toBe('echo one\necho two');
  });

  test('nested lists', () => {
    const root = render(['- a', '  - a1', '  - a2', '    1. deep', '- b'].join('\n'));
    expect(root.querySelectorAll(':scope > ul > li')).toHaveLength(2);
    expect(root.querySelectorAll('ul ul > li')).toHaveLength(2);
    expect(root.querySelector('ul ul ol li').textContent).toBe('deep');
  });

  test('table alignment, escaped pipes and empty cells', () => {
    const root = render(['| L | C | R |', '|:--|:-:|--:|', '| a \\| b | | `x|y` |'].join('\n'));
    const cells = root.querySelectorAll('td');
    expect(cells).toHaveLength(3);
    expect(cells[0].textContent).toBe('a | b');
    expect(cells[1].textContent).toBe('');
    expect(cells[2].textContent).toBe('x|y');
    expect(root.querySelectorAll('th')[1].style.textAlign).toBe('center');
    expect(root.querySelectorAll('th')[2].style.textAlign).toBe('right');
  });

  test('a line with a pipe followed by a rule is not a table', () => {
    const root = render(['a | b', '---'].join('\n'));
    expect(root.querySelector('table')).toBeNull();
  });

  test('emphasis does not touch snake_case or code', () => {
    expect(renderInline('set UTILITY_MODEL and `a*b*c`, *it* and **bold** and ~~gone~~')).toBe(
      'set UTILITY_MODEL and <code>a*b*c</code>, <em>it</em> and <strong>bold</strong> and <del>gone</del>'
    );
  });

  test('anchor links point at the prefixed heading ids', () => {
    const root = render(['## Quick start', '', 'See [below](#quick-start).'].join('\n'));
    expect(root.querySelector('h2').id).toBe('readme-quick-start');
    const a = root.querySelector('p a');
    expect(a.getAttribute('href')).toBe('#readme-quick-start');
    expect(a.hasAttribute('target')).toBe(false);
  });

  test('unsafe URLs are not links or images', () => {
    expect(resolveLink('javascript:alert(1)')).toBeNull();
    expect(resolveLink('JaVaScRiPt:alert(1)')).toBeNull();
    expect(resolveLink('data:text/html,x')).toBeNull();
    expect(resolveImage('data:image/png;base64,AAAA')).toBeNull();
    expect(resolveImage('http://example.com/a.png')).toBeNull();
    expect(resolveImage('./assets/a.png')).toBe('https://raw.githubusercontent.com/Somnius/shadowrealms-ai/main/assets/a.png');
    const root = render('[click](javascript:alert(1)) ![x](javascript:alert(1)) ![plain](http://example.com/a.png)');
    expect(root.querySelector('a')).toBeNull();
    expect(root.querySelector('img')).toBeNull();
    expect(root.textContent).toContain('plain');
  });

  test('no script or event handler survives rendering + sanitizing', () => {
    window.__mdXss = false;
    const md = [
      '<img src=x onerror="window.__mdXss=true">',
      '',
      '<script>window.__mdXss=true</script>',
      '',
      '<!-- secret',
      'comment -->',
      '',
      'Inline <img src=x onerror="window.__mdXss=true"> and <b onclick="x()">b</b>',
      '',
      '[x](https://example.com/" onmouseover="window.__mdXss=true)',
      '',
      '![a" onerror="window.__mdXss=true](https://example.com/a.png)',
      '',
      '<a href="javascript:window.__mdXss=true">raw</a>',
      '',
      '| <script>alert(1)</script> |',
      '|---|',
      '| <img src=x onerror=alert(1)> |',
    ].join('\n');
    const root = render(md);
    // Inline HTML is shown as text, so only elements and attributes are checked, not the text.
    expect(root.querySelector('script')).toBeNull();
    expect(root.textContent).not.toMatch(/secret/);
    root.querySelectorAll('*').forEach((el) => {
      [...el.attributes].forEach((attr) => {
        expect(attr.name.startsWith('on')).toBe(false);
        expect(attr.value).not.toMatch(/javascript:/i);
      });
    });
    expect(window.__mdXss).toBe(false);
    delete window.__mdXss;
  });
});

describe('renderMarkdown on hostile input', () => {
  test('long backtick runs and unclosed links render quickly', () => {
    const started = Date.now();
    renderMarkdown(`a ${'`'.repeat(6000)}`);
    renderMarkdown('![a]('.repeat(12500));
    renderMarkdown('[a]('.repeat(16000));
    expect(Date.now() - started).toBeLessThan(2000);
  });

  test('code spans still pair runs of the same length', () => {
    expect(renderInline('a ``x ` y`` b `z`')).toBe('a <code>x ` y</code> b <code>z</code>');
    expect(renderInline('only ` one')).toBe('only ` one');
  });

  test('deep nesting stops instead of overflowing the stack', () => {
    expect(() => renderMarkdown('- '.repeat(1250))).not.toThrow();
    expect(() => renderMarkdown('> '.repeat(5000))).not.toThrow();
  });

  test('nested markup never ends up inside an attribute', () => {
    const html = renderInline('[x](https://e.com/a![i](https://e.com/i.png)b) ![`alt`](https://e.com/p.png)');
    expect(html).not.toMatch(/href="[^"]*</);
    expect(html).not.toMatch(/alt="[^"]*</);
  });
});
