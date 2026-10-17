/**
 * "The chronicle so far", 0.25: PDF exports (paper, language), the Storyteller's edit copy with the
 * "newer digest" choice, and the language switch with Translate
 * (the chronicle language at creation is in integration/userFlow.test.js).
 */
import { render, screen, waitFor } from '@testing-library/react';
import setupUser from '../../../design/testing/setupUser';
import { DesignProvider } from '../../../design';
import ChronicleSoFarPanel from '../ChronicleSoFarPanel';
import { mdFileName, query } from '../soFar';

const toast = jest.fn();
const campaign = { id: 10, name: 'Athens' };

const written = {
  lang: 'el', own_lang: 'el', view: 'st', access: 'st', can_update: true, can_edit: true, quiet_minutes: 10,
  nights_written: 1, nights_total: 1, new_since: false, written_at: '2026-10-16T22:00:00', job: null, translation: null,
  edit: { edited: false, newer: false, edited_at: null },
  digest: { tldr: 'Με λίγα λόγια.', so_far: ['Η ιστορία.'], threads_open: [] },
  chapters: [{ key: '101:1', night: 1, room: 'Υπόγειο', visibility: 'all', started_at: '2026-10-05T21:00:00', chapter: { title: 'Τ', summary: ['Π'] } }],
};

const renderPanel = (api) =>
  render(
    <DesignProvider>
      <ChronicleSoFarPanel api={api} campaign={campaign} toast={toast} />
    </DesignProvider>
  );

beforeEach(() => {
  global.fetch = jest.fn(async () => ({ ok: true, status: 200, blob: async () => new Blob(['%PDF']) }));
  URL.createObjectURL = jest.fn(() => 'blob:x');
  URL.revokeObjectURL = jest.fn();
});

afterEach(() => toast.mockReset());

test('query and file names', () => {
  expect(query({ last: 3, lang: '', with_table_talk: false, paper: 'letter' })).toBe('?last=3&paper=letter');
  expect(query({ with_table_talk: true })).toBe('?with_table_talk=1');
  expect(query({})).toBe('');
  expect(mdFileName('Athens', 'so far', 'pdf')).toBe('Athens — so far.pdf');
});

test('PDF exports of the story and the minutes, on the chosen paper', async () => {
  const api = jest.fn(async () => ({ ok: true, data: written }));
  const user = setupUser();
  renderPanel(api);
  await user.click(await screen.findByRole('button', { name: 'Export story PDF' }));
  await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
  expect(global.fetch.mock.calls[0][0]).toBe('/api/campaigns/10/chronicle.pdf?paper=a4');
  await user.selectOptions(screen.getByRole('combobox', { name: 'Paper' }), 'letter');
  await user.type(screen.getByRole('spinbutton', { name: 'Number of nights' }), '2');
  await user.click(screen.getByRole('button', { name: 'Minutes PDF' }));
  await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(2));
  expect(global.fetch.mock.calls[1][0]).toBe('/api/campaigns/10/chronicle/minutes.pdf?last=2&paper=letter');
});

