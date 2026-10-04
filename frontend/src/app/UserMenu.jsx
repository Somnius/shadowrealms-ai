import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Avatar, Glyph, useMotionPreference } from '../design';
import MenuButton from './Menu';
import { useAuth } from './AuthContext';
import { LANGUAGE_NAMES, setLanguage, t, useLanguage } from '../i18n';

/** The one user menu of the app: profile, language, motion, admin, theme preview, logout. */
export default function UserMenu({ compact = false }) {
  const { user, isAdmin, logout } = useAuth();
  const navigate = useNavigate();
  const { reduced, systemReduced, setPreference } = useMotionPreference();
  const name = user?.username || '';
  const lang = useLanguage();

  const items = [
    { id: 'profile', icon: 'user', label: t('shell:menu.profile', 'Profile & characters'), onSelect: () => navigate('/profile') },
    { divider: true },
    { id: 'language', icon: 'globe', heading: t('shell:menu.language', 'Language') },
    ...Object.entries(LANGUAGE_NAMES).map(([code, label]) => ({
      id: `lang-${code}`,
      label,
      lang: code,
      radio: true,
      checked: lang === code,
      onSelect: () => setLanguage(code),
    })),
    { divider: true },
    {
      id: 'motion',
      icon: 'candle',
      label: systemReduced
        ? t('shell:menu.motionSystem', 'Reduced motion (system setting)')
        : t('shell:menu.motion', 'Reduce motion'),
      checked: reduced,
      disabled: systemReduced,
      onSelect: () => setPreference(reduced ? 'full' : 'reduced'),
    },
    ...(isAdmin ? [{ id: 'admin', icon: 'crown', label: t('shell:menu.admin', 'Admin panel'), onSelect: () => navigate('/admin') }] : []),
    { id: 'showcase', icon: 'eye', label: t('shell:menu.showcase', 'Theme preview'), onSelect: () => navigate('/showcase') },
    { divider: true },
    { id: 'logout', icon: 'logout', label: t('shell:menu.logout', 'Log out'), danger: true, onSelect: () => { logout(); navigate('/login'); } },
  ];

  return (
    <MenuButton
      label={t('shell:menu.button', 'Account menu for {{name}}', { name })}
      menuLabel={t('shell:menu.title', 'Account')}
      items={items}
      renderButton={(props, open) => (
        <button {...props} className={`sr-usermenu__btn${open ? ' is-open' : ''}`}>
          <Avatar src={user?.player_avatar_url} name={name} size={32} alt="" />
          {!compact ? <span className="sr-usermenu__name">{name}</span> : null}
          <Glyph name="chevron-down" size={16} />
        </button>
      )}
    />
  );
}
