import React from 'react';
import { Navigate, useLocation } from 'react-router';
import { useAuth } from './AuthContext';

/** Where to go after login: the page the user wanted, unless it was /login itself. */
export function afterLoginPath(state) {
  const from = state && state.from;
  if (from && typeof from.pathname === 'string' && from.pathname !== '/login') {
    return `${from.pathname}${from.search || ''}${from.hash || ''}`;
  }
  return '/chronicles';
}

/** Unauthenticated → /login (remembering where the user was going). */
export function RequireAuth({ children }) {
  const { token } = useAuth();
  const location = useLocation();
  if (!token) return <Navigate to="/login" replace state={{ from: location }} />;
  return children;
}

/** Logged-in users never see the login page. */
export function RedirectIfAuthed({ children }) {
  const { token } = useAuth();
  const location = useLocation();
  if (token) return <Navigate to={afterLoginPath(location.state)} replace />;
  return children;
}

/** Site admins only (others land in the hall). */
export function RequireAdmin({ children }) {
  const { user } = useAuth();
  if (!user) return null; // profile still loading
  if (user.role !== 'admin') return <Navigate to="/chronicles" replace />;
  return children;
}
