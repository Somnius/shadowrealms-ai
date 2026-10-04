import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { apiFetch, errorText, setUnauthorizedHandler } from './http';
import { onLanguageChosen, setLanguage, storedLanguage, t } from '../i18n';

const AuthContext = createContext(null);

function readStoredUser() {
  try {
    const raw = window.localStorage.getItem('user');
    return raw ? JSON.parse(raw) : null;
  } catch (e) {
    return null;
  }
}

function store(key, value) {
  try {
    if (value == null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, typeof value === 'string' ? value : JSON.stringify(value));
  } catch (e) {
    /* private mode */
  }
}

/**
 * Session state: JWT in localStorage (as before), the /users/me profile, login/register/logout.
 * Phase 5 hardens this (cookies, refresh); the shape here is what the rest of the shell uses.
 */
export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => {
    try {
      return window.localStorage.getItem('token');
    } catch (e) {
      return null;
    }
  });
  const [user, setUserState] = useState(readStoredUser);

  const setUser = useCallback((u) => {
    setUserState(u);
    store('user', u);
  }, []);

  const logout = useCallback(() => {
    store('token', null);
    store('user', null);
    setToken(null);
    setUserState(null);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(logout);
    return () => setUnauthorizedHandler(null);
  }, [logout]);

  const refreshUser = useCallback(
    async (tok = token) => {
      if (!tok) return null;
      const r = await apiFetch(tok, '/users/me');
      if (r.ok) {
        setUser(r.data);
        return r.data;
      }
      return null;
    },
    [token, setUser]
  );

  // Hydrate the profile once per token.
  useEffect(() => {
    if (token) refreshUser(token);
  }, [token]); // eslint-disable-line react-hooks/exhaustive-deps

  // Interface language: the user's saved choice wins; a choice made while logged out (stored in
  // this browser) is saved to the account; with neither, the language keeps following the browser.
  useEffect(() => {
    if (!token) return undefined;
    let cancelled = false;
    apiFetch(token, '/users/me/language').then((r) => {
      if (cancelled || !r.ok) return;
      const saved = r.data.ui_language;
      if (saved) setLanguage(saved, { remember: true, save: false });
      else if (storedLanguage()) apiFetch(token, '/users/me/language', { method: 'PUT', body: { ui_language: storedLanguage() } });
    });
    const off = onLanguageChosen((lang) => {
      apiFetch(token, '/users/me/language', { method: 'PUT', body: { ui_language: lang } });
    });
    return () => {
      cancelled = true;
      off();
    };
  }, [token]);

  const acceptToken = useCallback(
    async (accessToken) => {
      store('token', accessToken);
      setToken(accessToken);
      return refreshUser(accessToken);
    },
    [refreshUser]
  );

  const login = useCallback(
    async (username, password) => {
      const r = await apiFetch(null, '/auth/login', { method: 'POST', body: { username, password } });
      if (!r.ok || !r.data.access_token) {
        return { ok: false, error: errorText(r.data, t('auth:login.failed', 'Login failed')) };
      }
      await acceptToken(r.data.access_token);
      return { ok: true };
    },
    [acceptToken]
  );

  const register = useCallback(
    async ({ username, email, password, invite_code: inviteCode }) => {
      const r = await apiFetch(null, '/auth/register', {
        method: 'POST',
        body: { username, email, password, invite_code: inviteCode },
      });
      if (!r.ok || !r.data.access_token) {
        return { ok: false, error: errorText(r.data, t('auth:register.failed', 'Registration failed')) };
      }
      await acceptToken(r.data.access_token);
      return { ok: true };
    },
    [acceptToken]
  );

  const value = useMemo(
    () => ({
      token,
      user,
      isAdmin: user?.role === 'admin',
      isStaff: user?.role === 'admin' || user?.role === 'helper',
      setUser,
      refreshUser,
      login,
      register,
      logout,
    }),
    [token, user, setUser, refreshUser, login, register, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth() needs an <AuthProvider>');
  return ctx;
}

/** Shorthand: apiFetch bound to the current token. */
export function useApi() {
  const { token } = useAuth();
  return useCallback((path, opts) => apiFetch(token, path, opts), [token]);
}
