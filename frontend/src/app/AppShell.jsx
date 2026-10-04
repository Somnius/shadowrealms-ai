import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { Outlet, useLocation } from 'react-router';
import { Drawer, FogLayer, Glyph, IconButton, RouteTransition } from '../design';
import ChronicleRail from './ChronicleRail';
import UserMenu from './UserMenu';
import { useIsMobile } from './hooks';
import { t } from '../i18n';
import './shell.css';

const ShellContext = createContext({ openNav: () => {} });
export const useShell = () => useContext(ShellContext);

/**
 * Page header used by every shell page: (mobile menu) · icon · title/subtitle · actions · user menu.
 * There is exactly one user menu and it always lives here.
 */
export function TopBar({ title, subtitle, icon, actions, onMenu, menuLabel, titleId, ambient = false, children }) {
  const isMobile = useIsMobile();
  const { openNav } = useShell();
  return (
    <header className={`sr-topbar${ambient ? ' sr-topbar--ambient' : ''}`}>
      {ambient ? <FogLayer intensity={0.07} speed={0.6} className="sr-topbar__fog" /> : null}
      {isMobile ? (
        <IconButton
          icon="menu"
          label={menuLabel || t('shell:nav.open', 'Open navigation')}
          tooltip={false}
          onClick={onMenu || openNav}
          className="sr-topbar__menu"
        />
      ) : null}
      <div className="sr-topbar__title">
        {typeof icon === 'string' ? <Glyph name={icon} size={20} className="sr-topbar__icon" /> : icon}
        <div className="sr-topbar__text">
          <h1 id={titleId} className="sr-topbar__h">{title}</h1>
          {subtitle ? <div className="sr-topbar__sub">{subtitle}</div> : null}
        </div>
      </div>
      {children}
      <div className="sr-topbar__actions">{actions}</div>
      <UserMenu compact={isMobile} />
    </header>
  );
}

/**
 * Key for the page transition: one per page *type*, never per room or chronicle switch inside the
 * play view (that would remount PlayPage). /chronicles/* pages are distinct components anyway.
 */
export function routeKeyOf(pathname) {
  const parts = String(pathname || '').split('/').filter(Boolean);
  if (!parts.length) return 'root';
  if (parts[0] === 'chronicles') return parts.length > 1 && parts[1] !== 'new' ? 'chronicles/:id' : parts.join('/');
  if (parts[0] === 'c') return parts.length > 2 ? 'play' : 'play-redirect';
  return parts[0];
}

/** Rail + routed page. On phones the rail moves into a left drawer opened from the top bar. */
export default function AppShell() {
  const { pathname } = useLocation();
  const isMobile = useIsMobile();
  const [navOpen, setNavOpen] = useState(false);
  const openNav = useCallback(() => setNavOpen(true), []);
  const closeNav = useCallback(() => setNavOpen(false), []);
  const value = useMemo(() => ({ openNav, closeNav }), [openNav, closeNav]);

  return (
    <ShellContext.Provider value={value}>
      <div className="sr-shell">
        {!isMobile ? (
          <div className="sr-shell__rail">
            <ChronicleRail />
          </div>
        ) : null}
        <div className="sr-shell__main">
          <RouteTransition routeKey={routeKeyOf(pathname)}>
            <Outlet />
          </RouteTransition>
        </div>
      </div>
      {isMobile ? (
        <Drawer open={navOpen} onClose={closeNav} side="left" title={t('shell:nav.title', 'ShadowRealms')}>
          <ChronicleRail expanded onNavigate={closeNav} />
        </Drawer>
      ) : null}
    </ShellContext.Provider>
  );
}

/** Scrollable page body for non-chat pages. */
export function PageBody({ children, narrow = false, className = '' }) {
  return (
    <main className={`sr-page${narrow ? ' sr-page--narrow' : ''} ${className}`.trim()} id="main">
      <div className="sr-page__inner">{children}</div>
    </main>
  );
}
