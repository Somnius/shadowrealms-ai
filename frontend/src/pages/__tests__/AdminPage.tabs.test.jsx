import React from 'react';
import { act, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { ToastProvider } from '../../design';
import setupUser from '../../design/testing/setupUser';
import { setLanguage } from '../../i18n';
import AdminPage, { ADMIN_SECTIONS } from '../AdminPage';

function Where() {
  return <div data-testid="where">{useLocation().pathname}</div>;
}

function mount(path) {
  return render(
    <ToastProvider>
      <MemoryRouter initialEntries={[path]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Routes>
          <Route
            path="/admin/*"
            element={
              <>
                <AdminPage token="jwt" user={{ id: 1, username: 'claude_test', role: 'admin' }} />
                <Where />
              </>
            }
          />
        </Routes>
      </MemoryRouter>
    </ToastProvider>
  );
}

/** Let the mount-time fetches (users, invites, section data) resolve inside act(). */
async function flush() {
  for (let i = 0; i < 3; i += 1) {
    // eslint-disable-next-line no-await-in-loop
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
  }
}

beforeEach(() => {
  // Every admin endpoint answers "empty": lists are [], objects have no fields.
  global.fetch = jest.fn(async () => ({ ok: true, status: 200, json: async () => [] }));
});

afterEach(async () => {
  await act(async () => {
    await setLanguage('en', { remember: false, save: false });
  });
});

test('renders one tab per admin section, no separate sidebar', async () => {
  mount('/admin');
  await flush();
  const tabs = screen.getAllByRole('tab');
  expect(tabs).toHaveLength(ADMIN_SECTIONS.length);
  expect(screen.getByRole('tab', { name: 'Overview' })).toHaveAttribute('aria-selected', 'true');
  expect(screen.getByRole('heading', { name: 'Admin panel' })).toBeInTheDocument();
  expect(screen.queryByRole('navigation', { name: 'Admin sections' })).toBeNull();
  await waitFor(() => expect(global.fetch).toHaveBeenCalled());
});

test('clicking a tab opens that section and its URL', async () => {
  const user = setupUser();
  mount('/admin');
  await flush();
  await user.click(screen.getByRole('tab', { name: 'Invite codes' }));
  expect(screen.getByTestId('where').textContent).toBe('/admin/invites');
  expect(screen.getByRole('heading', { name: 'Invite codes (sign-up)' })).toBeInTheDocument();
  expect(await screen.findByText('No invites yet. Create one above.')).toBeInTheDocument();

  await user.click(screen.getByRole('tab', { name: 'Users' }));
  expect(screen.getByTestId('where').textContent).toBe('/admin/users');
  expect(screen.getByRole('heading', { name: 'User management' })).toBeInTheDocument();
  await flush();
});

test('a sub-route opens its section directly (AI system)', async () => {
  mount('/admin/ai');
  await flush();
  expect(screen.getByRole('tab', { name: 'AI system' })).toHaveAttribute('aria-selected', 'true');
  expect(await screen.findByTestId('ai-providers-panel')).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'Models per role' })).toBeInTheDocument();
  await flush();
});

test('the admin tabs are translated to Greek', async () => {
  await act(async () => {
    await setLanguage('el', { remember: false, save: false });
  });
  mount('/admin/moderation');
  await flush();
  expect(screen.getByRole('tab', { name: 'Επισκόπηση' })).toBeInTheDocument();
  expect(screen.getByRole('tab', { name: 'Ημερολόγιο ελέγχου' })).toHaveAttribute('aria-selected', 'true');
  await waitFor(() => expect(global.fetch).toHaveBeenCalled());
});

test('the Logins & lockouts tab opens the unlock form and the login audit', async () => {
  global.fetch = jest.fn(async () => ({ ok: true, status: 200, json: async () => ({ events: [], has_more: false }) }));
  mount('/admin/security');
  await flush();
  expect(screen.getByRole('tab', { name: 'Logins & lockouts' })).toHaveAttribute('aria-selected', 'true');
  expect(screen.getByTestId('security-panel')).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'Unlock sign-in' })).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'Login audit' })).toBeInTheDocument();
  expect(global.fetch.mock.calls.some(([u]) => String(u).startsWith('/api/admin/auth-events?'))).toBe(true);
});
