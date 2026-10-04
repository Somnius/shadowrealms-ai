import { render, screen, waitFor } from '@testing-library/react';
import ReadmeModal from '../ReadmeModal';

function mockReadme(text) {
  global.fetch = jest.fn(() =>
    Promise.resolve({ ok: true, status: 200, text: () => Promise.resolve(text) })
  );
}

describe('ReadmeModal', () => {
  const realFetch = global.fetch;
  afterEach(() => {
    global.fetch = realFetch;
  });

  test('renders the README markdown and strips unsafe HTML from it', async () => {
    mockReadme(
      [
        '# ShadowRealms',
        '',
        'See [the docs](docs/README.md) and **bold** text.',
        '',
        '<!-- hidden note -->',
        '<img src=x onerror="window.__readmeXss=true">',
        '<script>window.__readmeXss=true</script>',
        '',
      ].join('\n')
    );
    window.__readmeXss = false;
    render(<ReadmeModal isOpen onClose={() => {}} />);

    const heading = await screen.findByRole('heading', { name: 'ShadowRealms' });
    const content = heading.closest('.sr-readme__content');
    await waitFor(() => expect(content).toBeTruthy());

    const link = screen.getByRole('link', { name: 'the docs' });
    expect(link).toHaveAttribute(
      'href',
      'https://github.com/Somnius/shadowrealms-ai/blob/main/docs/README.md'
    );
    expect(link).toHaveAttribute('target', '_blank');

    const html = content.innerHTML;
    expect(html).not.toMatch(/onerror|<script|javascript:|hidden note/i);
    expect(window.__readmeXss).toBe(false);
    delete window.__readmeXss;
  });

  test('keeps the line breaks of fenced code blocks', async () => {
    mockReadme(
      [
        '# Setup',
        '',
        '```bash',
        'lms server start',
        'lms load llama-krikri-8b-instruct -y    # Storyteller',
        'ollama pull llama3.2:3b                 # utility model',
        '```',
        '',
      ].join('\n')
    );
    render(<ReadmeModal isOpen onClose={() => {}} />);
    const heading = await screen.findByRole('heading', { name: 'Setup' });
    const code = heading.closest('.sr-readme__content').querySelector('pre > code');
    expect(code.textContent).toBe(
      [
        'lms server start',
        'lms load llama-krikri-8b-instruct -y    # Storyteller',
        'ollama pull llama3.2:3b                 # utility model',
      ].join('\n')
    );
  });
});
