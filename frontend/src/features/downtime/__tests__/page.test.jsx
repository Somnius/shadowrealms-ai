/** DowntimePage picks the view from is_storyteller and drives the roll form from rules_edition. */
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { DesignProvider, ToastProvider } from '../../../design';
import DowntimePage from '../DowntimePage';

const mockApi = jest.fn();
jest.mock('../../../app/AuthContext', () => ({ useApi: () => mockApi }));
jest.mock('../../../app/AppShell', () => ({
  TopBar: ({ title }) => <h1>{title}</h1>,
  PageBody: ({ children }) => <main>{children}</main>,
}));

const view = (over) => ({
  is_storyteller: false, rules_edition: 'v5', round: { id: 3, title: 'Winter', status: 'open' }, character: { id: 7, name: 'Eleni' },
  can_play: true, player_problem: null,
  projects: [{ id: 1, title: 'Find the library', goal: '', status: 'active', parent_id: null, parent_title: null, phases: [{
    id: 11, project_id: 1, round_id: 3, round_title: 'Winter', round_status: 'open', action: 'Dig', difficulty_hidden: false,
    ready: true, difficulty: 3, roll: null, status: 'declared',
  }] }],
  ...over,
});

const renderPage = () =>
  render(
    <MemoryRouter>
      <DesignProvider>
        <ToastProvider>
          <DowntimePage />
        </ToastProvider>
      </DesignProvider>
    </MemoryRouter>
  );

beforeEach(() => mockApi.mockReset());

test('a player gets the player view and no Storyteller calls (V5: no specialty box)', async () => {
  mockApi.mockResolvedValue({ ok: true, status: 200, data: view() });
  renderPage();
  expect(await screen.findByText('Find the library', { selector: 'strong' })).toBeInTheDocument();
  expect(screen.queryByLabelText('Specialty')).toBeNull();
  expect(mockApi.mock.calls.every(([p]) => !/\/(rounds|inbox|variables|changes)/.test(p))).toBe(true);
});

test('a Classic chronicle offers specialty from the downtime view alone', async () => {
  mockApi.mockResolvedValue({ ok: true, status: 200, data: view({ rules_edition: 'classic' }) });
  renderPage();
  expect(await screen.findByLabelText('Specialty')).toBeInTheDocument();
});

test('a Storyteller who also plays gets the tools and their own projects', async () => {
  mockApi.mockImplementation(async (path) => {
    if (path.includes('/rounds')) return { ok: true, status: 200, data: { rounds: [] } };
    if (path.includes('/inbox')) return { ok: true, status: 200, data: { round: null, phases: [], projects: [], variables: [], locations: [] } };
    return { ok: true, status: 200, data: view({ is_storyteller: true }) };
  });
  renderPage();
  expect(await screen.findByRole('button', { name: 'Open a round' })).toBeInTheDocument();
  expect(screen.getByText('Your own projects as a player')).toBeInTheDocument();
  expect(screen.getByText('Find the library', { selector: 'strong' })).toBeInTheDocument();
});

test('a failed load offers a retry', async () => {
  mockApi.mockResolvedValueOnce({ ok: false, status: 500, data: { code: 'server_error' } });
  renderPage();
  expect(await screen.findByText('Downtime request failed. Try again.')).toBeInTheDocument();
  mockApi.mockResolvedValue({ ok: true, status: 200, data: view() });
  screen.getByRole('button', { name: 'Try again' }).click();
  await waitFor(() => expect(screen.getByText('Find the library', { selector: 'strong' })).toBeInTheDocument());
});
