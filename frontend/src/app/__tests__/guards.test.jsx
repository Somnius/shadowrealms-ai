import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { AuthProvider } from '../AuthContext';
import { RedirectIfAuthed, RequireAdmin, RequireAuth, afterLoginPath } from '../guards';

function Where() {
  const loc = useLocation();
  return <div data-testid="where">{`${loc.pathname}|${loc.state && loc.state.from ? loc.state.from.pathname : ''}`}</div>;
}

function mount(path) {
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={[path]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Routes>
          <Route path="/login" element={<RedirectIfAuthed><Where /></RedirectIfAuthed>} />
          <Route path="/chronicles" element={<RequireAuth><div>hall</div></RequireAuth>} />
          <Route path="/c/:id/:loc" element={<RequireAuth><Where /></RequireAuth>} />
          <Route path="/admin" element={<RequireAuth><RequireAdmin><div>admin area</div></RequireAdmin></RequireAuth>} />
        </Routes>
      </MemoryRouter>
    </AuthProvider>
  );
}

beforeEach(() => {
  localStorage.clear();
  global.fetch = jest.fn(async () => ({ ok: false, status: 500, json: async () => ({}) }));
});

test('unauthenticated users are sent to /login, remembering where they were going', () => {
  mount('/c/3/7');
  expect(screen.getByTestId('where').textContent).toBe('/login|/c/3/7');
});

test('logged-in users skip /login and land on the hall', () => {
  localStorage.setItem('token', 'jwt');
  localStorage.setItem('user', JSON.stringify({ id: 1, username: 'lef', role: 'player' }));
  mount('/login');
  expect(screen.getByText('hall')).toBeInTheDocument();
});

test('a deep link survives a reload while logged in', () => {
  localStorage.setItem('token', 'jwt');
  localStorage.setItem('user', JSON.stringify({ id: 1, username: 'lef', role: 'player' }));
  mount('/c/3/7');
  expect(screen.getByTestId('where').textContent).toBe('/c/3/7|');
});

test('admin routes: players are redirected, admins get in', () => {
  localStorage.setItem('token', 'jwt');
  localStorage.setItem('user', JSON.stringify({ id: 1, username: 'lef', role: 'player' }));
  const { unmount } = mount('/admin');
  expect(screen.queryByText('admin area')).toBeNull();
  expect(screen.getByText('hall')).toBeInTheDocument();
  unmount();
  localStorage.setItem('user', JSON.stringify({ id: 1, username: 'boss', role: 'admin' }));
  mount('/admin');
  expect(screen.getByText('admin area')).toBeInTheDocument();
});

test('afterLoginPath ignores /login and keeps query + hash', () => {
  expect(afterLoginPath(null)).toBe('/chronicles');
  expect(afterLoginPath({ from: { pathname: '/login' } })).toBe('/chronicles');
  expect(afterLoginPath({ from: { pathname: '/c/3/7', search: '?x=1', hash: '#m-5' } })).toBe('/c/3/7?x=1#m-5');
});
