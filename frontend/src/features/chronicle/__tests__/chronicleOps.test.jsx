/**
 * 0.28 "Ops": the chronicle's own settings (gap, table talk, nightly run, writer model), the writer
 * health panel in Admin → AI system and the archives of deleted chronicles.
 */
import { render, screen, waitFor, within } from '@testing-library/react';
import setupUser from '../../../design/testing/setupUser';
import { DesignProvider } from '../../../design';
import ChronicleSoFarPanel from '../ChronicleSoFarPanel';
import ChronicleSoFarSettings from '../ChronicleSoFarSettings';
import WriterHealthPanel from '../WriterHealthPanel';
import ChronicleArchivesPanel from '../ChronicleArchivesPanel';

const mockFetch = jest.fn();
const mockDownload = jest.fn();
jest.mock('../../../app/http', () => ({
  apiFetch: (...a) => mockFetch(...a),
  getCurrentToken: () => 'tok',
  errorText: (d, fallback) => (d && d.error) || fallback,
  API_URL: '/api',
  authFetch: jest.fn(),
}));
jest.mock('../soFar', () => ({
  ...jest.requireActual('../soFar'),
  downloadMarkdown: (...a) => mockDownload(...a),
}));

const toast = jest.fn();
const settingsBody = {
  settings: { v: 1, gap_hours: 6, table_talk: false, nightly: false, memory: true, model: null },
  models: [
    { provider: 'lm_studio', model: 'krikri-8b', cloud: false },
    { provider: 'anthropic', model: 'claude-x', cloud: true },
  ],
  gap_range: [2, 24],
  caps: { nights_per_job: 40, seconds_per_job: 3600 },
  nightly_at: '05:00',
  nightly_tz: 'Europe/Athens',
};

afterEach(() => {
  mockFetch.mockReset();
  mockDownload.mockReset();
  toast.mockReset();
});

const wrap = (ui) => render(<DesignProvider>{ui}</DesignProvider>);

