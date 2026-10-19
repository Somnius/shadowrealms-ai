import { act, render, screen, waitFor, within } from '@testing-library/react';
import { ToastProvider } from '../../design';
import setupUser from '../../design/testing/setupUser';
import { setLanguage } from '../../i18n';
import CharactersPanel, { filterCharacters } from '../admin/CharactersPanel';
import FallenNote from '../../components/FallenNote';

const DEATH = 'Η αυγή σε βρίσκει στο υπόγειο.';
const CHARS = [
  { id: 20, name: 'Kemal', owner_name: 'eleni', campaign_name: 'Harbor Nights', rules_edition: 'v5', is_active: true, death: null },
  {
    id: 21,
    name: 'Theo',
    owner_name: 'nikos',
    campaign_name: 'Constantinople',
    rules_edition: 'classic',
    is_active: false,
    death: { death_type: 'soft', death_description: DEATH, died_at: '2026-10-18T21:00:00Z' },
  },
];
const LOG = [
  { id: 1, action: 'kill', character_name: 'Theo', owner_name: 'nikos', campaign_name: 'Constantinople', death_type: 'soft',
    death_description: DEATH, admin_username: 'admin', moderated_at: '2026-10-18T21:00:00Z' },
];

const json = (status, body) => ({ ok: status >= 200 && status < 300, status, json: async () => body });

/** fetch mock; `kill` answers POST /kill (a promise lets the test hold the "writing" state). */
function mockFetch({ kill = () => json(200, { death_description: 'You fall.', generated: true }) } = {}) {
  global.fetch = jest.fn(async (url, init = {}) => {
    const u = String(url);
    if (u.endsWith('/kill')) return kill(JSON.parse(init.body));
    if (u.endsWith('/revive')) return json(200, { message: 'Character revived' });
    if (u.startsWith('/api/admin/character-deaths')) return json(200, LOG);
    if (u === '/api/admin/characters') return json(200, CHARS);
    return json(404, {});
  });
}

const showError = jest.fn();

function mount() {
  return render(
    <ToastProvider>
      <CharactersPanel token="jwt" displayTimezone="UTC" showError={showError} />
    </ToastProvider>
  );
}

const calls = (suffix) => global.fetch.mock.calls.filter(([u]) => String(u).endsWith(suffix));

afterEach(async () => {
  await act(async () => {
    await setLanguage('en', { remember: false, save: false });
  });
});

test('filterCharacters: search by name, owner or chronicle, and alive/fallen', () => {
  expect(filterCharacters(CHARS, 'harbor', 'all').map((c) => c.id)).toEqual([20]);
  expect(filterCharacters(CHARS, 'NIKOS', 'all').map((c) => c.id)).toEqual([21]);
  expect(filterCharacters(CHARS, '', 'fallen').map((c) => c.id)).toEqual([21]);
  expect(filterCharacters(CHARS, '', 'alive').map((c) => c.id)).toEqual([20]);
});

test('lists characters, their status and the deaths log', async () => {
  mockFetch();
  mount();
  expect(await screen.findByText('Kemal')).toBeInTheDocument();
  expect(screen.getAllByText('Fallen').length).toBeGreaterThan(0);
  expect(screen.getByText('eleni · Harbor Nights')).toBeInTheDocument();
  expect(await screen.findByText('admin killed Theo (Soft)')).toBeInTheDocument();
  expect(screen.getAllByText(DEATH)).toHaveLength(2); // on the card and in the log
});

test('kill: choose the type, confirm, wait while it writes, then the text and who wrote it', async () => {
  let answer;
  mockFetch({ kill: (body) => new Promise((resolve) => { answer = () => resolve(json(200, { death_description: `Died ${body.death_type}.`, generated: true })); }) });
  const user = setupUser();
  mount();
  await user.click(await screen.findByRole('button', { name: 'Kill' }));
  const dialog = screen.getByRole('dialog');
  expect(within(dialog).getByText(/retires the character for good/)).toBeInTheDocument();
  await user.click(within(dialog).getByRole('radio', { name: /Horrible/ }));
  await user.click(within(dialog).getByRole('button', { name: 'Kill for good' }));
  expect(await within(dialog).findByText(/can take up to 25 seconds/)).toBeInTheDocument();
  await act(async () => answer());
  expect(await within(dialog).findByText('Died horrible.')).toBeInTheDocument();
  expect(within(dialog).getByText('Written by the AI')).toBeInTheDocument();
  expect(calls('/kill')).toHaveLength(1);
  await waitFor(() => expect(calls('/api/admin/characters').length).toBeGreaterThan(1)); // reloaded
});

test('kill with the fixed sentence says so; an already fallen character is an error', async () => {
  mockFetch({ kill: () => json(200, { death_description: 'Your character fades.', generated: false }) });
  const user = setupUser();
  mount();
  await user.click(await screen.findByRole('button', { name: 'Kill' }));
  await user.click(screen.getByRole('button', { name: 'Kill for good' }));
  expect(await screen.findByText('Fixed sentence (the AI could not write it)')).toBeInTheDocument();
  await user.click(screen.getAllByRole('button', { name: 'Close' })[0]);

  global.fetch.mockImplementation(async (url) => (String(url).endsWith('/kill')
    ? json(409, { error_code: 'character_fallen' })
    : json(200, String(url).includes('deaths') ? [] : CHARS)));
  await user.click(await screen.findByRole('button', { name: 'Kill' }));
  await user.click(screen.getByRole('button', { name: 'Kill for good' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('This character has already fallen.');
});

test('revive asks first, then posts', async () => {
  mockFetch();
  const user = setupUser();
  mount();
  await user.click(await screen.findByRole('button', { name: 'Revive' }));
  expect(screen.getByText(/The death stays in the log/)).toBeInTheDocument();
  await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Revive' }));
  await waitFor(() => expect(calls('/revive')).toHaveLength(1));
});

test('the panel and the fallen note are translated to Greek', async () => {
  await act(async () => {
    await setLanguage('el', { remember: false, save: false });
  });
  mockFetch();
  mount();
  expect(await screen.findByRole('heading', { name: 'Χαρακτήρες' })).toBeInTheDocument();
  expect(await screen.findAllByRole('button', { name: 'Θάνατος' })).toHaveLength(1);
  render(<FallenNote character={CHARS[1]} />);
  expect(screen.getByText('Έπεσε')).toBeInTheDocument();
});

test('FallenNote shows nothing for a living character', () => {
  const { container } = render(<FallenNote character={CHARS[0]} />);
  expect(container).toBeEmptyDOMElement();
});
