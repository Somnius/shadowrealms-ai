import React from 'react';
import { act, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import setupUser from '../../design/testing/setupUser';
import App from '../../app/App';
import {
  browserLanguage,
  formatList,
  formatNumber,
  getLanguage,
  getLocale,
  normalizeLanguage,
  setLanguage,
  t,
  useT,
} from '..';
import { Term, termHint } from '../glossary';

function Probe() {
  const tr = useT();
  return <p data-testid="probe">{tr('shell:menu.logout', 'Log out')}</p>;
}

beforeEach(async () => {
  localStorage.clear();
  global.fetch = jest.fn(async () => ({ ok: false, status: 500, json: async () => ({}) }));
  await act(async () => {
    await setLanguage('en', { remember: false });
  });
});

test('detection: any el* browser language picks Greek, anything else English', () => {
  expect(browserLanguage(['el-GR', 'en-US'])).toBe('el');
  expect(browserLanguage(['de-DE', 'el'])).toBe('el');
  expect(browserLanguage(['en-US', 'el-GR'])).toBe('en');
  expect(browserLanguage(['fr-FR'])).toBe('en');
  expect(normalizeLanguage('EL')).toBe('el');
  expect(normalizeLanguage('de')).toBeNull();
});

test('switching language re-renders text, updates <html lang> and remembers the choice', async () => {
  render(<Probe />);
  expect(screen.getByTestId('probe').textContent).toBe('Log out');
  expect(document.documentElement.lang).toBe('en');
  await act(async () => {
    await setLanguage('el');
  });
  expect(screen.getByTestId('probe').textContent).toBe('Αποσύνδεση');
  expect(document.documentElement.lang).toBe('el');
  expect(localStorage.getItem('sr_lang')).toBe('el');
  expect(getLocale()).toBe('el-GR');
});

test('Greek plurals use one/other and interpolate count', async () => {
  await act(async () => {
    await setLanguage('el', { remember: false });
  });
  const def = { one: '{{count}} unread message', other: '{{count}} unread messages' };
  expect(t('play:room.unread', def, { count: 1 })).toBe('1 μη αναγνωσμένο μήνυμα');
  expect(t('play:room.unread', def, { count: 3 })).toBe('3 μη αναγνωσμένα μηνύματα');
  expect(t('play:room.unread', def, { count: 0 })).toBe('0 μη αναγνωσμένα μηνύματα');
  await act(async () => {
    await setLanguage('en', { remember: false });
  });
  expect(t('play:room.unread', def, { count: 1 })).toBe('1 unread message');
});

test('a key missing from the JSON falls back to the English default with interpolation', async () => {
  await act(async () => {
    await setLanguage('el', { remember: false });
  });
  expect(t('common:doesNotExist', 'Hello {{name}}', { name: 'Lef' })).toBe('Hello Lef');
});

test('numbers and lists follow the active locale', async () => {
  await act(async () => {
    await setLanguage('el', { remember: false });
  });
  expect(formatNumber(12345.6)).toBe('12.345,6');
  expect(formatList(['Α', 'Β', 'Γ'])).toBe('Α, Β και Γ');
});

test('game terms stay English with an explanation in the active language', async () => {
  await act(async () => {
    await setLanguage('el', { remember: false });
  });
  render(<Term id="hunger" />);
  const el = screen.getByText('Hunger');
  expect(el).toHaveAttribute('lang', 'en');
  expect(el.getAttribute('title')).toMatch(/Κτήνους/);
  expect(termHint('nope')).toBe('');
});

test('the login page language switch translates the whole page', async () => {
  const user = setupUser();
  render(
    <MemoryRouter initialEntries={['/login']}>
      <App />
    </MemoryRouter>
  );
  expect(screen.getByRole('tab', { name: 'Sign in' })).toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Ελληνικά' }));
  await waitFor(() => expect(screen.getByRole('tab', { name: 'Σύνδεση' })).toBeInTheDocument());
  expect(screen.getByRole('button', { name: 'Ελληνικά' })).toHaveAttribute('aria-pressed', 'true');
  expect(screen.getByRole('button', { name: 'Ελληνικά' })).toHaveAttribute('lang', 'el');
  expect(getLanguage()).toBe('el');
  expect(document.documentElement.lang).toBe('el');
  // Logged out: nothing is sent to the server.
  expect(global.fetch).not.toHaveBeenCalledWith(expect.stringContaining('/users/me/language'), expect.anything());
});

test('logged in: the saved account language is applied, and a manual switch is saved', async () => {
  localStorage.setItem('token', 'jwt');
  localStorage.setItem('user', JSON.stringify({ id: 1, username: 'lef', role: 'player' }));
  const calls = [];
  global.fetch = jest.fn(async (url, opts = {}) => {
    calls.push([url, opts.method || 'GET', opts.body]);
    if (url === '/api/users/me/language' && (opts.method || 'GET') === 'GET') {
      return { ok: true, status: 200, json: async () => ({ ui_language: 'el' }) };
    }
    if (url === '/api/users/me') return { ok: true, status: 200, json: async () => ({ id: 1, username: 'lef', role: 'player' }) };
    return { ok: true, status: 200, json: async () => ({}) };
  });
  render(<Probe />);
  const { AuthProvider } = require('../../app/AuthContext');
  render(<AuthProvider><span /></AuthProvider>);
  await waitFor(() => expect(screen.getByTestId('probe').textContent).toBe('Αποσύνδεση'));
  expect(getLanguage()).toBe('el');
  expect(localStorage.getItem('sr_lang')).toBe('el');
  await act(async () => {
    await setLanguage('en');
  });
  expect(calls).toContainEqual(['/api/users/me/language', 'PUT', JSON.stringify({ ui_language: 'en' })]);
});
