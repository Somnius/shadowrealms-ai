import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import {
  apiFetch,
  authErrorText,
  getCurrentToken,
  holdSession,
  setCurrentToken,
  setTokenRefreshedHandler,
  setUnauthorizedHandler,
} from './http';
import { clearSessionPrefix, DRAFT_PREFIX } from './hooks';
import {
  forgetStoredLanguage,
  onLanguageChosen,
  setLanguage,
  setLanguageOwner,
  storedLanguage,
  storedLanguageOwner,
  t,
} from '../i18n';

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

function withTimeout(promise, ms) {
  return Promise.race([promise, new Promise((resolve) => setTimeout(() => resolve({ ok: false, status: 0, data: {} }), ms))]);
}

/** apiFetch with whatever access token is current at call time (refreshes don't change identity). */
const call = (path, opts) => apiFetch(getCurrentToken(), path, opts);

/**
 * Session state: short-lived access token in localStorage, refresh token in an HttpOnly cookie
 * (http.js refreshes it on 401 TOKEN_EXPIRED), the /users/me profile, login/register/logout.
 * sessionNotice: why the last session ended on its own ('expired' | 'revoked' | 'invalid' | 'elsewhere' | 'signedOutAll' after a confirmed sign out everywhere).
 */
export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => {
    let tok = null;
    try {
      tok = window.localStorage.getItem('token');
    } catch (e) {
      tok = null;
    }
    setCurrentToken(tok);
    return tok;
  });
  const [user, setUserState] = useState(readStoredUser);
  const [sessionNotice, setSessionNotice] = useState(null);
  const loggingOut = useRef(false);
  const authed = !!token;
  const uid = user && user.id != null ? String(user.id) : null;

  const setUser = useCallback((u) => {
    setUserState(u);
    store('user', u);
  }, []);

  const clearLocal = useCallback((reason) => {
    setCurrentToken(null);
    store('token', null);
    store('user', null);
    clearSessionPrefix(DRAFT_PREFIX);
    setLanguageOwner(null);
    setToken(null);
    setUserState(null);
    setSessionNotice(reason || null);
  }, []);

  /** Ends the session on the server (this device, or every device), then locally. */
  const logout = useCallback(
    async ({ everywhere = false } = {}) => {
      const tok = getCurrentToken();
      let ok = true;
      if (tok) {
        loggingOut.current = true;
        try {
          const r = await withTimeout(call(everywhere ? '/auth/logout-all' : '/auth/logout', { method: 'POST', body: {} }), 6000);
          ok = !!r.ok;
        } catch (e) {
          ok = false;
        } finally {
          loggingOut.current = false;
        }
      }
      // Sign out everywhere only counts when the server confirmed it; plain logout always clears.
      if (everywhere && !ok) return { ok: false };
      clearLocal(everywhere ? 'signedOutAll' : null);
      return { ok };
    },
    [clearLocal]
  );

  useEffect(() => {
    setUnauthorizedHandler((reason) => clearLocal(reason || 'expired'));
    setTokenRefreshedHandler((tok) => {
      if (loggingOut.current) return;
      store('token', tok);
      setToken(tok);
    });
    return () => {
      setUnauthorizedHandler(null);
      setTokenRefreshedHandler(null);
    };
  }, [clearLocal]);

  const refreshUser = useCallback(async () => {
    if (!getCurrentToken()) return null;
    const r = await call('/users/me');
    if (r.ok) {
      setUser(r.data);
      return r.data;
    }
    return null;
  }, [setUser]);

  // Hydrate the profile once per session (not on every token refresh).
  useEffect(() => {
    if (authed) refreshUser();
  }, [authed]); // eslint-disable-line react-hooks/exhaustive-deps

  // Other tabs: a refresh there gives us its token; a logout there ends this tab's session too.
  useEffect(() => {
    const onStorage = (e) => {
      if (e.key !== 'token') return;
      if (e.newValue) {
        const changedUser = !getCurrentToken();
        setCurrentToken(e.newValue);
        setToken(e.newValue);
        if (changedUser) refreshUser();
      } else if (getCurrentToken()) {
        clearLocal('elsewhere');
      }
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, [clearLocal, refreshUser]);

  // Interface language: the user's saved choice wins. A choice stored in this browser is copied to
  // the account only when this user made it (or it was made while signed out, just before this
  // login); one left behind by another account is dropped so it doesn't carry over.
  useEffect(() => {
    if (!authed || !uid) return undefined;
    setLanguageOwner(uid);
    let cancelled = false;
    call('/users/me/language').then((r) => {
      if (cancelled || !r.ok) return;
      const saved = r.data.ui_language;
      if (saved) {
        setLanguage(saved, { remember: true, save: false });
        return;
      }
      const stored = storedLanguage();
      if (!stored) return;
      const owner = storedLanguageOwner();
      if (owner === uid || owner === 'anon') {
        setLanguage(stored, { remember: true, save: false });
        call('/users/me/language', { method: 'PUT', body: { ui_language: stored } });
      } else if (owner) {
        forgetStoredLanguage();
      }
    });
    const off = onLanguageChosen((lang) => {
      call('/users/me/language', { method: 'PUT', body: { ui_language: lang } });
    });
    return () => {
      cancelled = true;
      off();
      setLanguageOwner(null);
    };
  }, [authed, uid]);

  const acceptToken = useCallback(
    async (accessToken) => {
      setCurrentToken(accessToken);
      store('token', accessToken);
      setSessionNotice(null);
      setToken(accessToken);
      return refreshUser();
    },
    [refreshUser]
  );

  const login = useCallback(
    async (username, password) => {
      const r = await apiFetch(null, '/auth/login', { method: 'POST', body: { username, password } });
      if (!r.ok || !r.data.access_token) {
        return { ok: false, status: r.status, error: authErrorText(r.data, t('auth:login.failed', 'Login failed')) };
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
        return { ok: false, status: r.status, code: r.data.code, error: authErrorText(r.data, t('auth:register.failed', 'Registration failed')) };
      }
      await acceptToken(r.data.access_token);
      return { ok: true };
    },
    [acceptToken]
  );

  /**
   * POST /auth/change-password. The server ends every other session and returns a new access token
   * for this one; requests still in flight with the old token wait for it instead of logging out.
   */
  const changePassword = useCallback(async (currentPassword, newPassword) => {
    const p = (async () => {
      const r = await call('/auth/change-password', {
        method: 'POST',
        body: { current_password: currentPassword, new_password: newPassword },
      });
      if (r.ok && r.data.access_token) {
        setCurrentToken(r.data.access_token);
        store('token', r.data.access_token);
        setToken(r.data.access_token);
      }
      return r;
    })();
    const r = await holdSession(p);
    if (r.ok) return { ok: true };
    let error;
    if (r.data.code === 'INVALID_CREDENTIALS') error = t('auth:pw.currentWrong', 'Your current password is not correct.');
    else error = authErrorText(r.data, t('auth:pw.changeFailed', 'Could not change the password.'));
    return { ok: false, code: r.data.code, status: r.status, error };
  }, []);

  const clearSessionNotice = useCallback(() => setSessionNotice(null), []);

  const value = useMemo(
    () => ({
      token,
      user,
      isAdmin: user?.role === 'admin',
      isStaff: user?.role === 'admin' || user?.role === 'helper',
      sessionNotice,
      clearSessionNotice,
      setUser,
      refreshUser,
      login,
      register,
      logout,
      changePassword,
    }),
    [token, user, sessionNotice, clearSessionNotice, setUser, refreshUser, login, register, logout, changePassword]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth() needs an <AuthProvider>');
  return ctx;
}

/**
 * Shorthand: apiFetch with the current access token. Stable across token refreshes, so a refresh
 * doesn't reload rooms or reconnect live updates; it changes only when the session starts or ends.
 */
export function useApi() {
  const { token } = useAuth();
  const authed = !!token;
  return useCallback((path, opts) => apiFetch(authed ? getCurrentToken() : null, path, opts), [authed]);
}
