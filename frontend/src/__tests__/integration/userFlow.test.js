/**
 * Integration tests for the main user flows through the v0.9 app shell (router + providers),
 * with fetch mocked per route.
 */
import React from 'react';
import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import setupUser from '../../design/testing/setupUser';
import App from '../../app/App';

const ME_PLAYER = { id: 1, username: 'testuser', role: 'player', email: 't@example.com', statistics: { characters_owned: 0 } };

function json(status, body) {
  return Promise.resolve({ ok: status >= 200 && status < 300, status, json: async () => body });
}

/** routes: { 'POST /api/auth/login': (body) => [status, json] } ; unknown routes → 200 [] */
function mockFetch(routes) {
  global.fetch = jest.fn((url, opts = {}) => {
    const method = opts.method || 'GET';
    const path = String(url).split('?')[0];
    const key = `${method} ${path}`;
    const body = opts.body ? JSON.parse(opts.body) : undefined;
    if (routes[key]) {
      const [status, payload] = routes[key](body, url);
      return json(status, payload);
    }
    return json(200, []);
  });
}

function renderAt(path) {
  return render(
    <MemoryRouter initialEntries={[path]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <App />
    </MemoryRouter>
  );
}

const calls = (method, path) =>
  global.fetch.mock.calls.filter(([url, opts = {}]) => (opts.method || 'GET') === method && String(url).split('?')[0] === path);

beforeEach(() => {
  localStorage.clear();
});

describe('Authentication flow', () => {
  it('registers with an invite code and lands in the chronicle hall', async () => {
    mockFetch({
      'POST /api/auth/register': () => [201, { access_token: 'test-token' }],
      'GET /api/users/me': () => [200, ME_PLAYER],
      'GET /api/campaigns/': () => [200, []],
    });
    const u = setupUser();
    renderAt('/login');
    await u.click(screen.getByRole('tab', { name: /register/i }));
    await u.type(screen.getByLabelText(/username/i), 'testuser');
    await u.type(screen.getByLabelText(/email/i), 'test@example.com');
    await u.type(screen.getByLabelText(/^password/i), 'SecurePass123');
    await u.type(screen.getByLabelText(/invite code/i), 'VALID-CODE');
    await u.click(screen.getByRole('button', { name: /create account/i }));
    await waitFor(() => expect(calls('POST', '/api/auth/register')).toHaveLength(1));
    expect(JSON.parse(calls('POST', '/api/auth/register')[0][1].body)).toMatchObject({ username: 'testuser', invite_code: 'VALID-CODE' });
    expect(await screen.findByRole('heading', { name: /chronicle hall/i })).toBeInTheDocument();
    expect(localStorage.getItem('token')).toBe('test-token');
  });

  it('shows the server error for an invalid invite code', async () => {
    mockFetch({ 'POST /api/auth/register': () => [400, { error: 'Invalid invite code' }] });
    const u = setupUser();
    renderAt('/login');
    await u.click(screen.getByRole('tab', { name: /register/i }));
    await u.type(screen.getByLabelText(/username/i), 'x');
    await u.type(screen.getByLabelText(/email/i), 'x@example.com');
    await u.type(screen.getByLabelText(/^password/i), 'pw');
    await u.type(screen.getByLabelText(/invite code/i), 'NOPE');
    await u.click(screen.getByRole('button', { name: /create account/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid invite code');
    expect(localStorage.getItem('token')).toBeNull();
  });

  it('logs in and shows every chronicle with its own character', async () => {
    mockFetch({
      'POST /api/auth/login': () => [200, { access_token: 'jwt-1' }],
      'GET /api/users/me': () => [200, ME_PLAYER],
      'GET /api/campaigns/': () => [
        200,
        [
          { id: 3, name: 'Night Court', game_system: 'vampire', rules_edition: 'v5', my_playing_character_name: 'Yorika' },
          { id: 2, name: 'Old Blood', game_system: 'vampire', rules_edition: 'classic' },
        ],
      ],
    });
    const u = setupUser();
    renderAt('/login');
    await u.type(screen.getByLabelText(/username/i), 'testuser');
    await u.type(screen.getByLabelText(/password/i), 'pw');
    await u.click(screen.getByRole('button', { name: /enter/i }));
    const main = await screen.findByRole('main');
    expect(await within(main).findByRole('link', { name: 'Night Court' })).toHaveAttribute('href', '/c/3');
    expect(screen.getByText('Yorika')).toBeInTheDocument();
    expect(screen.getByText(/no character in this chronicle yet/i)).toBeInTheDocument();
    expect(calls('GET', '/api/campaigns/')[0][0]).not.toContain('for_active_character');
  });

  it('shows the login error', async () => {
    mockFetch({ 'POST /api/auth/login': () => [401, { error: 'Invalid credentials' }] });
    const u = setupUser();
    renderAt('/login');
    await u.type(screen.getByLabelText(/username/i), 'x');
    await u.type(screen.getByLabelText(/password/i), 'y');
    await u.click(screen.getByRole('button', { name: /enter/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid credentials');
  });

  it('sends unauthenticated deep links to the login page', async () => {
    mockFetch({});
    renderAt('/c/3/7');
    expect(await screen.findByRole('tab', { name: /sign in/i })).toBeInTheDocument();
  });
});

describe('Chronicle management', () => {
  beforeEach(() => {
    localStorage.setItem('token', 'jwt');
    localStorage.setItem('user', JSON.stringify({ ...ME_PLAYER, role: 'admin' }));
  });

  it('creates a V5 chronicle and opens its settings', async () => {
    mockFetch({
      'GET /api/users/me': () => [200, { ...ME_PLAYER, role: 'admin' }],
      'POST /api/campaigns': () => [201, { campaign_id: 42, rules_edition: 'v5' }],
      'GET /api/campaigns/42': () => [200, { id: 42, name: 'New Night', description: 'd', game_system: 'vampire', rules_edition: 'v5', created_by: 1 }],
      'GET /api/campaigns/42/roster': () => [200, { members: [] }],
      'GET /api/characters/': () => [200, { characters: [] }],
      'GET /api/campaigns/42/stats': () => [200, {}],
      'GET /api/campaigns/42/locations': () => [200, []],
    });
    const u = setupUser();
    renderAt('/chronicles/new');
    await u.type(await screen.findByLabelText(/^name/i), 'New Night');
    await u.type(screen.getByLabelText(/world and setting/i), 'A city of masks.');
    await u.click(within(screen.getByTestId('rules-edition-choice')).getByLabelText(/v5/i));
    await u.click(screen.getByRole('button', { name: /create chronicle/i }));
    await waitFor(() => expect(calls('POST', '/api/campaigns')).toHaveLength(1));
    expect(JSON.parse(calls('POST', '/api/campaigns')[0][1].body)).toEqual({
      name: 'New Night',
      description: 'A city of masks.',
      game_system: 'vampire',
      rules_edition: 'v5',
    });
    expect(await screen.findByRole('link', { name: /enter chronicle/i })).toHaveAttribute('href', '/c/42');
  });

  it('renders hostile chronicle names as text', async () => {
    mockFetch({
      'GET /api/users/me': () => [200, ME_PLAYER],
      'GET /api/campaigns/': () => [200, [{ id: 9, name: '<img src=x onerror=alert(1)>', game_system: 'vampire', description: '<script>alert(1)</script>' }]],
    });
    const { container } = renderAt('/chronicles');
    const main = await screen.findByRole('main');
    expect(await within(main).findByText('<img src=x onerror=alert(1)>')).toBeInTheDocument();
    expect(container.querySelector('img[src="x"]')).toBeNull();
    expect(container.querySelector('script')).toBeNull();
  });
});

describe('Session', () => {
  it('logging out clears the stored token and profile', async () => {
    localStorage.setItem('token', 'jwt');
    localStorage.setItem('user', JSON.stringify(ME_PLAYER));
    mockFetch({ 'GET /api/users/me': () => [200, ME_PLAYER], 'GET /api/campaigns/': () => [200, []] });
    const u = setupUser();
    renderAt('/chronicles');
    await u.click(await screen.findByRole('button', { name: /account menu for testuser/i }));
    await u.click(screen.getByRole('menuitem', { name: /log out/i }));
    expect(localStorage.getItem('token')).toBeNull();
    expect(localStorage.getItem('user')).toBeNull();
    expect(await screen.findByRole('tab', { name: /sign in/i })).toBeInTheDocument();
  });

  it('a 401 from the API logs the user out', async () => {
    localStorage.setItem('token', 'expired');
    localStorage.setItem('user', JSON.stringify(ME_PLAYER));
    mockFetch({ 'GET /api/users/me': () => [401, { msg: 'Token has expired' }] });
    renderAt('/chronicles');
    expect(await screen.findByRole('tab', { name: /sign in/i })).toBeInTheDocument();
    expect(localStorage.getItem('token')).toBeNull();
  });
});
