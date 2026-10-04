import { render } from '@testing-library/react';
import Markdown, { parseBlocks, safeHref } from '../markdown';

const html = (text) => render(<Markdown text={text} />).container;

test('renders bold, italic, strike, inline code and keeps line breaks', () => {
  const c = html('**bold** and *it* and _also_ ~~gone~~ `x < y`\nnext line');
  expect(c.querySelector('strong').textContent).toBe('bold');
  expect([...c.querySelectorAll('em')].map((e) => e.textContent)).toEqual(['it', 'also']);
  expect(c.querySelector('del').textContent).toBe('gone');
  expect(c.querySelector('code').textContent).toBe('x < y');
  expect(c.querySelector('br')).not.toBeNull();
});

test('raw HTML is shown as text, never parsed', () => {
  const c = html('<img src=x onerror="alert(1)"><script>alert(2)</script><b>no</b>');
  expect(c.querySelector('img')).toBeNull();
  expect(c.querySelector('script')).toBeNull();
  expect(c.querySelector('b')).toBeNull();
  expect(c.textContent).toContain('<script>alert(2)</script>');
});

test('javascript:, data: and other unsafe links stay plain text', () => {
  for (const evil of ['javascript:alert(1)', 'JaVaScRiPt:alert(1)', 'data:text/html,<b>x</b>', 'vbscript:x', 'java\tscript:alert(1)']) {
    const c = html(`[click](${evil})`);
    expect(c.querySelector('a')).toBeNull();
  }
  expect(safeHref('javascript:alert(1)')).toBeNull();
  expect(safeHref('/relative')).toBeNull();
});

test('http(s) links are clickable, open safely, and attributes cannot be injected', () => {
  const c = html('see [docs](https://example.com/a?b=1) or https://example.org/x. "onmouseover=alert(1)');
  const links = c.querySelectorAll('a');
  expect(links).toHaveLength(2);
  expect(links[0].getAttribute('href')).toBe('https://example.com/a?b=1');
  expect(links[0].getAttribute('rel')).toContain('noopener');
  expect(links[0].getAttribute('target')).toBe('_blank');
  expect(links[1].getAttribute('href')).toBe('https://example.org/x');
  expect(links[1].getAttribute('onmouseover')).toBeNull();
});

test('fenced code, quotes and lists become blocks; markdown inside code is literal', () => {
  const blocks = parseBlocks('intro\n```\n**not bold** <b>\n```\n> quoted\n- one\n- two');
  expect(blocks.map((b) => b.type)).toEqual(['para', 'code', 'quote', 'list']);
  const c = html('```\n**not bold**\n```');
  expect(c.querySelector('pre code').textContent).toBe('**not bold**');
  expect(c.querySelector('strong')).toBeNull();
});

test('dice lines with brackets are not mistaken for links', () => {
  const c = html('Dice: [5] [4] [✓7] | Hunger: [8]');
  expect(c.querySelector('a')).toBeNull();
  expect(c.textContent).toBe('Dice: [5] [4] [✓7] | Hunger: [8]');
});
