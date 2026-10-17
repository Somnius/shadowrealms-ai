/**
 * Characters with no chronicle yet: Profile → Characters shows a "No chronicle yet" badge and a
 * "Bring into a chronicle" action that lists only fitting chronicles; the play panel offers them.
 */
import { act, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router';
import setupUser from '../../../design/testing/setupUser';
import { DesignProvider, ToastProvider } from '../../../design';
import { setLanguage } from '../../../i18n';
import ProfilePage from '../ProfilePage';
import MemberPanel from '../../play/MemberPanel';
import { fitsChronicle, isUnassigned } from '../BringIntoChronicle';

const mockApi = jest.fn();
const mockReloadChronicles = jest.fn();
const mockChronicles = [
  { id: 8, name: 'Athens by Night', game_system: 'vampire', rules_edition: 'v5' },
  { id: 9, name: 'Constantinople Nights', game_system: 'vampire', rules_edition: 'classic' },
  { id: 12, name: 'Wolves of Pindus', game_system: 'werewolf', rules_edition: 'classic' },
];

// stable objects: the components reload when `user` changes identity
const mockAuth = { user: { id: 13, username: 'volkan', role: 'player' }, isAdmin: false };
jest.mock('../../../app/AuthContext', () => ({
  useAuth: () => mockAuth,
  useApi: () => mockApi,
}));
const mockChroniclesValue = { chronicles: mockChronicles, reload: mockReloadChronicles };
jest.mock('../../../app/ChroniclesContext', () => ({
  useChronicles: () => mockChroniclesValue,
}));
const mockSheet = { openSheet: () => {} };
jest.mock('../../../app/SheetContext', () => ({ useSheet: () => mockSheet }));
jest.mock('../../../app/SignOutEverywhere', () => ({ useSignOutEverywhere: () => () => {} }));

const volkan = {
  id: 10, name: 'Volkan Kibar', user_id: 13, campaign_id: null, system_type: 'vampire',
  rules_edition: 'v5', wod_meta: { edition: 'v5' }, is_active: true,
};
const theodore = {
  id: 8, name: 'Theodore Doukas', user_id: 13, campaign_id: 9, campaign_name: 'Constantinople Nights',
  system_type: 'vampire', rules_edition: 'classic', is_active: true,
};

let assigned;
beforeEach(() => {
  assigned = false;
  sessionStorage.clear();
  mockApi.mockReset();
  mockReloadChronicles.mockReset();
  mockApi.mockImplementation(async (path, opts) => {
    if (path === '/characters/') {
      const v = assigned ? { ...volkan, campaign_id: 8, campaign_name: 'Athens by Night' } : volkan;
      return { ok: true, status: 200, data: { characters: [v, theodore] } };
    }
    if (path === '/characters/10/assign' && opts && opts.method === 'POST') {
      assigned = true;
      return { ok: true, status: 200, data: { character_id: 10, campaign_id: opts.body.campaign_id, campaign_name: 'Athens by Night' } };
    }
    return { ok: false, status: 404, data: {} };
  });
});

function renderProfile() {
  return render(
    <DesignProvider>
      <ToastProvider>
        <MemoryRouter initialEntries={['/profile/characters']}>
          <Routes>
            <Route path="/profile/:section" element={<ProfilePage />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </DesignProvider>
  );
}

test('helpers: unassigned and fitting chronicles (edition and game line)', () => {
  expect(isUnassigned(volkan)).toBe(true);
  expect(isUnassigned(theodore)).toBe(false);
  expect(mockChronicles.filter((c) => fitsChronicle(volkan, c)).map((c) => c.id)).toEqual([8]);
  expect(mockChronicles.filter((c) => fitsChronicle({ ...theodore, campaign_id: null }, c)).map((c) => c.id)).toEqual([9]);
  expect(fitsChronicle({ system_type: 'vampire' }, { game_system: 'custom', rules_edition: 'classic' })).toBe(true);
});

test('profile shows the badge, and bringing a character in lists only fitting chronicles', async () => {
  const user = setupUser();
  renderProfile();
  const card = (await screen.findByText('Volkan Kibar')).closest('.sr-char');
  expect(within(card).getByText('No chronicle yet')).toBeInTheDocument();
  // no chronicle link (a V5 vampire's only link is the ghoul forge)
  expect(within(card).queryAllByRole('link').map((l) => l.textContent)).toEqual(['Add a ghoul retainer']);
  // a character in a chronicle keeps its chronicle link and has no bring action
  const other = screen.getByText('Theodore Doukas').closest('.sr-char');
  expect(within(other).getByRole('link', { name: 'Constantinople Nights' })).toBeInTheDocument();
  expect(within(other).queryByRole('button', { name: 'Bring into a chronicle' })).toBeNull();

  await user.click(within(card).getByRole('button', { name: 'Bring into a chronicle' }));
  const dialog = await screen.findByRole('dialog');
  const select = within(dialog).getByLabelText('Chronicle');
  expect(within(select).getAllByRole('option').map((o) => o.textContent)).toEqual(['Athens by Night']);
  await user.click(within(dialog).getByRole('button', { name: 'Bring into chronicle' }));

  await waitFor(() => expect(mockApi).toHaveBeenCalledWith('/characters/10/assign', { method: 'POST', body: { campaign_id: 8 } }));
  await waitFor(() => expect(screen.queryByText('No chronicle yet')).toBeNull());
  expect(screen.getByRole('link', { name: 'Athens by Night' })).toBeInTheDocument();
  expect(mockReloadChronicles).toHaveBeenCalled();
});

test('an edition mismatch from the server is shown translated', async () => {
  mockApi.mockImplementation(async (path) => {
    if (path === '/characters/') return { ok: true, status: 200, data: { characters: [volkan] } };
    return { ok: false, status: 400, data: { error: 'x', error_code: 'rules_edition_mismatch' } };
  });
  const user = setupUser();
  renderProfile();
  await user.click(await screen.findByRole('button', { name: 'Bring into a chronicle' }));
  await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Bring into chronicle' }));
  expect(await screen.findByText('This character uses different rules than that chronicle.')).toBeInTheDocument();
});

test('in Greek the badge reads "Χωρίς χρονικό ακόμα"', async () => {
  await act(async () => {
    await setLanguage('el', { remember: false, save: false });
  });
  try {
    renderProfile();
    expect(await screen.findByText('Χωρίς χρονικό ακόμα')).toBeInTheDocument();
  } finally {
    await act(async () => {
      await setLanguage('en', { remember: false, save: false });
    });
  }
});

test('play panel without a character offers fitting unassigned characters', async () => {
  const user = setupUser();
  const onAssigned = jest.fn();
  const toast = jest.fn();
  const panel = (campaign) => (
    <DesignProvider>
      <MemoryRouter>
        <MemberPanel campaign={campaign} character={null} members={[]} user={{ id: 13 }} onCharacterAssigned={onAssigned} toast={toast} />
      </MemoryRouter>
    </DesignProvider>
  );
  const { rerender } = render(panel(mockChronicles[1]));
  await waitFor(() => expect(mockApi).toHaveBeenCalledWith('/characters/'));
  expect(screen.queryByRole('button', { name: 'Bring Volkan Kibar here' })).toBeNull();

  rerender(panel(mockChronicles[0]));
  await user.click(await screen.findByRole('button', { name: 'Bring Volkan Kibar here' }));
  await waitFor(() => expect(onAssigned).toHaveBeenCalled());
  expect(mockApi).toHaveBeenCalledWith('/characters/10/assign', { method: 'POST', body: { campaign_id: 8 } });
  expect(toast).toHaveBeenCalledWith(expect.objectContaining({ tone: 'ok' }));
});

// --- ghouls: no chronicle by design ---------------------------------------------------------

const ayla = {
  id: 31, name: 'Ayla', user_id: 13, campaign_id: null, system_type: 'vampire', rules_edition: 'v5', sheet_kind: 'ghoul',
  wod_meta: { edition: 'v5', sheet_kind: 'ghoul', ghoul: { template: 'gifted', domitor: { character_id: 10, name: 'Volkan Kibar' } } },
  is_active: true,
};

test('a ghoul sits under its domitor, says whose it is, and is never brought into a chronicle', async () => {
  mockApi.mockImplementation(async (path) =>
    path === '/characters/' ? { ok: true, status: 200, data: { characters: [ayla, theodore, volkan] } } : { ok: false, status: 404, data: {} }
  );
  renderProfile();
  const card = (await screen.findByText('Ayla')).closest('.sr-char');
  expect(within(card).getByText('Ghoul of Volkan Kibar')).toBeInTheDocument();
  expect(within(card).queryByText('No chronicle yet')).toBeNull();
  expect(within(card).queryByRole('button', { name: 'Bring into a chronicle' })).toBeNull();
  expect(within(card).queryByRole('link', { name: 'Add a ghoul retainer' })).toBeNull();
  // the ghoul comes right after its domitor
  const names = [...document.querySelectorAll('.sr-char__name')].map((n) => n.textContent.replace('↳ ', ''));
  expect(names).toEqual(['Theodore Doukas', 'Volkan Kibar', 'Ayla']);
  // a V5 vampire and a Classic one both offer the ghoul forge (of their own edition)
  const volkanCard = screen.getByText('Volkan Kibar').closest('.sr-char');
  expect(within(volkanCard).getByRole('link', { name: 'Add a ghoul retainer' })).toHaveAttribute('href', '/profile/characters/new?ghoul_of=10');
  expect(within(screen.getByText('Theodore Doukas').closest('.sr-char')).getByRole('link', { name: 'Add a ghoul retainer' })).toHaveAttribute(
    'href',
    '/profile/characters/new?ghoul_of=8'
  );
});

test("a Classic vampire's ghoul sits under it too", async () => {
  const marta = {
    id: 32, name: 'Marta Ionescu', user_id: 13, campaign_id: null, system_type: 'vampire', rules_edition: 'classic', sheet_kind: 'ghoul',
    wod_meta: { sheet_kind: 'ghoul', ghoul: { kind: 'vassal', domitor: { character_id: 8, name: 'Theodore Doukas' } }, blood_pool: { max: 10, current: 6, per_turn: 1 } },
    is_active: true,
  };
  mockApi.mockImplementation(async (path) =>
    path === '/characters/' ? { ok: true, status: 200, data: { characters: [marta, volkan, theodore] } } : { ok: false, status: 404, data: {} }
  );
  renderProfile();
  const card = (await screen.findByText('Marta Ionescu')).closest('.sr-char');
  expect(within(card).getByText('Ghoul of Theodore Doukas')).toBeInTheDocument();
  expect(within(card).queryByRole('button', { name: 'Bring into a chronicle' })).toBeNull();
  expect(within(card).queryByRole('link', { name: 'Add a ghoul retainer' })).toBeNull();
  const names = [...document.querySelectorAll('.sr-char__name')].map((n) => n.textContent.replace('↳ ', ''));
  expect(names.indexOf('Marta Ionescu')).toBe(names.indexOf('Theodore Doukas') + 1);
});

test('the play panel never offers a ghoul', async () => {
  mockApi.mockImplementation(async (path) =>
    path === '/characters/' ? { ok: true, status: 200, data: { characters: [ayla] } } : { ok: false, status: 404, data: {} }
  );
  render(
    <DesignProvider>
      <MemoryRouter>
        <MemberPanel campaign={mockChronicles[0]} character={null} members={[]} user={{ id: 13 }} onCharacterAssigned={() => {}} toast={() => {}} />
      </MemoryRouter>
    </DesignProvider>
  );
  await waitFor(() => expect(mockApi).toHaveBeenCalledWith('/characters/'));
  expect(screen.queryByRole('button', { name: 'Bring Ayla here' })).toBeNull();
});

test("the ghoul page opens the forge of the domitor's edition", async () => {
  const CharacterCreatePage = require('../CharacterCreatePage').default;
  mockApi.mockImplementation(async (path) =>
    path === '/characters/' ? { ok: true, status: 200, data: { characters: [volkan, theodore] } } : { ok: false, status: 404, data: {} }
  );
  const page = (id) =>
    render(
      <DesignProvider>
        <ToastProvider>
          <MemoryRouter initialEntries={[`/profile/characters/new?ghoul_of=${id}`]}>
            <Routes>
              <Route path="/profile/characters/new" element={<CharacterCreatePage />} />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </DesignProvider>
    );
  const classic = page(8);
  expect(await screen.findByText('Ghoul forge · Classic (Revised)')).toBeInTheDocument();
  expect(screen.getByText(/A Classic vampire's ghoul is a Classic sheet/)).toBeInTheDocument();
  classic.unmount();
  const v5 = page(10);
  expect(await screen.findByText('Ghoul forge · V5')).toBeInTheDocument();
  v5.unmount();
  // an id that isn't one of yours: a message, not another vampire's forge
  page(999);
  expect(await screen.findByText(/isn't one of your characters, or can't have ghouls/)).toBeInTheDocument();
  expect(screen.queryByText(/Ghoul forge/)).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Back to your characters' })).toBeInTheDocument();
});

test('while the list loads the page says blood is being drawn, and the next visit shows the last list at once', async () => {
  let release;
  mockApi.mockImplementation((path) =>
    path === '/characters/'
      ? new Promise((r) => {
          release = () => r({ ok: true, status: 200, data: { characters: [volkan, theodore] } });
        })
      : Promise.resolve({ ok: false, status: 404, data: {} })
  );
  const first = renderProfile();
  expect(screen.getByRole('status')).toHaveTextContent('Drawing blood…');
  await act(async () => release());
  expect(await screen.findByText('Volkan Kibar')).toBeInTheDocument();
  expect(screen.queryByText('Drawing blood…')).toBeNull();
  first.unmount();

  // second visit: the cached list is there before the server answers
  renderProfile();
  expect(screen.getByText('Volkan Kibar')).toBeInTheDocument();
  expect(screen.queryByText('Drawing blood…')).toBeNull();
  await act(async () => release());
});
