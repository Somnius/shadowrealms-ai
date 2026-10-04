import React from 'react';
import { act, render, waitFor } from '@testing-library/react';
import { AuthProvider, useAuth } from '../AuthContext';
import { getLanguage, setLanguage } from '../../i18n';

function mockServer(saved) {
  const calls = [];
  global.fetch = jest.fn(async (url, opts = {}) => {
    calls.push([url, opts.method || 'GET', opts.body]);
    if (url === '/api/users/me/language' && (opts.method || 'GET') === 'GET') {
      return { ok: true, status: 200, json: async () => ({ ui_language: saved }) };
    }
    if (url === '/api/users/me') return { ok: true, status: 200, json: async () => ({ id: 2, username: 'bob', role: 'player' }) };
    return { ok: true, status: 200, json: async () => ({}) };
  });
  return calls;
}

beforeEach(async () => {
  localStorage.clear();
  await act(async () => {
    await setLanguage('en', { remember: false, save: false });
  });
});

test("another account's stored language is not copied onto this user", async () => {
  localStorage.setItem('sr_lang', 'el');
  localStorage.setItem('sr_lang_owner', '1'); // chosen by user 1
  localStorage.setItem('token', 'jwt');
  localStorage.setItem('user', JSON.stringify({ id: 2, username: 'bob', role: 'player' }));
  const calls = mockServer(null);
  render(<AuthProvider><span /></AuthProvider>);
  await waitFor(() => expect(calls.some(([u, m]) => u === '/api/users/me/language' && m === 'GET')).toBe(true));
  await waitFor(() => expect(localStorage.getItem('sr_lang')).toBeNull());
  expect(calls.some(([u, m]) => u === '/api/users/me/language' && m === 'PUT')).toBe(false);
});

test('a choice made while signed out is saved to the account that signs in', async () => {
  await act(async () => {
    await setLanguage('el'); // signed out: owner "anon"
  });
  expect(localStorage.getItem('sr_lang_owner')).toBe('anon');
  localStorage.setItem('token', 'jwt');
  localStorage.setItem('user', JSON.stringify({ id: 2, username: 'bob', role: 'player' }));
  const calls = mockServer(null);
  render(<AuthProvider><span /></AuthProvider>);
  await waitFor(() =>
    expect(calls).toContainEqual(['/api/users/me/language', 'PUT', JSON.stringify({ ui_language: 'el' })])
  );
  expect(getLanguage()).toBe('el');
  await waitFor(() => expect(localStorage.getItem('sr_lang_owner')).toBe('2'));
});

function Grab({ into }) {
  into.current = useAuth();
  return null;
}

test('logout calls the server, then clears local state even when the server call fails', async () => {
  localStorage.setItem('token', 'jwt');
  localStorage.setItem('user', JSON.stringify({ id: 2, username: 'bob', role: 'player' }));
  sessionStorage.setItem('sr_draft_2:3:7', 'draft');
  const calls = [];
  global.fetch = jest.fn(async (url, opts = {}) => {
    calls.push([url, opts.method || 'GET', opts.headers && opts.headers.Authorization]);
    if (url === '/api/auth/logout') throw new Error('offline');
    return { ok: true, status: 200, json: async () => ({}) };
  });
  const ref = { current: null };
  render(<AuthProvider><Grab into={ref} /></AuthProvider>);
  await act(async () => {
    await ref.current.logout();
  });
  expect(calls).toContainEqual(['/api/auth/logout', 'POST', 'Bearer jwt']);
  expect(localStorage.getItem('token')).toBeNull();
  expect(sessionStorage.getItem('sr_draft_2:3:7')).toBeNull();
  expect(ref.current.token).toBeNull();
});

test('sign out everywhere only clears the session when the server confirmed it', async () => {
  localStorage.setItem('token', 'jwt');
  localStorage.setItem('user', JSON.stringify({ id: 2, username: 'bob', role: 'player' }));
  global.fetch = jest.fn(async (url) =>
    url === '/api/auth/logout-all'
      ? { ok: false, status: 503, json: async () => ({ code: 'UNAVAILABLE' }) }
      : { ok: true, status: 200, json: async () => ({}) }
  );
  const ref = { current: null };
  render(<AuthProvider><Grab into={ref} /></AuthProvider>);
  let r;
  await act(async () => {
    r = await ref.current.logout({ everywhere: true });
  });
  expect(r.ok).toBe(false);
  expect(ref.current.token).toBe('jwt');
  global.fetch = jest.fn(async () => ({ ok: true, status: 200, json: async () => ({}) }));
  await act(async () => {
    r = await ref.current.logout({ everywhere: true });
  });
  expect(r.ok).toBe(true);
  expect(global.fetch).toHaveBeenCalledWith('/api/auth/logout-all', expect.objectContaining({ method: 'POST' }));
  expect(ref.current.token).toBeNull();
});
