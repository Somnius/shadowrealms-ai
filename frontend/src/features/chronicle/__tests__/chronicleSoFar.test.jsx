/**
 * "The chronicle so far" panel: the estimate before starting, the live progress card (night x of y,
 * tokens from the stream, waiting for a quiet moment), polling, Cancel, partial runs, exports and the
 * Storyteller part behind a toggle. Plus the design-system ProgressBar.
 */
import { act, render, screen, waitFor } from '@testing-library/react';
import setupUser from '../../../design/testing/setupUser';
import { DesignProvider, ProgressBar } from '../../../design';
import ChronicleSoFarPanel, { ProgressCard } from '../ChronicleSoFarPanel';
import { clock, mdFileName, pollDelay } from '../soFar';

const toast = jest.fn();
const campaign = { id: 10, name: 'Athens: Blood / Concrete' };

const written = {
  lang: 'el', view: 'st', access: 'st', can_update: true, quiet_minutes: 15, nights_written: 2, nights_total: 2, new_since: false,
  written_at: '2026-10-16T22:00:00', job: null,
  digest: { tldr: 'In short.', so_far: ['The story.'], threads_open: [{ text: 'Who watches?', nights: [1] }], st_so_far: ['Secret part.'] },
  chapters: [
    { key: '101:1', night: 1, room: 'Basement', visibility: 'all', started_at: '2026-10-05T21:00:00', chapter: { title: 'The note', summary: ['P1'], st_notes: [{ text: 'Hidden roll failed.' }] } },
    { key: '103:9', night: null, room: 'Crypt', visibility: 'st', started_at: '2026-10-06T21:00:00', chapter: { title: 'Sealed', summary: ['P2'] } },
    { key: '101:20', night: 2, room: 'Basement', visibility: 'all', started_at: '2026-10-07T21:00:00', chapter: { title: 'Kept', summary: ['P3'], check: ['language'] } },
  ],
};

const job = (over) => ({
  id: 7, status: 'running', phase: 'writing', night: 3, nights: 12, nights_done: 2, tokens_night: 1240,
  tok_per_s: 104.2, elapsed_s: 42, eta_s: 70, ...over,
});

const renderPanel = (api) =>
  render(
    <DesignProvider>
      <ChronicleSoFarPanel api={api} campaign={campaign} toast={toast} />
    </DesignProvider>
  );

afterEach(() => {
  jest.useRealTimers();
  toast.mockReset();
});

test('ProgressBar is a labelled progressbar', () => {
  render(<ProgressBar value={3} max={12} label="Writing" valueText="Night 3 of 12" />);
  const bar = screen.getByRole('progressbar', { name: 'Writing' });
  expect(bar).toHaveAttribute('aria-valuenow', '3');
  expect(bar).toHaveAttribute('aria-valuemax', '12');
  expect(bar).toHaveAttribute('aria-valuetext', 'Night 3 of 12');
  render(<ProgressBar label="Busy" />);
  expect(screen.getByRole('progressbar', { name: 'Busy' })).not.toHaveAttribute('aria-valuenow');
});

test('the progress card shows the night, tokens, time and the waiting state', () => {
  const { rerender } = render(<DesignProvider><ProgressCard job={job()} onCancel={() => {}} /></DesignProvider>);
  expect(screen.getByText('Night 3 of 12')).toBeInTheDocument();
  expect(screen.getByText(/1,240 tokens · 104 tok\/s/)).toBeInTheDocument();
  expect(screen.getByText('Elapsed 0:42 · about 1:10 left')).toBeInTheDocument();
  expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '2');
  rerender(<DesignProvider><ProgressCard job={job({ tokens_night: 0, tok_per_s: null })} onCancel={() => {}} /></DesignProvider>);
  expect(screen.getByText('Reading the night…')).toBeInTheDocument();
  rerender(<DesignProvider><ProgressCard job={job({ status: 'waiting', phase: 'waiting' })} onCancel={() => {}} quietMinutes={15} /></DesignProvider>);
  expect(screen.getAllByText('Waiting for a quiet moment').length).toBeGreaterThan(0);
  expect(screen.getByText(/after 15 minutes with no new message/)).toBeInTheDocument();
  expect(screen.getByRole('status')).toBeInTheDocument(); // the spinner
  expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
});

test('helpers: polling delay, clock, file names', () => {
  expect(pollDelay({ status: 'running' })).toBe(1500);
  expect(pollDelay({ status: 'queued' })).toBe(1500);
  expect(pollDelay({ status: 'waiting' })).toBe(5000);
  expect(clock(75)).toBe('1:15');
  expect(clock(3725)).toBe('1:02:05');
  expect(mdFileName('Athens: Blood / Concrete', 'so far')).toBe('Athens Blood Concrete — so far.md');
});

test('Update shows the estimate first; Start creates the job and the card polls it to the end', async () => {
  jest.useFakeTimers();
  const user = setupUser({ advanceTimers: jest.advanceTimersByTime });
  let polls = 0;
  const api = jest.fn(async (path, opts) => {
    if (path.endsWith('/estimate')) {
      return { ok: true, data: { enough: true, nights_to_write: 12, nights_stale: 50, seconds: 150, capped: true, max_nights: 40 } };
    }
    if (path.endsWith('/jobs') && opts && opts.method === 'POST') return { ok: true, status: 202, data: { job: job({ status: 'queued', night: 0, nights: 0 }) } };
    if (path.includes('/jobs/7')) {
      polls += 1;
      return { ok: true, data: { job: polls < 2 ? job() : job({ status: 'done', phase: null }) } };
    }
    return { ok: true, data: { ...written, nights_written: 0, chapters: [], digest: null } };
  });
  renderPanel(api);
  await user.click(await screen.findByRole('button', { name: 'Update' }));
  expect(await screen.findByText('This will take about 3 min: 12 nights to write, then the summary.')).toBeInTheDocument();
  expect(screen.getByText(/It stops after 40 nights \(50 are waiting\)/)).toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Start' }));
  expect(api).toHaveBeenCalledWith('/campaigns/10/chronicle/jobs', { method: 'POST', body: { scope: 'update' } });
  expect(await screen.findByText('Queued…')).toBeInTheDocument();
  await act(async () => {
    jest.advanceTimersByTime(1500);
  });
  expect(await screen.findByText('Night 3 of 12')).toBeInTheDocument();
  await act(async () => {
    jest.advanceTimersByTime(1500);
  });
  await waitFor(() => expect(screen.queryByTestId('sofar-progress')).not.toBeInTheDocument());
  expect(polls).toBe(2);
});

