import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Drawer, Glyph, IconButton } from '../design';
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
export function TopBar({ title, subtitle, icon, actions, onMenu, menuLabel, titleId, children }) {
  const isMobile = useIsMobile();
  const { openNav } = useShell();
  return (
    <header className="sr-topbar">
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

/** Rail + routed page. On phones the rail moves into a left drawer opened from the top bar. */
export default function AppShell() {
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
          <Outlet />
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