test('settings load, validate the gap and save the whole form', async () => {
  const user = setupUser();
  const api = jest.fn(async (path, opts) => {
    if (opts && opts.method === 'PUT') {
      return { ok: true, data: { ...settingsBody, settings: { ...settingsBody.settings, ...opts.body } } };
    }
    return { ok: true, data: settingsBody };
  });
  wrap(<ChronicleSoFarSettings api={api} id={10} toast={toast} />);
  const box = await screen.findByTestId('sofar-settings');
  await user.click(within(box).getByText('Settings'));
  const gap = screen.getByLabelText('Night gap (hours)');
  expect(gap).toHaveValue(6);
  await user.clear(gap);
  await user.type(gap, '30');
  expect(screen.getByText('A whole number from 2 to 24.')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Save settings' })).toBeDisabled();
  await user.clear(gap);
  await user.type(gap, '4');
  await user.click(screen.getByRole('switch', { name: 'Nightly run' }));
  expect(screen.getByText(/At 05:00 \(Europe\/Athens\)/)).toBeInTheDocument();
  await user.selectOptions(screen.getByLabelText('Writer model'), 'anthropic|claude-x');
  expect(screen.getByRole('alert')).toHaveTextContent('hidden rolls included');
  await user.click(screen.getByRole('button', { name: 'Save settings' }));
  await waitFor(() => expect(api).toHaveBeenCalledWith('/campaigns/10/chronicle/settings', {
    method: 'PUT',
    body: { gap_hours: 4, nightly: true, model: { provider: 'anthropic', model: 'claude-x' } },
  }));
  expect(toast).toHaveBeenCalledWith(expect.objectContaining({ tone: 'ok', title: expect.stringMatching(/new gap/) }));
});

test('the panel shows settings only to the Storyteller and uses the table-talk default for exports', async () => {
  const user = setupUser();
  const base = {
    lang: 'el', own_lang: 'el', view: 'st', access: 'st', can_update: true, can_edit: true, quiet_minutes: 10,
    nights_written: 1, nights_total: 1, chapters: [], digest: null, job: null,
  };
  const api = jest.fn(async (path) => (path.endsWith('/settings')
    ? { ok: true, data: settingsBody }
    : { ok: true, data: { ...base, can_settings: true, settings: { ...settingsBody.settings, table_talk: true } } }));
  mockDownload.mockResolvedValue({ ok: true });
  const { unmount } = wrap(<ChronicleSoFarPanel api={api} campaign={{ id: 10, name: 'Athens' }} toast={toast} />);
  expect(await screen.findByTestId('sofar-settings')).toBeInTheDocument();
  expect(screen.getByRole('switch', { name: 'With table talk' })).toBeChecked();
  await user.click(screen.getByRole('button', { name: 'Export story' }));
  expect(mockDownload.mock.calls[0][0]).toBe('/campaigns/10/chronicle.md');  // the server's default applies
  await user.click(screen.getByRole('switch', { name: 'With table talk' }));
  await user.click(screen.getByRole('button', { name: 'Export story' }));
  expect(mockDownload.mock.calls[1][0]).toBe('/campaigns/10/chronicle.md?with_table_talk=0');
  unmount();
  const helperApi = jest.fn(async () => ({ ok: true, data: { ...base, access: 'helper', can_update: false, can_settings: false, settings: settingsBody.settings } }));
  wrap(<ChronicleSoFarPanel api={helperApi} campaign={{ id: 10, name: 'Athens' }} toast={toast} />);
  expect(await screen.findByTestId('sofar-status')).toBeInTheDocument();
  expect(screen.queryByTestId('sofar-settings')).toBeNull();
  expect(helperApi.mock.calls.some(([p]) => p.endsWith('/settings'))).toBe(false);
});

test('writer health: jobs today, median, failures, last error and live jobs', async () => {
  mockFetch.mockResolvedValue({ ok: true, data: {
    jobs_today: 3, failures_today: 1, seconds_per_night: 7.5, nightly_at: '05:00',
    last_error: { code: 'context', at: '2026-10-17T05:20:00' },
    jobs: [{ id: 9, campaign_id: 10, campaign_name: 'Athens', status: 'running', night: 2, nights: 5, nightly: true }],
  } });
  wrap(<WriterHealthPanel />);
  expect(await screen.findByText(/3 runs, 1 failed/)).toBeInTheDocument();
  expect(screen.getByText(/7\.5 s/)).toBeInTheDocument();
  expect(screen.getByText(/did not fit the model’s context \(context\)/)).toBeInTheDocument();
  expect(within(screen.getByTestId('writer-jobs')).getByText(/Athens · writing · night 2 of 5 · nightly/)).toBeInTheDocument();
  expect(mockFetch).toHaveBeenCalledWith('tok', '/chronicle-health');
});

test('archives list names, sizes and nights, and downloads both files', async () => {
  const user = setupUser();
  mockFetch.mockResolvedValue({ ok: true, data: { st_days: 30, archives: [{
    id: 4, campaign_name: 'Athens', storyteller: 'lef', deleted_by: 'siteadmin', size: 2048,
    nights: 5, nights_written: 4, created_at: '2026-10-10T12:00:00',
  }] } });
  mockDownload.mockResolvedValue({ ok: false, status: 410 });
  wrap(<ChronicleArchivesPanel admin />);
  expect(await screen.findByText(/Storyteller lef · deleted .* by siteadmin · 2 KB · 4 of 5 nights written/)).toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Minutes' }));
  expect(mockDownload).toHaveBeenCalledWith('/chronicle-archives/4/minutes', 'Athens — minutes.md');
  await user.click(screen.getByRole('button', { name: 'Transcript' }));
  expect(mockDownload).toHaveBeenLastCalledWith('/chronicle-archives/4/transcript', 'Athens — transcript.md');
});

test('archives: empty list and the Storyteller lead', async () => {
  mockFetch.mockResolvedValue({ ok: true, data: { st_days: 30, archives: [] } });
  wrap(<ChronicleArchivesPanel />);
  expect(await screen.findByText('No archived chronicles.')).toBeInTheDocument();
  expect(screen.getByText(/for 30 days after the delete/)).toBeInTheDocument();
});

test("a Storyteller sees an admin's cloud writer locked and never sends it", async () => {
  const user = setupUser();
  const cloud = { provider: 'anthropic', model: 'claude-x' };
  const body = { ...settingsBody, models: settingsBody.models.slice(0, 1), settings: { ...settingsBody.settings, model: cloud } };
  const api = jest.fn(async (path, opts) => (opts && opts.method === 'PUT'
    ? { ok: true, data: { ...body, settings: { ...body.settings, ...opts.body } } }
    : { ok: true, data: body }));
  wrap(<ChronicleSoFarSettings api={api} id={10} toast={toast} />);
  const box = await screen.findByTestId('sofar-settings');
  await user.click(within(box).getByText('Settings'));
  const select = screen.getByLabelText('Writer model');
  expect(select).toBeDisabled();
  expect(screen.getByRole('option', { name: 'claude-x · anthropic (set by a site admin)' })).toBeDisabled();
  expect(screen.getByRole('alert')).toHaveTextContent('hidden rolls included');
  await user.click(screen.getByRole('switch', { name: 'Nightly run' }));
  await user.click(screen.getByRole('button', { name: 'Save settings' }));
  await waitFor(() => expect(api).toHaveBeenCalledWith('/campaigns/10/chronicle/settings', { method: 'PUT', body: { nightly: true } }));
});

test('the Storyteller memory switch is on by default and sends memory: false', async () => {
  const user = setupUser();
  const api = jest.fn(async (path, opts) => (opts && opts.method === 'PUT'
    ? { ok: true, data: { ...settingsBody, settings: { ...settingsBody.settings, ...opts.body } } }
    : { ok: true, data: settingsBody }));
  wrap(<ChronicleSoFarSettings api={api} id={10} toast={toast} />);
  const box = await screen.findByTestId('sofar-settings');
  await user.click(within(box).getByText('Settings'));
  const sw = screen.getByRole('switch', { name: 'The Storyteller remembers the chronicle' });
  expect(sw).toHaveAttribute('aria-checked', 'true');
  expect(screen.getByText(/the last nights of this room from the chapters/)).toBeInTheDocument();
  await user.click(sw);
  await user.click(screen.getByRole('button', { name: 'Save settings' }));
  await waitFor(() => expect(api).toHaveBeenCalledWith('/campaigns/10/chronicle/settings', { method: 'PUT', body: { memory: false } }));
});