test('Cancel stops a running job', async () => {
  let cancelled = false;
  const api = jest.fn(async (path, opts) => {
    if (opts && opts.method === 'DELETE') {
      cancelled = true;
      return { ok: true, data: { job: job({ status: 'cancelled' }) } };
    }
    const current = cancelled ? job({ status: 'cancelled' }) : job();
    if (path.includes('/jobs/7')) return { ok: true, data: { job: current } };
    return { ok: true, data: { ...written, job: current } };
  });
  const user = setupUser();
  renderPanel(api);
  await user.click(await screen.findByRole('button', { name: 'Cancel' }));
  expect(api).toHaveBeenCalledWith('/campaigns/10/chronicle/jobs/7', { method: 'DELETE' });
  await waitFor(() => expect(screen.queryByTestId('sofar-progress')).not.toBeInTheDocument());
});

test('too little to tell: the notice says so and offers no Start', async () => {
  const api = jest.fn(async (path) =>
    path.endsWith('/estimate')
      ? { ok: true, data: { enough: false, nights_to_write: 0, seconds: 0 } }
      : { ok: true, data: { ...written, nights_written: 0, chapters: [], digest: null } });
  const user = setupUser();
  renderPanel(api);
  await user.click(await screen.findByRole('button', { name: 'Update' }));
  expect(await screen.findByText('Nothing to tell yet: write a few scenes first.')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Start' })).not.toBeInTheDocument();
});

test('partial runs say so; the Storyteller part is behind a toggle; exports', async () => {
  const api = jest.fn(async () => ({ ok: true, data: { ...written, nights_total: 63, new_since: true } }));
  const user = setupUser();
  global.fetch = jest.fn(async () => ({ ok: true, status: 200, blob: async () => new Blob(['# x']) }));
  URL.createObjectURL = jest.fn(() => 'blob:x');
  URL.revokeObjectURL = jest.fn();
  renderPanel(api);
  expect(await screen.findByText(/2 of 63 nights; Update continues\. New messages since the last update\./)).toBeInTheDocument();
  expect(screen.getByText('The story.')).toBeInTheDocument();
  expect(screen.queryByText('Secret part.')).not.toBeInTheDocument();
  expect(screen.queryByText(/Crypt/)).not.toBeInTheDocument();
  await user.click(screen.getByRole('switch', { name: 'Show the Storyteller part' }));
  expect(screen.getByText('Secret part.')).toBeInTheDocument();
  expect(screen.getByText(/Crypt/)).toBeInTheDocument();
  expect(screen.getByText('not fully in Greek')).toBeInTheDocument();
  await user.type(screen.getByRole('spinbutton', { name: 'Number of nights' }), '3');
  await user.click(screen.getByRole('button', { name: /Export minutes · the last 3 nights/ }));
  await waitFor(() => expect(global.fetch).toHaveBeenCalled());
  expect(global.fetch.mock.calls[0][0]).toBe('/api/campaigns/10/chronicle/minutes.md?last=3');
  await user.click(screen.getByRole('button', { name: 'Export story' }));
  await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(2));
  expect(global.fetch.mock.calls[1][0]).toBe('/api/campaigns/10/chronicle.md');
});

test('helpers read and export but get no Update or Rewrite everything', async () => {
  const api = jest.fn(async () => ({ ok: true, data: { ...written, access: 'helper', can_update: false } }));
  renderPanel(api);
  expect(await screen.findByRole('button', { name: 'Export story' })).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Update' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Rewrite everything' })).not.toBeInTheDocument();
});

test('Rewrite everything asks the estimate at scope=all and starts a scope all job; 429 is explained', async () => {
  const api = jest.fn(async (path, opts) => {
    if (path.endsWith('/estimate?scope=all')) return { ok: true, data: { enough: true, nights_to_write: 2, nights_stale: 2, seconds: 30 } };
    if (opts && opts.method === 'POST') return { ok: false, status: 429, data: { error: 'too_soon', retry_after: 1200 } };
    return { ok: true, data: written };
  });
  const user = setupUser();
  renderPanel(api);
  await user.click(await screen.findByRole('button', { name: 'Rewrite everything' }));
  expect(await screen.findByText('Every night is written again, the oldest first.')).toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Start' }));
  expect(api).toHaveBeenCalledWith('/campaigns/10/chronicle/jobs', { method: 'POST', body: { scope: 'all' } });
  await waitFor(() => expect(toast).toHaveBeenCalledWith({ tone: 'danger', title: 'Update was pressed a moment ago; try again in 1200 s.' }));
});

test('a failed job shows a short reason, never the provider text', async () => {
  const api = jest.fn(async () => ({ ok: true, data: { ...written, job: { id: 3, status: 'failed', error: 'model_failed' } } }));
  renderPanel(api);
  expect(await screen.findByText(/The last update failed: the model did not answer/)).toBeInTheDocument();
});