test('the Storyteller edits one Markdown box and saves it with PUT', async () => {
  let saved = null;
  const api = jest.fn(async (path, opts) => {
    if (path.endsWith('/chronicle/edit')) {
      if (opts && opts.method === 'PUT') {
        saved = opts.body;
        return { ok: true, data: { markdown: opts.body.markdown, edited: true, newer: false } };
      }
      return { ok: true, data: { markdown: '# Athens\n\nΗ ιστορία.', edited: false, newer: false } };
    }
    return { ok: true, data: saved ? { ...written, edit: { edited: true, newer: false } } : written };
  });
  const user = setupUser();
  renderPanel(api);
  await user.click(await screen.findByRole('button', { name: 'Edit the story' }));
  const box = await screen.findByRole('textbox', { name: 'The story so far (Markdown)' });
  expect(box).toHaveValue('# Athens\n\nΗ ιστορία.');
  await user.type(box, ' Και κάτι δικό μου.');
  await user.click(screen.getByRole('button', { name: 'Save my edit' }));
  await waitFor(() => expect(saved).toEqual({ markdown: '# Athens\n\nΗ ιστορία. Και κάτι δικό μου.' }));
  expect(await screen.findByText(/Exports of the story use your edited copy/)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Edit my copy' })).toBeInTheDocument();
});

test('a newer digest offers "keep my edit" or "start from the new one"', async () => {
  const api = jest.fn(async (path) => {
    if (path.endsWith('/chronicle/edit')) return { ok: true, data: { markdown: 'x', edited: false, newer: false } };
    return { ok: true, data: { ...written, edit: { edited: true, newer: true } } };
  });
  const user = setupUser();
  renderPanel(api);
  expect(await screen.findByTestId('sofar-newer')).toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Keep my edit' }));
  expect(api).toHaveBeenCalledWith('/campaigns/10/chronicle/edit', { method: 'PUT', body: { keep: true } });
  await user.click(screen.getByRole('button', { name: 'Start from the new one' }));
  expect(api).toHaveBeenCalledWith('/campaigns/10/chronicle/edit', { method: 'DELETE', body: undefined });
});

test('helpers get no edit box', async () => {
  const api = jest.fn(async () => ({ ok: true, data: { ...written, access: 'helper', can_update: false, can_edit: false } }));
  renderPanel(api);
  expect(await screen.findByRole('button', { name: 'Export story PDF' })).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Edit the story' })).not.toBeInTheDocument();
});

test('the language switch reads the translation; Translate starts a translate job', async () => {
  const api = jest.fn(async (path, opts) => {
    if (path === '/campaigns/10/chronicle?lang=en') {
      return { ok: true, data: { ...written, lang: 'en', digest: null, chapters: [], nights_written: 0 } };
    }
    if (path.endsWith('/estimate?scope=translate')) return { ok: true, data: { texts: 12, seconds: 24, from: 'el' } };
    if (opts && opts.method === 'POST') return { ok: true, status: 202, data: { job: { id: 9, status: 'done', scope: 'translate' } } };
    return { ok: true, data: written };
  });
  const user = setupUser();
  renderPanel(api);
  await user.selectOptions(await screen.findByRole('combobox', { name: 'Language' }), 'en');
  expect(await screen.findByText('Not translated yet.')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Update' })).not.toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Translate' }));
  expect(await screen.findByText('Translating 12 texts takes less than a minute.')).toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Start' }));
  expect(api).toHaveBeenCalledWith('/campaigns/10/chronicle/jobs', { method: 'POST', body: { scope: 'translate', lang: 'en' } });
});

test('exports in the translated language pass lang=', async () => {
  const api = jest.fn(async (path) => (path.includes('lang=en')
    ? { ok: true, data: { ...written, lang: 'en', translation: { from: 'el', stale: false, written_at: '2026-10-17T10:00:00' } } }
    : { ok: true, data: written }));
  const user = setupUser();
  renderPanel(api);
  await user.selectOptions(await screen.findByRole('combobox', { name: 'Language' }), 'en');
  expect(await screen.findByText(/^Translated /)).toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Export story' }));
  await waitFor(() => expect(global.fetch).toHaveBeenCalled());
  expect(global.fetch.mock.calls[0][0]).toBe('/api/campaigns/10/chronicle.md?lang=en');
  expect(screen.queryByRole('button', { name: 'Edit the story' })).not.toBeInTheDocument();
});

test('a partial translation says how many texts are left and offers Translate again', async () => {
  const api = jest.fn(async (path) => (path.includes('lang=en')
    ? { ok: true, data: { ...written, lang: 'en', translation: { from: 'el', stale: false, untranslated: 3, written_at: '2026-10-17T10:00:00' } } }
    : { ok: true, data: written }));
  const user = setupUser();
  renderPanel(api);
  await user.selectOptions(await screen.findByRole('combobox', { name: 'Language' }), 'en');
  expect(await screen.findByText(/3 texts are still in Ελληνικά\./)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Translate' })).toBeInTheDocument();
});

test('an edit in the target language stops Translate with a sentence', async () => {
  const api = jest.fn(async (path, opts) => {
    if (path.includes('estimate')) return { ok: true, data: { texts: 4, seconds: 8 } };
    if (opts && opts.method === 'POST') return { ok: false, status: 409, data: { error: 'edited_in_target' } };
    if (path.includes('lang=en')) return { ok: true, data: { ...written, lang: 'en', digest: null, chapters: [], nights_written: 0 } };
    return { ok: true, data: written };
  });
  const user = setupUser();
  renderPanel(api);
  await user.selectOptions(await screen.findByRole('combobox', { name: 'Language' }), 'en');
  await user.click(await screen.findByRole('button', { name: 'Translate' }));
  await user.click(await screen.findByRole('button', { name: 'Start' }));
  await waitFor(() => expect(toast).toHaveBeenCalledWith({ tone: 'danger', title: expect.stringMatching(/never deleted without you/) }));
});

test('helpers see the live job but get no Cancel', async () => {
  const running = { id: 7, status: 'running', phase: 'writing', night: 1, nights: 2, nights_done: 0, tokens_night: 0, elapsed_s: 1 };
  const api = jest.fn(async (path) => (path.includes('/jobs/7')
    ? { ok: true, data: { job: running } }
    : { ok: true, data: { ...written, access: 'helper', can_update: false, can_edit: false, job: running } }));
  renderPanel(api);
  expect(await screen.findByTestId('sofar-progress')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Cancel' })).not.toBeInTheDocument();
});
